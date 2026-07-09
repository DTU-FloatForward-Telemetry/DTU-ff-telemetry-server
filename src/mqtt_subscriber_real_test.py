import os
import json
import ast
from pathlib import Path
from datetime import datetime, timedelta

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import WriteOptions


COLORS = {
    "battery": "\033[33m",
    "battery_lv": "\033[33m",
    "motor": "\033[36m",
    "gps": "\033[32m",
    "dht": "\033[34m",
    "thrust": "\033[96m",
    "imu": "\033[35m",
    "WARN": "\033[91m",
    "RESET": "\033[0m",
    "DIM": "\033[2m",
}


def log(topic_key: str, value):
    group = topic_key.split("/")[0]
    color = COLORS.get(group, COLORS["RESET"])
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{COLORS['DIM']}{ts}{COLORS['RESET']}  {color}{topic_key:<35}{COLORS['RESET']} {value}")


def log_warn(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{COLORS['DIM']}{ts}{COLORS['RESET']}  {COLORS['WARN']}{msg}{COLORS['RESET']}")


BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / "config" / ".env"
load_dotenv(ENV_PATH)

BROKER = os.getenv("HIVEMQ_HOST")
PORT = int(os.getenv("HIVEMQ_PORT", "8883"))
USER = os.getenv("HIVEMQ_USER")
PASSWORD = os.getenv("HIVEMQ_PASSWORD")

INFLUXDB_URL = os.getenv("INFLUX_URL")
INFLUXDB_TOKEN = os.getenv("INFLUX_TOKEN")
INFLUXDB_ORG = os.getenv("INFLUX_ORG")
INFLUXDB_BUCKET = os.getenv("INFLUX_BUCKET")

print(f"DEBUG: INFLUX_URL is {INFLUXDB_URL}")

if INFLUXDB_URL is None:
    raise ValueError("INFLUX_URL not found! Check your .env file path and keys.")


client_db = InfluxDBClient(
    url=INFLUXDB_URL,
    token=INFLUXDB_TOKEN,
    org=INFLUXDB_ORG,
)

write_api = client_db.write_api(
    write_options=WriteOptions(
        batch_size=50,
        flush_interval=50,
    )
)


ALLOWED_TOPICS = {
    # JSON topics
    "gps",
    "battery/1",
    "battery/2",
    "battery_lv",
    "thrust",
    "motor",
    "dht",

    # Unchanged from main branch
    "imu/batch",

    # Battery 1 fault topics
    "battery/1/fault/thermal_runaway",
    "battery/1/fault/dischg_mos_stuck",
    "battery/1/fault/short_circuit",
    "battery/1/fault/chg_mos_stuck",

    # Battery 2 fault topics
    "battery/2/fault/thermal_runaway",
    "battery/2/fault/dischg_mos_stuck",
    "battery/2/fault/short_circuit",
    "battery/2/fault/chg_mos_stuck",
}


def parse_ts(data: dict):
    ts = data.get("ts")

    if not ts:
        return None

    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        log_warn(f"Invalid timestamp: {ts}")
        return None


def add_time(point: Point, data: dict):
    parsed_time = parse_ts(data)

    if parsed_time:
        point.time(parsed_time, WritePrecision.NS)

    return point


def write_point(point: Point):
    write_api.write(
        bucket=INFLUXDB_BUCKET,
        org=INFLUXDB_ORG,
        record=point,
    )


def parse_payload(payload: str):
    """Parse a payload as JSON, falling back to Python dict-literal
    syntax (e.g. single quotes) if standard JSON parsing fails."""
    try:
        return json.loads(payload)
    except Exception:
        pass

    try:
        value = ast.literal_eval(payload)
        if isinstance(value, dict):
            return value
    except Exception:
        pass

    return None


def handle_gps(data: dict):
    p = Point("telemetry").tag("object", "boat")

    if "valid" in data:
        p.field("gps_valid", int(data["valid"]))

    if "status" in data:
        p.field("gps_status", int(data["status"]))

    if "Nsatellites" in data:
        p.field("gps_Nsatellites", int(data["Nsatellites"]))

    if "latitude" in data:
        p.field("gps_latitude", float(data["latitude"]))

    if "longitude" in data:
        p.field("gps_longitude", float(data["longitude"]))

    if "altitude" in data:
        p.field("gps_altitude", float(data["altitude"]))

    if "speed" in data:
        p.field("gps_speed", float(data["speed"]))

    p = add_time(p, data)
    write_point(p)

    log("gps", f"lat={data.get('latitude')} lon={data.get('longitude')}")


def handle_battery(data: dict, battery_id: int):
    prefix = f"battery_{battery_id}"

    p = (
        Point("telemetry")
        .tag("object", "boat")
        .field(f"{prefix}_voltage", float(data["voltage"]))
        .field(f"{prefix}_current", float(data["current"]))
        .field(f"{prefix}_temperature", float(data["temperature"]))
        .field(f"{prefix}_power", float(data["power"]))
        .field(f"{prefix}_totenergy", float(data["totenergy"]))
        .field(f"{prefix}_boardtemp", float(data["boardtemp"]))
        .field(f"{prefix}_soc", float(data["soc"]))
        .field(f"{prefix}_status", str(data["status"]))
        .field(f"{prefix}_loaddetect", str(data["loaddetect"]))
    )

    p = add_time(p, data)
    write_point(p)

    log(f"battery/{battery_id}", f"SOC={data['soc']} status={data['status']}")


def handle_battery_lv(data: dict):
    p = Point("telemetry").tag("object", "boat")

    if "voltage" in data:
        p.field("lv_voltage", float(data["voltage"]))

    if "temp" in data:
        p.field("lv_temp", float(data["temp"]))

    if "current" in data:
        p.field("lv_current", float(data["current"]))

    p = add_time(p, data)
    write_point(p)

    log("battery_lv", f"voltage={data.get('voltage')} temp={data.get('temp')}")


def handle_thrust(data: dict):
    p = (
        Point("telemetry")
        .tag("object", "boat")
        .field("thrust_loadcell_n", float(data["loadcell_n"]))
        .field("thrust_propeller_n", float(data["propeller_n"]))
        .field("rotary_angle_deg", float(data["angle_deg"]))
    )

    p = add_time(p, data)
    write_point(p)

    log("thrust", f"loadcell={data['loadcell_n']} propeller={data['propeller_n']}")


def handle_motor(data: dict):
    p = Point("telemetry").tag("object", "boat")

    if "valid" in data:
        p.field("motor_valid", int(data["valid"]))

    if "enabled" in data:
        p.field("motor_enabled", int(data["enabled"]))

    if "power" in data:
        p.field("motor_power", float(data["power"]))

    if "speed" in data:
        p.field("motor_speed", float(data["speed"]))

    if "direction" in data:
        p.field("motor_direction", str(data["direction"]))

    if "current" in data:
        p.field("motor_current", float(data["current"]))

    if "voltage_dc" in data:
        p.field("motor_voltage_dc", float(data["voltage_dc"]))

    if "torque" in data:
        p.field("motor_torque", float(data["torque"]))

    if "temp_motor" in data:
        p.field("motor_temp_motor", float(data["temp_motor"]))

    if "temp_inverter" in data:
        p.field("motor_temp_inverter", float(data["temp_inverter"]))

    if "emcy" in data and isinstance(data["emcy"], dict):
        emcy = data["emcy"]

        if "code" in emcy:
            p.field("motor_emcy_code", int(emcy["code"]))

        if "event" in emcy:
            p.field("motor_emcy_event", int(emcy["event"]))

    p = add_time(p, data)
    write_point(p)

    log("motor", "written")


def handle_dht(data: dict):
    p = Point("telemetry").tag("object", "boat")

    if "temp" in data:
        p.field("dht_temp", float(data["temp"]))

    if "hum" in data:
        p.field("dht_hum", float(data["hum"]))

    p = add_time(p, data)
    write_point(p)

    log("dht", "written")


def handle_imu_batch(payload: str):
    try:
        imu_data = json.loads(payload)

        samples = imu_data.get("samples", [])
        count = imu_data.get("count", 0)

        if count != len(samples):
            log_warn("IMU count mismatch")
            return

        base_time = parse_ts(imu_data)
        base_t_boot = samples[0]["t"] if samples and "t" in samples[0] else None

        points = []
        required_keys = {"t", "ax", "ay", "az", "gx", "gy", "gz"}

        for sample in samples:
            if not required_keys.issubset(sample):
                log_warn("Invalid IMU sample keys")
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

            # Each sample shares the batch's "ts", so offset by this
            # sample's own boot-relative "t" to give every point a
            # distinct, correctly-ordered timestamp. Without this,
            # all samples in the batch would land on the same
            # timestamp and overwrite each other in InfluxDB.
            if base_time is not None and base_t_boot is not None:
                offset_ms = int(sample["t"]) - int(base_t_boot)
                p.time(base_time + timedelta(milliseconds=offset_ms), WritePrecision.NS)

            points.append(p)

        write_api.write(
            bucket=INFLUXDB_BUCKET,
            org=INFLUXDB_ORG,
            record=points,
        )

        log("imu/batch", f"{len(points)} samples")

    except Exception as e:
        log_warn(f"Invalid IMU batch: {e}")


def handle_battery_fault(topic_key: str, payload: str):
    data = parse_payload(payload)

    if data is None or "status" not in data:
        log_warn(f"Invalid fault payload for {topic_key}: {payload}")
        return

    p = (
        Point("telemetry")
        .tag("object", "boat")
        .field(topic_key.replace("/", "_"), str(data["status"]))
    )

    p = add_time(p, data)
    write_point(p)

    log(topic_key, data["status"])


def on_connect(client, userdata, flags, rc, properties=None):
    print(f"Connected: {rc}")
    client.subscribe("boat/telemetry/#", qos=0)
    print("Subscribed to boat/telemetry/#")


def on_disconnect(client, userdata, rc, properties=None):
    print(f"Disconnected from MQTT broker (rc={rc})")

    if rc != 0:
        print("Unexpected disconnection. Trying to reconnect...")


def on_message(client, userdata, msg):
    topic_key = msg.topic.replace("boat/telemetry/", "")
    payload = msg.payload.decode().strip()

    if topic_key not in ALLOWED_TOPICS:
        log_warn(f"Ignored unknown topic: {msg.topic}")
        return

    if topic_key.startswith("battery/") and "/fault/" in topic_key:
        handle_battery_fault(topic_key, payload)
        return

    if topic_key == "imu/batch":
        handle_imu_batch(payload)
        return

    data = parse_payload(payload)
    if data is None:
        log_warn(f"Invalid JSON on {topic_key}: {payload}")
        return

    try:
        if topic_key == "gps":
            handle_gps(data)

        elif topic_key == "battery/1":
            handle_battery(data, 1)

        elif topic_key == "battery/2":
            handle_battery(data, 2)

        elif topic_key == "battery_lv":
            handle_battery_lv(data)

        elif topic_key == "thrust":
            handle_thrust(data)

        elif topic_key == "motor":
            handle_motor(data)

        elif topic_key == "dht":
            handle_dht(data)

    except KeyError as e:
        log_warn(f"Missing key in {topic_key}: {e}")

    except ValueError as e:
        log_warn(f"Invalid value type in {topic_key}: {e}")

    except Exception as e:
        log_warn(f"Error handling {topic_key}: {e}")


client = mqtt.Client(
    client_id="boat_telemetry_bridge_json",
    protocol=mqtt.MQTTv5,
)

client.reconnect_delay_set(
    min_delay=1,
    max_delay=30,
)

client.username_pw_set(
    USER,
    PASSWORD,
)

client.tls_set()

client.on_connect = on_connect
client.on_message = on_message
client.on_disconnect = on_disconnect

client.connect(
    BROKER,
    PORT,
)

print("MQTT JSON subscriber running...")

client.loop_forever()