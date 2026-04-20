import paho.mqtt.client as mqtt
from dotenv import load_dotenv
import os
import json

load_dotenv("config/.env")

BROKER = os.getenv("HIVEMQ_HOST")
PORT = int(os.getenv("HIVEMQ_PORT"))
USER = os.getenv("HIVEMQ_USER")
PASSWORD = os.getenv("HIVEMQ_PASSWORD")

TOPICS = [
    ("boat/message/text", 1),
    ("boat/message/power", 1),
]

# ==========================
# MQTT callbacks
# ==========================
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print("✅ Connected to HiveMQ")

        for topic, qos in TOPICS:
            client.subscribe(topic, qos=qos)
            print(f"📡 Subscribed to {topic} (QoS {qos})")
    else:
        print(f"❌ Connection failed with code: {rc}")


def on_message(client, userdata, msg):
    topic = msg.topic
    payload = msg.payload.decode().strip()

    print(f"\n📩 Topic: {topic}")
    print(f"📦 RAW MESSAGE: {payload}")

    if topic == "boat/message/text":
        if payload:
            print(f"💬 Free message: {payload}")
            # 👉 ESP32 logic: handle_free_message(payload)
        else:
            print("⚠️ Empty text message received")

    elif topic == "boat/message/power":
        try:
            data = json.loads(payload)

            power_min = data.get("powerMin")
            power_max = data.get("powerMax")

            if power_min is not None or power_max is not None:
                print(f"⚡ Target power range: {power_min} – {power_max} kW")
                # 👉 ESP32 logic: set_target_power_range(power_min, power_max)
            else:
                print("⚠️ Power JSON received but no powerMin/powerMax found")

        except json.JSONDecodeError:
            print("❌ Invalid JSON format on boat/message/power")

    else:
        print("⚠️ Message received on unexpected topic")


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