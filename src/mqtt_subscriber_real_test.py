import os
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv("config/.env")

BROKER = os.getenv("HIVEMQ_HOST")
PORT = int(os.getenv("HIVEMQ_PORT", "8883"))
USER = os.getenv("HIVEMQ_USER")
PASSWORD = os.getenv("HIVEMQ_PASSWORD")

def on_connect(client, userdata, flags, rc, properties=None):
    print("Connected:", rc)
    client.subscribe("boat/telemetry/#", qos=0)

def on_message(client, userdata, msg):
    print(f"{msg.topic} -> {msg.payload.decode()}")

client = mqtt.Client(client_id="mqtt_test_subscriber", protocol=mqtt.MQTTv5)
client.username_pw_set(USER, PASSWORD)
client.tls_set()

client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER, PORT)
client.loop_forever()