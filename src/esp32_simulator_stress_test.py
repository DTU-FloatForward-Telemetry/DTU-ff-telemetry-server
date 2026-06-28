import os
import time
import math
import json
import random

from pathlib import Path
from dataclasses import dataclass, field
from typing import Callable, List, Any

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

# =========================================================
# ENV SETUP
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent

ENV_PATH = BASE_DIR / "config" / ".env"

load_dotenv(ENV_PATH)

BROKER = os.getenv("HIVEMQ_HOST")

PORT = int(
    os.getenv("HIVEMQ_PORT", "8883")
)

USER = os.getenv("HIVEMQ_USER")

PASSWORD = os.getenv("HIVEMQ_PASSWORD")

if not BROKER:
    raise ValueError(
        f"HIVEMQ_HOST is missing. "
        f"Check {ENV_PATH}"
    )

CLIENT_ID = (
    f"esp32_can_bridge_simulator_"
    f"{random.randint(0,9999)}"
)

# =========================================================
# RUNTIME CONFIG
# =========================================================

MQTT_QOS = 1

MQTT_RETAIN = False

PRINT_EACH_MESSAGE = False

PRINT_TASK_RUNS = False

STATS_INTERVAL_S = 10

TRACK_BANDWIDTH = True

bytes_sent_total = 0

# =========================================================
# MQTT SETUP
# =========================================================

def on_connect(
        client,
        userdata,
        flags,
        reason_code,
        properties=None
):
    print(
        f"[MQTT] Connected "
        f"with rc={reason_code}"
    )


def on_disconnect(
        client,
        userdata,
        flags,
        reason_code,
        properties=None
):
    print(
        f"[MQTT] Disconnected "
        f"with rc={reason_code}"
    )


client = mqtt.Client(
    client_id=CLIENT_ID,
    protocol=mqtt.MQTTv5,
    callback_api_version=(
        mqtt.CallbackAPIVersion.VERSION2
    )
)

# IMPORTANT:
# HiveMQ Cloud free tier is sensitive
# to inflight QoS1 floods.

client.max_inflight_messages_set(20)

client.max_queued_messages_set(0)

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

client.on_disconnect = on_disconnect

print(f"[BOOT] Loading env from: {ENV_PATH}")

print(f"[BOOT] Broker: {BROKER}:{PORT}")

print(f"[BOOT] User: {USER}")

print("[BOOT] Connecting to broker...")

client.connect(
    BROKER,
    PORT
)

client.loop_start()

# =========================================================
# STATS
# =========================================================

message_count_total = 0

message_count_window = 0

stats_last_time = time.time()

# =========================================================
# SHARED STATE
# =========================================================

@dataclass
class SimState:

    start_time: float = field(
        default_factory=time.time
    )

    lat: float = 55.4000

    lon: float = 12.3000

    altitude: float = 1.8

    speed_mps: float = 2.2

    heading_deg: float = 70.0

    roll_deg: float = 0.0

    pitch_deg: float = 0.0

    motor_rpm: float = 1100.0

    motor_power_w: float = 850.0

    motor_direction: str = "Forward"

    batt_v: List[float] = field(
        default_factory=lambda: [53.2, 53.1]
    )

    batt_i: List[float] = field(
        default_factory=lambda: [5.5, 5.7]
    )

    batt_t: List[float] = field(
        default_factory=lambda: [29.0, 29.6]
    )

    batt_soc: List[float] = field(
        default_factory=lambda: [96.2, 95.8]
    )


state = SimState()

# =========================================================
# HELPERS
# =========================================================

def clamp(
        value,
        lo,
        hi
):
    return max(
        lo,
        min(hi, value)
    )


def _record_publish(
        topic: str,
        payload: str,
        msg_info
):
    global message_count_total
    global message_count_window
    global bytes_sent_total

    message_count_total += 1

    message_count_window += 1

    if TRACK_BANDWIDTH:

        bytes_sent_total += len(
            payload.encode("utf-8")
        )

    if PRINT_EACH_MESSAGE:

        print(
            f"{time.strftime('%H:%M:%S')} "
            f"MQTT {topic} -> {payload} "
            f"| mid={msg_info.mid}"
        )


def safe_publish(
        topic: str,
        payload: str
):
    msg_info = client.publish(
        topic,
        payload,
        qos=MQTT_QOS,
        retain=MQTT_RETAIN
    )

    # IMPORTANT:
    # wait for QoS1 PUBACK
    # prevents receive maximum overflow

    msg_info.wait_for_publish()

    _record_publish(
        topic,
        payload,
        msg_info
    )


def publish_float(
        topic: str,
        value: float,
        decimals: int = 2
):
    payload = f"{value:.{decimals}f}"

    safe_publish(
        topic,
        payload
    )


def publish_int(
        topic: str,
        value: int
):
    payload = str(int(value))

    safe_publish(
        topic,
        payload
    )


def publish_string(
        topic: str,
        value: str
):
    safe_publish(
        topic,
        value
    )

# =========================================================
# BOAT PHYSICS / STATE UPDATE
# =========================================================

def update_state(
        dt: float
):
    t = (
            time.time()
            - state.start_time
    )

    target_speed = (
            2.5
            + 1.0 * math.sin(t / 25.0)
            + 0.4 * math.sin(t / 7.0)
    )

    state.speed_mps += (
            0.12
            * (
                    target_speed
                    - state.speed_mps
            )
    )

    state.speed_mps = clamp(
        state.speed_mps,
        0.0,
        6.5
    )

    state.heading_deg = (
                                state.heading_deg
                                + random.uniform(
                            -1.2,
                            1.2
                        )
                        ) % 360

# =========================================================
# MQTT PUBLISHERS
# =========================================================

def frame_batt1():

    publish_float(
        "boat/telemetry/battery/1/voltage",
        state.batt_v[0]
    )

    publish_float(
        "boat/telemetry/battery/1/current",
        state.batt_i[0]
    )

    publish_float(
        "boat/telemetry/battery/1/temperature",
        state.batt_t[0]
    )

    publish_float(
        "boat/telemetry/battery/1/soc",
        state.batt_soc[0]
    )


def frame_batt2():

    publish_float(
        "boat/telemetry/battery/2/voltage",
        state.batt_v[1]
    )

    publish_float(
        "boat/telemetry/battery/2/current",
        state.batt_i[1]
    )

    publish_float(
        "boat/telemetry/battery/2/temperature",
        state.batt_t[1]
    )

    publish_float(
        "boat/telemetry/battery/2/soc",
        state.batt_soc[1]
    )


def frame_motor():

    publish_float(
        "boat/telemetry/motor/speed",
        state.motor_rpm
    )

    publish_float(
        "boat/telemetry/motor/power",
        state.motor_power_w
    )

    publish_string(
        "boat/telemetry/motor/direction",
        state.motor_direction
    )


def frame_gps_position():

    publish_float(
        "boat/telemetry/gps/latitude",
        state.lat,
        6
    )

    publish_float(
        "boat/telemetry/gps/longitude",
        state.lon,
        6
    )


def frame_gps_speed():

    publish_float(
        "boat/telemetry/gps/speed",
        state.speed_mps
    )


def publish_imu_batch():

    samples = []

    base_t = int(
        (
                time.time()
                - state.start_time
        ) * 1000
    )

    # Reduced from 100
    # much more stable

    for i in range(20):

        sample = {

            "t": base_t + i * 10,

            "ax": round(
                random.uniform(-0.25, 0.25),
                3
            ),

            "ay": round(
                random.uniform(-0.25, 0.25),
                3
            ),

            "az": round(
                9.81
                + random.uniform(-0.12, 0.12),
                3
            ),

            "gx": round(
                random.uniform(-0.15, 0.15),
                3
            ),

            "gy": round(
                random.uniform(-0.15, 0.15),
                3
            ),

            "gz": round(
                random.uniform(-0.20, 0.20),
                3
            ),
        }

        samples.append(sample)

    payload = json.dumps({
        "count": len(samples),
        "samples": samples
    })

    safe_publish(
        "boat/telemetry/imu/batch",
        payload
    )

# =========================================================
# SCHEDULER
# =========================================================

class Task:

    def __init__(
            self,
            name: str,
            period_s: float,
            fn: Callable[[], Any],
            jitter_ratio: float = 0.05
    ):

        self.name = name

        self.period_s = period_s

        self.fn = fn

        self.jitter_ratio = jitter_ratio

        self.next_run = time.monotonic()

    def maybe_run(
            self,
            now: float
    ):

        if now >= self.next_run:

            if PRINT_TASK_RUNS:

                print(
                    f"[TASK] Running "
                    f"{self.name}"
                )

            self.fn()

            jitter = random.uniform(
                -self.jitter_ratio,
                self.jitter_ratio
            ) * self.period_s

            self.next_run = (
                    now
                    + self.period_s
                    + jitter
            )

# =========================================================
# TASKS
# =========================================================

tasks = [

    Task(
        "batt1",
        0.20,
        frame_batt1
    ),

    Task(
        "batt2",
        0.20,
        frame_batt2
    ),

    Task(
        "gps_position",
        0.10,
        frame_gps_position
    ),

    Task(
        "gps_speed",
        0.10,
        frame_gps_speed
    ),

    # aggressive but stable

    Task(
        "motor",
        0.02,
        frame_motor
    ),

    Task(
        "imu_batch",
        0.20,
        publish_imu_batch
    ),
]

# =========================================================
# MAIN LOOP
# =========================================================

def maybe_print_stats():

    global stats_last_time
    global message_count_window
    global bytes_sent_total

    now = time.time()

    elapsed = (
            now
            - stats_last_time
    )

    if elapsed >= STATS_INTERVAL_S:

        rate = (
            message_count_window
            / elapsed
            if elapsed > 0
            else 0.0
        )

        bandwidth_mbps = (
                (
                        bytes_sent_total * 8
                )
                / elapsed
                / 1_000_000
        )

        bandwidth_kbps = (
                bandwidth_mbps * 1000
        )

        print(
            f"[STATS] "
            f"total_messages="
            f"{message_count_total} "
            f"| window_messages="
            f"{message_count_window} "
            f"| avg_rate="
            f"{rate:.2f} msg/s "
            f"| bandwidth="
            f"{bandwidth_kbps:.2f} kbps "
            f"({bandwidth_mbps:.4f} Mbps)"
        )

        stats_last_time = now

        message_count_window = 0

        bytes_sent_total = 0


print(
    "[BOOT] ESP32-like stress "
    "simulator started"
)

last_time = time.monotonic()

try:

    while True:

        now = time.monotonic()

        dt = now - last_time

        last_time = now

        update_state(dt)

        for task in tasks:

            task.maybe_run(now)

        maybe_print_stats()

        time.sleep(0.01)

except KeyboardInterrupt:

    print(
        "[BOOT] Stopping simulator..."
    )

finally:

    client.loop_stop()

    client.disconnect()

    print(
        "[BOOT] Simulator stopped"
    )