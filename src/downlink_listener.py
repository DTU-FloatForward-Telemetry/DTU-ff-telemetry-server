import paho.mqtt.client as mqtt
from dotenv import load_dotenv
import os
import json

load_dotenv('config/.env')

BROKER = os.getenv("HIVEMQ_HOST")
PORT = int(os.getenv("HIVEMQ_PORT"))
USER = os.getenv("HIVEMQ_USER")
PASSWORD = os.getenv("HIVEMQ_PASSWORD")

TOPIC = "boat/commands/motor"

# ==========================
# MQTT callbacks
# ==========================
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print("✅ Connected to HiveMQ")
        client.subscribe(TOPIC)
        print(f"📡 Subscribed to {TOPIC}")
    else:
        print("❌ Connection failed")

def on_message(client, userdata, msg):
    payload = msg.payload.decode()

    print(f"\n📩 RAW MESSAGE: {payload}")

    try:
        data = json.loads(payload)

        speed = data.get("speed")
        direction = data.get("direction")

        print(f"⚙️ Parsed command:")
        print(f"   Speed: {speed}")
        print(f"   Direction: {direction}")

        # 👉 Here is where ESP32 logic would go
        # e.g. set_motor_speed(speed)

    except json.JSONDecodeError:
        print("❌ Invalid JSON format")

# ==========================
# MQTT client setup
# ==========================
client = mqtt.Client(protocol=mqtt.MQTTv5)
client.username_pw_set(USER, PASSWORD)
client.tls_set()

client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER, PORT)
client.loop_forever()