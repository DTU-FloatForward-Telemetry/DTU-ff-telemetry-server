import os
import json
import ssl
from pathlib import Path
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import WriteOptions


# =========================================================
# Terminal colors
# =========================================================

COLORS = {
    "battery": "\033[33m",
    "battery_lv": "\033[33m",
    "motor": "\033[36m",
    "gps": "\033[32m",
    "imu": "\033[35m",
    "dht": "\033[34m",
    "thrust": "\033[96m",
    "WARN": "\033[91m",
    "RESET": "\033[0m",
    "DIM": "\033[2m",
}


def log(topic_key: str, value):
    group = topic_key.split("/")[0]
    color = COLORS.get(group, COLORS["RESET"])
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{COLORS['DIM']}{ts}{COLORS['RESET']}  {color}{topic_key:<25}{COLORS['RESET']} {value}")


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
PORT = int(os.getenv("HIVEMQ_PORT", "8883"))
USER = os.getenv("HIVEMQ_USER")
PASSWORD = os.getenv("HIVEMQ_PASSWORD")


# =========================================================
# InfluxDB details
# =========================================================

INFLUXDB_URL = os.getenv("INFLUX_URL")
INFLUXDB_TOKEN = os.getenv("INFLUX_TOKEN")
INFLUXDB_ORG = os.getenv("INFLUX_ORG")
INFLUXDB_BUCKET = os.getenv("INFLUX_BUCKET")

print(f"DEBUG: INFLUX_URL is {INFLUXDB_URL}")

if INFLUXDB_URL is None:
    raise ValueError("INFLUX_URL not found! Check your .env file path and keys.")


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
        flush_interval=50,
    )
)


# =========================================================
# Accepted JSON topics
# =========================================================

ALLOWED_TOPICS = {
    "gps",
    "battery/1",
    "battery/2",
    "battery_lv",
    "thrust",
    "motor",
    "dht",
}


# =========================================================
# Helpers
# =========================================================

def parse_ts(data: dict):
    """
    Parses ISO timestamp from JSON field 'ts'.
    Example: 2026-07-08T11:41:42.952Z
    """
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


# =========================================================
# JSON topic handlers
# =========================================================

def handle_gps(data: dict):
    p = (
        Point("telemetry")
        .tag("object", "boat")
        .field("gps_valid", int(data["valid"]))
        .field("gps_status", int(data["status"]))
        .field("gps_Nsatellites", int(data["Nsatellites"]))
        .field("gps_latitude", float(data["latitude"]))
        .field("gps_longitude", float(data["longitude"]))
        .field("gps_altitude", float(data["altitude"]))
        .field("gps_speed", float(data["speed"]))
    )

    p = add_time(p, data)
    write_point(p)

    log("gps", f"lat={data['latitude']} lon={data['longitude']}")


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
    p = (
        Point("telemetry")
        .tag("object", "boat")
        .field("battery_3_voltage", float(data["voltage"]))
        .field("battery_3_current", float(data["current"]))
    )

    p = add_time(p, data)
    write_point(p)

    log("battery_lv", f"voltage={data['voltage']} current={data['current']}")


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


# =========================================================
# MQTT callbacks
# =========================================================

def on_connect(client, userdata, flags, rc, properties=None):
    print(f"Connected: {rc}")

    client.subscribe(
        "boat/telemetry/#",
        qos=0,
    )

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

    try:
        data = json.loads(payload)
    except Exception as e:
        log_warn(f"Invalid JSON on {topic_key}: {e}")
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


# =========================================================
# MQTT client setup
# =========================================================

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


# =========================================================
# Connect
# =========================================================

client.connect(
    BROKER,
    PORT,
)

print("MQTT JSON subscriber running...")

client.loop_forever()