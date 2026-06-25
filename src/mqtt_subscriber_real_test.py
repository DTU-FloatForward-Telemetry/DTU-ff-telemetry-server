import os
import paho.mqtt.client as mqtt
from pathlib import Path
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
    # HV batteries
    "battery/1/voltage",
    "battery/2/voltage",

    "battery/1/current",
    "battery/2/current",

    "battery/1/temperature",
    "battery/2/temperature",

    "battery/1/soc",
    "battery/2/soc",

    # LV battery
    "battery/3/voltage",

    # DHT
    "dht/temp",

    # Motor
    "motor/power",
    "motor/speed",
    "motor/direction",
    "motor/current",
    "motor/voltage_dc",
    "motor/torque",
    "motor/temp_motor"
    "motor/temp_inverter",
    "motor/emcy"

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

    # LV battery
    "battery/3/voltage": float,

    # DHT
    "dht/temp": float,

    # Motor
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
        print(
            f"Ignored unknown topic: "
            f"{msg.topic}"
        )
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

            print(
                f"Written {len(points)} "
                f"IMU samples to InfluxDB"
            )

        except Exception as e:

            print(
                f"Invalid IMU batch: {e}"
            )

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
        print(
            f"Invalid payload type for "
            f"{topic_key}: {payload}"
        )
        return

    print(
        f"{msg.topic} -> {value}"
    )

    # =========================================================
    # Validate motor direction enum
    # =========================================================
    if topic_key == "motor/direction":
        if value not in VALID_MOTOR_DIRECTIONS:
            print(
                f"Invalid motor direction: "
                f"{value}"
            )
            return

    # =========================================================
    # Validate gps/valid
    # =========================================================
    if topic_key == "gps/valid":
        if value not in (0, 1):
            print(
                f"Invalid gps/valid value: "
                f"{value}"
            )
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

    print(
        f"Written to InfluxDB: "
        f"{topic_key} = {value}"
    )


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
