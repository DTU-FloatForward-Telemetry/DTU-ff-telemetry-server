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
        batch_size=50,
        flush_interval=200
    )
)

# =========================================================
# Topics we want to accept
# =========================================================

ALLOWED_TOPICS = {
    # HV batteries
    "battery/1/voltage",
    "battery/2/voltage",

    "battery/1/current",
    "battery/2/current",

    "battery/1/temperature",
    "battery/2/temperature",

    "battery/1/soc",
    "battery/2/soc",

    "battery/1/power",
    "battery/2/power",

    "battery/1/boardtemp",
    "battery/2/boardtemp",

    "battery/1/totenergy",
    "battery/2/totenergy",

    "battery/1/loaddetect",
    "battery/2/loaddetect",

    "battery/1/status",
    "battery/2/status",

    # HV battery faults
    "battery/1/fault/thermal_runaway",
    "battery/1/fault/dischg_mos_stuck",
    "battery/1/fault/short_circuit",
    "battery/1/fault/chg_mos_stuck",

    "battery/2/fault/thermal_runaway",
    "battery/2/fault/dischg_mos_stuck",
    "battery/2/fault/short_circuit",
    "battery/2/fault/chg_mos_stuck",

    # LV battery
    "battery/3/voltage",

    # DHT
    "dht/temp",
    "dht/hum",

    # Motor
    "motor/valid",
    "motor/enabled",
    "motor/power",
    "motor/speed",
    "motor/direction",
    "motor/current",
    "motor/voltage_dc",
    "motor/torque",
    "motor/temp_motor",
    "motor/temp_inverter",
    "motor/emcy",

    # GPS
    "gps/status",
    "gps/speed",
    "gps/latitude",
    "gps/longitude",
    "gps/Nsatellites",
    "gps/altitude",
    "gps/roll",
    "gps/pitch",
    "gps/heading",
    "gps/valid",

    # IMU
    "imu/batch",

    #Load cell
    "thrust/loadcell_n",
    "thrust/propeller_n",
    # Rotary encoder
    "rotary/angle_deg",
}

# =========================================================
# Expected data types for each topic
# =========================================================

TOPIC_TYPES = {

    # HV batteries
    "battery/1/voltage": float,
    "battery/2/voltage": float,

    "battery/1/current": float,
    "battery/2/current": float,

    "battery/1/temperature": float,
    "battery/2/temperature": float,

    "battery/1/soc": float,
    "battery/2/soc": float,

    "battery/1/power": float,
    "battery/2/power": float,

    "battery/1/boardtemp": float,
    "battery/2/boardtemp": float,

    "battery/1/totenergy": float,
    "battery/2/totenergy": float,

    "battery/1/loaddetect": str,
    "battery/2/loaddetect": str,

    "battery/1/status": str,
    "battery/2/status": str,

    # HV battery faults
    "battery/1/fault/thermal_runaway": int,
    "battery/1/fault/dischg_mos_stuck": int,
    "battery/1/fault/short_circuit": int,
    "battery/1/fault/chg_mos_stuck": int,

    "battery/2/fault/thermal_runaway": int,
    "battery/2/fault/dischg_mos_stuck": int,
    "battery/2/fault/short_circuit": int,
    "battery/2/fault/chg_mos_stuck": int,

    # LV battery
    "battery/3/voltage": float,

    # DHT
    "dht/temp": float,
    "dht/hum": float,

    # Motor
    "motor/valid": int,
    "motor/enabled": int,
    "motor/power": float,
    "motor/speed": float,
    "motor/direction": str,
    "motor/current": float,
    "motor/voltage_dc": float,
    "motor/torque": float,
    "motor/temp_motor": float,
    "motor/temp_inverter": float,
    "motor/emcy": str,

    # GPS
    "gps/status": int,
    "gps/speed": float,
    "gps/latitude": float,
    "gps/longitude": float,
    "gps/Nsatellites": int,
    "gps/altitude": float,
    "gps/roll": float,
    "gps/pitch": float,
    "gps/heading": float,
    "gps/valid": int,

    # IMU
    "imu/batch": str,

    #Load cell
    "thrust/loadcell_n": float,
    "thrust/propeller_n": float,
    # Rotary encoder
    "rotary/angle_deg": float,
}

# =========================================================
# Valid enum values
# =========================================================

VALID_MOTOR_DIRECTIONS = {
    "Forward",
    "Reverse",
    "Neutral",
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
    # Motor emcy handling
    # =========================================================

    if topic_key == "motor/emcy":

        try:

            emcy = json.loads(payload)

            p = (
                Point("telemetry")
                .tag("object", "boat")
                .field(
                    "motor_emcy_code",
                    int(emcy["code"])
                )
                .field(
                    "motor_emcy_event",
                    int(emcy["event"])
                )
            )

            write_api.write(
                bucket=INFLUXDB_BUCKET,
                org=INFLUXDB_ORG,
                record=p
            )

            log("motor/emcy", f"code={emcy['code']} event={emcy['event']}")

        except Exception as e:

            log_warn(f"Invalid motor/emcy payload: {e}")

        return

    # =========================================================
    # Validate and parse payload
    # =========================================================
    expected_type = TOPIC_TYPES.get(topic_key)

    try:
        if expected_type == float:
            value = float(payload)
        elif expected_type == int:
            value = int(payload)
        elif expected_type == str:
            value = payload
        else:
            value = payload

    except ValueError:
        log_warn(f"Invalid payload type for {topic_key}: {payload}")
        return

    # =========================================================
    # Validate motor direction enum
    # =========================================================
    if topic_key == "motor/direction":
        if value not in VALID_MOTOR_DIRECTIONS:
            log_warn(f"Invalid motor direction: {value}")
            return

    # =========================================================
    # Validate gps/valid
    # =========================================================
    if topic_key == "gps/valid":
        if value not in (0, 1):
            log_warn(f"Invalid gps/valid value: {value}")
            return

    # Write to InfluxDB
    p = (
        Point("telemetry")
        .tag("object", "boat")
        .field(
            topic_key.replace("/", "_"),
            value
        )
    )

    write_api.write(
        bucket=INFLUXDB_BUCKET,
        org=INFLUXDB_ORG,
        record=p
    )

    log(topic_key, value)


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
