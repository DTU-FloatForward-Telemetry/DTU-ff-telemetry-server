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

        speed_min = data.get("speedMin")
        speed_max = data.get("speedMax")
        power_min = data.get("powerMin")
        power_max = data.get("powerMax")
        message = data.get("message")

        if speed_min is not None or speed_max is not None:
            print(f"🚤 Target speed range: {speed_min} – {speed_max} knots")
            # 👉 ESP32 logic: set_target_speed_range(speed_min, speed_max)

        if power_min is not None or power_max is not None:
            print(f"⚡ Target power range: {power_min} – {power_max} kW")
            # 👉 ESP32 logic: set_target_power_range(power_min, power_max)

        if message is not None:
            print(f"💬 Free message: {message}")
            # 👉 ESP32 logic: handle_free_message(message)

        if not data:
            print("⚠️ Empty command received")

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