import os
import paho.mqtt.client as mqtt

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

load_dotenv("../config/.env")

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
        batch_size=1
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

    # Parse float when possible
    try:
        value = float(payload)

    except ValueError:
        value = payload

    print(
        f"{msg.topic} -> {value}"
    )

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
    client_id="mqtt_test_subscriber",
    protocol=mqtt.MQTTv5
)

client.username_pw_set(
    USER,
    PASSWORD
)

client.tls_set()

client.on_connect = on_connect

client.on_message = on_message

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