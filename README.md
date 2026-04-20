# 🚢 Float Forward Telemetry Server  
### DTU Boat Telemetry Pipeline

A modern telemetry backend for the Float Forward (DTU) boat.  
This system replaces last year's Raspberry Pi with a more reliable, cloud-integrated stack:

- **HiveMQ Cloud** – secure MQTT broker  
- **Python MQTT Bridge** – receives telemetry & writes to InfluxDB  
- **InfluxDB** – time-series storage  
- **Grafana** – real-time dashboards  
- **Cloudflare Tunnel** – remote access  
- **ESP32 Simulator** – realistic telemetry generator for development  

Designed to run on the **DTU mini-PC telemetry server**.

---

# ⚡ System Architecture

## Bidirectional Communication Flow

### **Uplink** (Boat → Server: Telemetry Data)
```
ESP32 / Simulator
    │ (publishes telemetry)
    ▼
HiveMQ Cloud (boat/telemetry/#)
    │
    ▼
mqtt_subscriber_real_test.py
    │ (receives & processes)
    ▼
Your Application / InfluxDB
```

### **Downlink** (Server → Boat: Commands)
```
Your API
    │ (publishes commands)
    ▼
HiveMQ Cloud (boat/message/#)
    │
    ▼
downlink_listener.py
    │ (receives & forwards)
    ▼
ESP32 (via serial/wireless)
```

---

# 📂 Project Structure

```
DTU-ff-telemetry-server/
│
├── src/
│   ├── downlink_listener.py              # Receives API commands from HiveMQ → forwards to ESP32
│   ├── mqtt_subscriber_real_test.py      # Uplink: receives telemetry FROM boat
│   ├── mqtt_subscriber_basic_test.py     # Basic test version (no real credentials)
│   ├── esp32_simulator_real.py           # Realistic ESP32 simulator (publishes telemetry)
│   ├── esp32_simulator_basic.py          # Basic ESP32 simulator
│   └── __init__.py
│
├── config/
│   └── .env                    # Environment variables (not in Git)
│
├── tools/
│   └── cloudflared.deb         # Optional Cloudflare installer
│
├── old_scripts/                # Previous scripts (legacy)
│
├── docker-compose.yml          # InfluxDB + Grafana containers
├── requirements.txt
└── README.md
```

---

# 🚀 Running the Telemetry Pipeline

## Setup

### 1️⃣ Activate Python Virtual Environment

```bash
source ff-env/bin/activate
```

### 2️⃣ Install dependencies

```bash
pip install -r requirements.txt
```

### 3️⃣ Configure Environment Variables

Create `config/.env` with your HiveMQ credentials:

```
HIVEMQ_HOST=your-broker.hivemq.cloud
HIVEMQ_PORT=8883
HIVEMQ_USER=your_username
HIVEMQ_PASSWORD=your_password
```

---

## Testing Uplink (Boat → Server)

**Test that telemetry flows from the boat to your server.**

### Option A: Using ESP32 Simulator

Terminal 1 - Start simulator:
```bash
python src/esp32_simulator_real.py
```

Terminal 2 - Subscribe to telemetry:
```bash
python src/mqtt_subscriber_real_test.py
```

Expected output in Terminal 2:
```
Connected: 0
boat/telemetry/gps/speed -> 3.87
boat/telemetry/battery/1/voltage -> 52.4
boat/telemetry/battery/2/voltage -> 51.9
```

**What's happening:**
- The simulator publishes telemetry to HiveMQ topics
- The subscriber receives and displays that data in real-time
- Data is also visible in HiveMQ web dashboard under `boat/telemetry/#`

### Option B: Using Real ESP32

Simply run the subscriber without the simulator:
```bash
python src/mqtt_subscriber_real_test.py
```

The real ESP32 will publish telemetry, and you'll see it displayed.

---

## Testing Downlink (Server → Boat)

**Test that commands flow from your API to the boat.**

```bash
python src/downlink_listener.py
```

Expected output:
```
Connected: 0
Subscribed to boat/message/#
Waiting for commands from API...
```

**What's happening:**
- The listener subscribes to `boat/message/#` topics
- When your API publishes a command (e.g., `boat/message/power: ON`), the listener receives it
- It processes the command and forwards it to the ESP32 via serial connection

---

## Full Integration Test

Run all three in separate terminals:

Terminal 1 (Simulator):
```bash
python src/esp32_simulator_real.py
```

Terminal 2 (Uplink):
```bash
python src/mqtt_subscriber_real_test.py
```

Terminal 3 (Downlink):
```bash
python src/downlink_listener.py
```

You should see:
- Simulator publishing telemetry
- Subscriber receiving telemetry
- Listener receiving the command and forwarding to "ESP32"

---