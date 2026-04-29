import os
import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import WriteOptions

load_dotenv("config/.env")

# ==========================
# HiveMQ cloud details
# ==========================
BROKER = os.getenv("HIVEMQ_HOST")
PORT = int(os.getenv("HIVEMQ_PORT", "8883"))
USER = os.getenv("HIVEMQ_USER")
PASSWORD = os.getenv("HIVEMQ_PASSWORD")

# ==========================
# InfluxDB details
# ==========================
INFLUXDB_URL = os.getenv("INFLUX_URL")
INFLUXDB_TOKEN = os.getenv("INFLUX_TOKEN")
INFLUXDB_ORG = os.getenv("INFLUX_ORG")
INFLUXDB_BUCKET = os.getenv("INFLUX_BUCKET")

client_db = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
write_api = client_db.write_api(write_options=WriteOptions(batch_size=1))

def on_connect(client, userdata, flags, rc, properties=None):
    print("Connected:", rc)
    client.subscribe("boat/telemetry/#", qos=0)

def on_message(client, userdata, msg):
    topic_key = msg.topic.replace("boat/telemetry/", "")
    payload = msg.payload.decode().strip()

    # Parse float when possible
    try:
        value = float(payload)
    except ValueError:
        value = payload

    print(f"{msg.topic} -> {value}")

    # Write to InfluxDB
    p = Point("telemetry").tag("object", "boat").field(topic_key.replace("/", "_"), value)
    write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=p)
    print(f"Written to InfluxDB: {topic_key} = {value}")

client = mqtt.Client(client_id="mqtt_test_subscriber", protocol=mqtt.MQTTv5)
client.username_pw_set(USER, PASSWORD)
client.tls_set()

client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER, PORT)
client.loop_forever()