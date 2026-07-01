import os
import paho.mqtt.client as mqtt
from pathlib import Path
from datetime import datetime
import json

from dotenv import load_dotenv

from influxdb_client import (
    InfluxDBClient,
    Point,
)

from influxdb_client.client.write_api import (
    WriteOptions,
)

# =========================================================
# Terminal colors
# =========================================================

COLORS = {
    "battery": "\033[33m",   # yellow
    "motor":   "\033[36m",   # cyan
    "gps":     "\033[32m",   # green
    "imu":     "\033[35m",   # magenta
    "dht":     "\033[34m",   # blue
    "thrust":  "\033[96m",   # bright cyan
    "rotary":  "\033[94m",   # bright blue
    "WARN":    "\033[91m",   # red
    "RESET":   "\033[0m",
    "DIM":     "\033[2m",
}

def log(topic_key: str, value):
    group = topic_key.split("/")[0]
    color = COLORS.get(group, COLORS["RESET"])
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{COLORS['DIM']}{ts}{COLORS['RESET']}  {color}{topic_key:<35}{COLORS['RESET']} {value}")

def log_warn(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{COLORS['DIM']}{ts}{COLORS['RESET']}  {COLORS['WARN']}{msg}{COLORS['RESET']}")

# =========================================================
# Load environment variables
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / "config" / ".env"
load_dotenv(ENV_PATH)

# =========================================================
# HiveMQ Cloud details
# =========================================================

BROKER = os.getenv("HIVEMQ_HOST")

PORT = int(
    os.getenv("HIVEMQ_PORT", "8883")
)

USER = os.getenv("HIVEMQ_USER")

PASSWORD = os.getenv("HIVEMQ_PASSWORD")

# =========================================================
# InfluxDB details
# =========================================================

INFLUXDB_URL = os.getenv("INFLUX_URL")

print(f"DEBUG: INFLUX_URL is {INFLUXDB_URL}")

if INFLUXDB_URL is None:
    raise ValueError(
        "INFLUX_URL not found! "
        "Check your .env file path and keys."
    )

INFLUXDB_TOKEN = os.getenv("INFLUX_TOKEN")

INFLUXDB_ORG = os.getenv("INFLUX_ORG")

INFLUXDB_BUCKET = os.getenv("INFLUX_BUCKET")

# =========================================================
# InfluxDB client
# =========================================================

client_db = InfluxDBClient(
    url=INFLUXDB_URL,
    token=INFLUXDB_TOKEN,
    org=INFLUXDB_ORG,
)

write_api = client_db.write_api(
    write_options=WriteOptions(
        batch_size=500,
        flush_interval=1000
    )
)

# =========================================================
# Topics we want to accept
# =========================================================

ALLOWED_TOPICS = {
    # HV batteries (JSON batch)
    "battery/1",
    "battery/2",

    # HV battery faults (JSON {"status":"FAULT"/"OK","ts":"..."})
    "battery/1/fault/thermal_runaway",
    "battery/1/fault/dischg_mos_stuck",
    "battery/1/fault/short_circuit",
    "battery/1/fault/chg_mos_stuck",

    "battery/2/fault/thermal_runaway",
    "battery/2/fault/dischg_mos_stuck",
    "battery/2/fault/short_circuit",
    "battery/2/fault/chg_mos_stuck",

    # Motor emcy (JSON {"code":X,"event":Y}, no ts)
    "motor/emcy",

    # IMU
    "imu/batch",

    # JSON batch topics with ts
    "thrust",
    "motor",
    "gps",
    "dht",
}

# =========================================================
# Expected data types for each topic
# =========================================================

TOPIC_TYPES = {
    # all handled explicitly in on_message — this dict only needed for future fallthrough
}

# =========================================================
# MQTT callbacks
# =========================================================

def on_connect(
        client,
        userdata,
        flags,
        rc,
        properties=None
):
    print(f"Connected: {rc}")

    # Subscribe to all telemetry topics
    client.subscribe(
        "boat/telemetry/#",
        qos=0
    )

    print(
        "Subscribed to "
        "boat/telemetry/#"
    )


# =========================================================

def on_disconnect(
        client,
        userdata,
        rc,
        properties=None
):
    print(
        f"Disconnected from MQTT broker "
        f"(rc={rc})"
    )

    # rc == 0 means clean disconnect
    if rc != 0:
        print(
            "Unexpected disconnection. "
            "Trying to reconnect..."
        )


# =========================================================

def on_message(
        client,
        userdata,
        msg
):
    topic_key = msg.topic.replace(
        "boat/telemetry/",
        ""
    )

    # Ignore unknown topics
    if topic_key not in ALLOWED_TOPICS:
        log_warn(f"Ignored unknown topic: {msg.topic}")
        return

    payload = msg.payload.decode().strip()

    # =========================================================
    # IMU batch handling
    # =========================================================

    if topic_key == "imu/batch":

        try:

            imu_data = json.loads(payload)

            samples = imu_data.get("samples", [])

            count = imu_data.get("count", 0)

            # Validate count
            if count != len(samples):

                print(
                    "IMU count mismatch"
                )

                return

            points = []

            required_keys = {
                "t",
                "ax",
                "ay",
                "az",
                "gx",
                "gy",
                "gz",
            }

            for sample in samples:

                # Validate IMU sample keys
                if not required_keys.issubset(sample):

                    print(
                        "Invalid IMU sample keys"
                    )

                    continue

                p = (
                    Point("imu")
                    .tag("object", "boat")

                    .field("ax", float(sample["ax"]))
                    .field("ay", float(sample["ay"]))
                    .field("az", float(sample["az"]))

                    .field("gx", float(sample["gx"]))
                    .field("gy", float(sample["gy"]))
                    .field("gz", float(sample["gz"]))

                    .field("t_boot_ms", int(sample["t"]))
                )

                points.append(p)

            write_api.write(
                bucket=INFLUXDB_BUCKET,
                org=INFLUXDB_ORG,
                record=points
            )

            log("imu/batch", f"{len(points)} samples")

        except Exception as e:

            log_warn(f"Invalid IMU batch: {e}")

        return

    # =========================================================
    # Thrust JSON batch handling
    # =========================================================

    if topic_key == "thrust":

        try:

            data = json.loads(payload)

            ts = data.get("ts")

            p = Point("telemetry").tag("object", "boat")

            if "loadcell_n" in data:
                p = p.field("thrust_loadcell_n", float(data["loadcell_n"]))

            if "propeller_n" in data:
                p = p.field("thrust_propeller_n", float(data["propeller_n"]))

            if "angle_deg" in data:
                p = p.field("rotary_angle_deg", float(data["angle_deg"]))

            if not ts:
                log_warn(f"Missing ts in thrust payload")
                return

            p = p.time(datetime.fromisoformat(ts.replace("Z", "+00:00")))

            write_api.write(
                bucket=INFLUXDB_BUCKET,
                org=INFLUXDB_ORG,
                record=p
            )

            log("thrust", f"loadcell={data.get('loadcell_n')} propeller={data.get('propeller_n')} angle={data.get('angle_deg')} ts={ts}")

        except Exception as e:

            log_warn(f"Invalid thrust payload: {e}")

        return

    # =========================================================
    # Motor JSON batch handling
    # =========================================================

    if topic_key == "motor":

        try:

            data = json.loads(payload)
            ts = data.get("ts")

            p = Point("telemetry").tag("object", "boat")

            float_fields = ["power", "speed", "current", "voltage_dc", "torque", "temp_motor", "temp_inverter"]
            int_fields   = ["valid", "enabled"]

            for f in float_fields:
                if f in data:
                    p = p.field(f"motor_{f}", float(data[f]))

            for f in int_fields:
                if f in data:
                    p = p.field(f"motor_{f}", int(data[f]))

            if "direction" in data:
                p = p.field("motor_direction", str(data["direction"]))

            if "emcy" in data and isinstance(data["emcy"], dict):
                emcy = data["emcy"]
                if "active" in emcy:
                    p = p.field("motor_emcy_active", int(bool(emcy["active"])))
                if "code" in emcy:
                    p = p.field("motor_emcy_code", int(emcy["code"]))
                if "event" in emcy:
                    p = p.field("motor_emcy_event", int(emcy["event"]))

            if not ts:
                log_warn(f"Missing ts in motor payload")
                return

            p = p.time(datetime.fromisoformat(ts.replace("Z", "+00:00")))

            write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=p)
            log("motor", f"valid={data.get('valid')} enabled={data.get('enabled')} direction={data.get('direction')} speed={data.get('speed')} current={data.get('current')} voltage_dc={data.get('voltage_dc')} torque={data.get('torque')} temp_motor={data.get('temp_motor')} temp_inverter={data.get('temp_inverter')} power={data.get('power')} ts={ts}")

        except Exception as e:

            log_warn(f"Invalid motor payload: {e}")

        return

    # =========================================================
    # GPS JSON batch handling
    # =========================================================

    if topic_key == "gps":

        try:

            data = json.loads(payload)
            ts = data.get("ts")

            p = Point("telemetry").tag("object", "boat")

            float_fields = ["latitude", "longitude", "altitude", "speed", "roll", "pitch", "heading"]
            int_fields   = ["valid", "status", "Nsatellites",
                            "imu_valid", "fix_type", "satellites",
                            "status_stale", "position_stale", "speed_stale",
                            "attitude_stale", "imu_stale", "can_rx_count", "imu_dropped_count"]

            for f in float_fields:
                if f in data:
                    p = p.field(f"gps_{f}", float(data[f]))

            for f in int_fields:
                if f in data:
                    p = p.field(f"gps_{f}", int(data[f]))

            if not ts:
                log_warn(f"Missing ts in gps payload")
                return

            p = p.time(datetime.fromisoformat(ts.replace("Z", "+00:00")))

            write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=p)
            log("gps", f"lat={data.get('latitude')} lon={data.get('longitude')} speed={data.get('speed')} sats={data.get('Nsatellites', data.get('satellites'))} ts={ts}")

        except Exception as e:

            log_warn(f"Invalid gps payload: {e}")

        return

    # =========================================================
    # DHT JSON batch handling
    # =========================================================

    if topic_key == "dht":

        try:

            data = json.loads(payload)
            ts = data.get("ts")

            p = Point("telemetry").tag("object", "boat")

            if "temp" in data:
                p = p.field("dht_temp", float(data["temp"]))
            if "hum" in data:
                p = p.field("dht_hum", float(data["hum"]))

            if not ts:
                log_warn(f"Missing ts in dht payload")
                return

            p = p.time(datetime.fromisoformat(ts.replace("Z", "+00:00")))

            write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=p)
            log("dht", f"temp={data.get('temp')} hum={data.get('hum')} ts={ts}")

        except Exception as e:

            log_warn(f"Invalid dht payload: {e}")

        return

    # =========================================================
    # Battery JSON batch handling (battery/1 and battery/2)
    # =========================================================

    if topic_key in ("battery/1", "battery/2"):

        batt_num = topic_key.split("/")[1]

        try:

            data = json.loads(payload)
            ts = data.get("ts")

            if not ts:
                log_warn(f"Missing ts in {topic_key} payload")
                return

            p = Point("telemetry").tag("object", "boat").tag("battery", batt_num)

            float_fields = ["voltage", "current", "temperature", "power", "totenergy", "boardtemp"]
            str_fields   = ["status", "loaddetect"]

            for f in float_fields:
                if f in data:
                    p = p.field(f"battery_{f}", float(data[f]))

            for f in str_fields:
                if f in data:
                    p = p.field(f"battery_{f}", str(data[f]))

            p = p.time(datetime.fromisoformat(ts.replace("Z", "+00:00")))

            write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=p)
            log(topic_key, f"voltage={data.get('voltage')} current={data.get('current')} soc={data.get('soc')} status={data.get('status')} ts={ts}")

        except Exception as e:

            log_warn(f"Invalid {topic_key} payload: {e}")

        return

    # =========================================================
    # Battery fault handling (JSON {"status":"FAULT"/"OK","ts":"..."})
    # =========================================================

    if topic_key.startswith("battery/") and "/fault/" in topic_key:

        try:

            data = json.loads(payload)
            ts = data.get("ts")
            status = data.get("status", "")

            if not ts:
                log_warn(f"Missing ts in {topic_key} payload")
                return

            field_name = topic_key.replace("/", "_")
            p = (
                Point("telemetry")
                .tag("object", "boat")
                .field(field_name, str(status))
                .time(datetime.fromisoformat(ts.replace("Z", "+00:00")))
            )

            write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=p)
            log(topic_key, f"status={status} ts={ts}")

        except Exception as e:

            log_warn(f"Invalid {topic_key} payload: {e}")

        return

    # =========================================================
    # Motor emcy handling (JSON {"code":X,"event":Y}, no ts)
    # =========================================================

    if topic_key == "motor/emcy":

        try:

            data = json.loads(payload)

            p = (
                Point("telemetry")
                .tag("object", "boat")
                .field("motor_emcy_code", int(data.get("code", 0)))
                .field("motor_emcy_event", int(data.get("event", 0)))
            )

            write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=p)
            log("motor/emcy", f"code={data.get('code')} event={data.get('event')}")

        except Exception as e:

            log_warn(f"Invalid motor/emcy payload: {e}")

        return


# =========================================================
# MQTT client setup
# =========================================================

client = mqtt.Client(
    client_id="boat_telemetry_bridge",
    protocol=mqtt.MQTTv5
)

client.reconnect_delay_set(
    min_delay=1,
    max_delay=30
)

client.username_pw_set(
    USER,
    PASSWORD
)

client.tls_set()

client.on_connect = on_connect
client.on_message = on_message
client.on_disconnect = on_disconnect

# =========================================================
# Connect
# =========================================================

client.connect(
    BROKER,
    PORT
)

print(
    "MQTT subscriber running..."
)

client.loop_forever()
