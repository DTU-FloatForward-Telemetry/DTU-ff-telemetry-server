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

CLIENT_ID = "esp32_can_bridge_simulator"

# =========================================================
# RUNTIME CONFIG
# =========================================================

MQTT_QOS = 0

MQTT_RETAIN = False

PRINT_EACH_MESSAGE = False

PRINT_TASK_RUNS = False

STATS_INTERVAL_S = 10


# =========================================================
# MQTT SETUP
# =========================================================

def on_connect(
        client,
        userdata,
        flags,
        rc,
        properties=None
):
    print(f"[MQTT] Connected with rc={rc}")


def on_disconnect(
        client,
        userdata,
        rc,
        properties=None
):
    print(f"[MQTT] Disconnected with rc={rc}")


client = mqtt.Client(
    client_id=CLIENT_ID,
    protocol=mqtt.MQTTv5
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

    accel_x: float = 0.0

    accel_y: float = 0.0

    accel_z: float = 9.81

    gyro_x: float = 0.0

    gyro_y: float = 0.0

    gyro_z: float = 0.0

    motor_rpm: float = 1100.0

    motor_power_w: float = 850.0

    motor_direction: str = "Forward"

    dht_temp: float = 22.0

    fix_type: int = 3

    satellites: int = 12

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

    batt_power: List[float] = field(
        default_factory=lambda: [0.0, 0.0]
    )

    batt_boardtemp: List[float] = field(
        default_factory=lambda: [28.0, 28.5]
    )

    batt_totenergy: List[float] = field(
        default_factory=lambda: [500.0, 500.0]
    )

    batt_status: List[str] = field(
        default_factory=lambda: ["discharging", "discharging"]
    )

    batt_loaddetect: List[str] = field(
        default_factory=lambda: ["connected", "connected"]
    )

    motor_valid: int = 1

    motor_enabled: int = 1

    motor_voltage_dc: float = 52.0

    motor_current: float = 15.0

    motor_torque: float = 12.0

    motor_temp_motor: float = 35.0

    motor_temp_inverter: float = 40.0

    dht_hum: float = 55.0

    thrust_loadcell_n: float = 0.0

    thrust_propeller_n: float = 0.0

    rotary_angle_deg: float = 0.0

    lv_voltage: float = 12.8


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
        info
):
    global message_count_total
    global message_count_window

    message_count_total += 1

    message_count_window += 1

    if PRINT_EACH_MESSAGE:
        print(
            f"{time.strftime('%H:%M:%S')} "
            f"MQTT {topic} -> {payload} "
            f"| rc={info.rc} "
            f"| qos={MQTT_QOS} "
            f"| retain={MQTT_RETAIN}"
        )


def publish_float(
        topic: str,
        value: float,
        decimals: int = 2
):
    payload = f"{value:.{decimals}f}"

    info = client.publish(
        topic,
        payload,
        qos=MQTT_QOS,
        retain=MQTT_RETAIN
    )

    _record_publish(
        topic,
        payload,
        info
    )


def publish_int(
        topic: str,
        value: int
):
    payload = str(int(value))

    info = client.publish(
        topic,
        payload,
        qos=MQTT_QOS,
        retain=MQTT_RETAIN
    )

    _record_publish(
        topic,
        payload,
        info
    )


def publish_string(
        topic: str,
        value: str
):
    info = client.publish(
        topic,
        value,
        qos=MQTT_QOS,
        retain=MQTT_RETAIN
    )

    _record_publish(
        topic,
        value,
        info
    )


# =========================================================
# BOAT PHYSICS / STATE UPDATE
# =========================================================

def update_state(
        dt: float
):
    t = time.time() - state.start_time

    target_speed = (
            2.5
            + 1.0 * math.sin(t / 25.0)
            + 0.4 * math.sin(t / 7.0)
    )

    state.speed_mps += (
            0.12
            * (target_speed - state.speed_mps)
    )

    state.speed_mps = clamp(
        state.speed_mps,
        0.0,
        6.5
    )

    state.heading_deg = (
                                state.heading_deg
                                + random.uniform(-1.2, 1.2)
                        ) % 360

    state.roll_deg = clamp(
        4.0 * math.sin(t / 4.0)
        + random.uniform(-0.3, 0.3),
        -10.0,
        10.0,
    )

    state.pitch_deg = clamp(
        2.0 * math.sin(t / 6.0)
        + random.uniform(-0.2, 0.2),
        -5.0,
        5.0,
    )

    distance = state.speed_mps * dt

    heading_rad = math.radians(
        state.heading_deg
    )

    d_north = (
            distance
            * math.cos(heading_rad)
    )

    d_east = (
            distance
            * math.sin(heading_rad)
    )

    state.lat += (
            d_north / 111_320.0
    )

    state.lon += (
            d_east
            / (
                    111_320.0
                    * math.cos(
                math.radians(state.lat)
            )
            )
    )

    state.altitude = clamp(
        1.8
        + 0.2 * math.sin(t / 20.0)
        + random.uniform(-0.05, 0.05),
        0.5,
        3.0,
    )

    state.fix_type = 3

    state.satellites = random.randint(
        10,
        16
    )

    state.accel_x = random.uniform(
        -0.25,
        0.25
    )

    state.accel_y = random.uniform(
        -0.25,
        0.25
    )

    state.accel_z = (
            9.81
            + random.uniform(-0.12, 0.12)
    )

    state.gyro_x = random.uniform(
        -0.15,
        0.15
    )

    state.gyro_y = random.uniform(
        -0.15,
        0.15
    )

    state.gyro_z = random.uniform(
        -0.20,
        0.20
    )

    target_rpm = (
            850
            + state.speed_mps * 170
    )

    state.motor_rpm += (
            0.18
            * (target_rpm - state.motor_rpm)
    )

    state.motor_rpm = clamp(
        state.motor_rpm,
        700,
        2200
    )

    target_power = (
            250
            + state.speed_mps * 300
            + random.uniform(-20, 20)
    )

    state.motor_power_w += (
            0.20
            * (target_power - state.motor_power_w)
    )

    state.motor_power_w = clamp(
        state.motor_power_w,
        150,
        2500
    )

    state.motor_direction = (
        "Forward"
        if state.speed_mps > 0.2
        else "Neutral"
    )

    state.dht_temp = clamp(
        state.dht_temp + random.uniform(-0.08, 0.08),
        18.0, 32.0
    )

    state.dht_hum = clamp(
        state.dht_hum + random.uniform(-0.1, 0.1),
        30.0, 90.0
    )

    state.motor_valid = 1
    state.motor_enabled = 1 if state.speed_mps > 0.1 else 0

    state.motor_voltage_dc = clamp(
        state.motor_voltage_dc + random.uniform(-0.1, 0.1),
        48.0, 54.6
    )

    state.motor_current = clamp(
        state.motor_power_w / max(state.motor_voltage_dc, 1.0),
        0.0, 50.0
    )

    state.motor_torque = clamp(
        state.motor_power_w / max(state.motor_rpm * 2 * math.pi / 60, 1.0),
        0.0, 30.0
    )

    state.motor_temp_motor = clamp(
        state.motor_temp_motor + 0.01 * (state.motor_power_w / 500.0 - 0.5),
        25.0, 80.0
    )

    state.motor_temp_inverter = clamp(
        state.motor_temp_inverter + 0.01 * (state.motor_power_w / 400.0 - 0.5),
        25.0, 85.0
    )

    state.thrust_loadcell_n = clamp(
        state.motor_power_w * 0.012 + random.uniform(-0.5, 0.5),
        0.0, 40.0
    )

    state.thrust_propeller_n = clamp(
        state.thrust_loadcell_n * 0.95 + random.uniform(-0.3, 0.3),
        0.0, 40.0
    )

    state.rotary_angle_deg = (
        state.rotary_angle_deg + random.uniform(-0.5, 0.5)
    ) % 360.0

    for i in range(2):
        discharge = (
                (state.motor_power_w / 2500.0)
                * 0.0025
                * dt
        )

        state.batt_soc[i] = clamp(
            state.batt_soc[i] - discharge,
            0.0,
            100.0
        )

        current_target = (
                3.5
                + state.motor_power_w / 400.0
                + random.uniform(-0.3, 0.3)
        )

        state.batt_i[i] += (
                0.20
                * (
                        current_target
                        - state.batt_i[i]
                )
        )

        state.batt_i[i] = clamp(
            state.batt_i[i],
            0.0,
            20.0
        )

        voltage_target = (
                49.5
                + 0.04 * state.batt_soc[i]
                - 0.05 * state.batt_i[i]
        )

        state.batt_v[i] += (
                0.20
                * (
                        voltage_target
                        - state.batt_v[i]
                )
        )

        state.batt_v[i] = clamp(
            state.batt_v[i],
            48.0,
            54.6
        )

        temp_target = (
                25.0
                + 0.6 * state.batt_i[i]
        )

        state.batt_t[i] += (
                0.08
                * (
                        temp_target
                        - state.batt_t[i]
                )
        )

        state.batt_t[i] = clamp(
            state.batt_t[i],
            20.0,
            45.0
        )

        state.batt_power[i] = round(
            state.batt_v[i] * state.batt_i[i], 2
        )

        state.batt_boardtemp[i] = clamp(
            state.batt_boardtemp[i] + random.uniform(-0.05, 0.05),
            20.0, 50.0
        )

        state.batt_totenergy[i] = clamp(
            state.batt_totenergy[i] - state.batt_power[i] * dt / 3600.0,
            0.0, 1000.0
        )

        state.batt_status[i] = "discharging" if state.batt_i[i] > 0.5 else "stationary"
        state.batt_loaddetect[i] = "connected"


# =========================================================
# MQTT PUBLISHERS
# =========================================================

def frame_batt1():
    publish_float("boat/telemetry/battery/1/voltage",     state.batt_v[0], 2)
    publish_float("boat/telemetry/battery/1/current",     state.batt_i[0], 2)
    publish_float("boat/telemetry/battery/1/temperature", state.batt_t[0], 2)
    publish_float("boat/telemetry/battery/1/soc",         state.batt_soc[0], 2)
    publish_float("boat/telemetry/battery/1/power",       state.batt_power[0], 2)
    publish_float("boat/telemetry/battery/1/boardtemp",   state.batt_boardtemp[0], 2)
    publish_float("boat/telemetry/battery/1/totenergy",   state.batt_totenergy[0], 2)
    publish_string("boat/telemetry/battery/1/status",     state.batt_status[0])
    publish_string("boat/telemetry/battery/1/loaddetect", state.batt_loaddetect[0])


def frame_batt2():
    publish_float("boat/telemetry/battery/2/voltage",     state.batt_v[1], 2)
    publish_float("boat/telemetry/battery/2/current",     state.batt_i[1], 2)
    publish_float("boat/telemetry/battery/2/temperature", state.batt_t[1], 2)
    publish_float("boat/telemetry/battery/2/soc",         state.batt_soc[1], 2)
    publish_float("boat/telemetry/battery/2/power",       state.batt_power[1], 2)
    publish_float("boat/telemetry/battery/2/boardtemp",   state.batt_boardtemp[1], 2)
    publish_float("boat/telemetry/battery/2/totenergy",   state.batt_totenergy[1], 2)
    publish_string("boat/telemetry/battery/2/status",     state.batt_status[1])
    publish_string("boat/telemetry/battery/2/loaddetect", state.batt_loaddetect[1])


def frame_lv_battery():
    publish_float("boat/telemetry/battery/3/voltage", state.lv_voltage, 2)


def frame_gps_status():
    publish_int(
        "boat/telemetry/gps/status",
        state.fix_type
    )

    publish_int(
        "boat/telemetry/gps/Nsatellites",
        state.satellites
    )

    publish_int(
        "boat/telemetry/gps/valid",
        1
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


def frame_gps_attitude():
    publish_float(
        "boat/telemetry/gps/roll",
        state.roll_deg,
        2
    )

    publish_float(
        "boat/telemetry/gps/pitch",
        state.pitch_deg,
        2
    )

    publish_float(
        "boat/telemetry/gps/heading",
        state.heading_deg,
        2
    )


def frame_gps_speed():
    publish_float(
        "boat/telemetry/gps/speed",
        state.speed_mps,
        2
    )


def frame_gps_altitude():
    publish_float(
        "boat/telemetry/gps/altitude",
        state.altitude,
        2
    )


def frame_motor():
    publish_float("boat/telemetry/motor/speed",        state.motor_rpm, 2)
    publish_float("boat/telemetry/motor/power",        state.motor_power_w, 2)
    publish_float("boat/telemetry/motor/voltage_dc",   state.motor_voltage_dc, 2)
    publish_float("boat/telemetry/motor/current",      state.motor_current, 2)
    publish_float("boat/telemetry/motor/torque",       state.motor_torque, 2)
    publish_float("boat/telemetry/motor/temp_motor",   state.motor_temp_motor, 2)
    publish_float("boat/telemetry/motor/temp_inverter",state.motor_temp_inverter, 2)
    publish_string("boat/telemetry/motor/direction",   state.motor_direction)
    publish_int("boat/telemetry/motor/valid",          state.motor_valid)
    publish_int("boat/telemetry/motor/enabled",        state.motor_enabled)


def frame_dht():
    publish_float("boat/telemetry/dht/temp", state.dht_temp, 2)
    publish_float("boat/telemetry/dht/hum",  state.dht_hum, 2)


def frame_thrust():
    publish_float("boat/telemetry/thrust/loadcell_n",  state.thrust_loadcell_n, 3)
    publish_float("boat/telemetry/thrust/propeller_n", state.thrust_propeller_n, 3)


def frame_rotary():
    publish_float("boat/telemetry/rotary/angle_deg", state.rotary_angle_deg, 2)


def publish_imu_batch():
    samples = []

    base_t = int(
        (
                time.time()
                - state.start_time
        ) * 1000
    )

    for i in range(100):
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

    info = client.publish(
        "boat/telemetry/imu/batch",
        payload,
        qos=MQTT_QOS,
        retain=MQTT_RETAIN
    )

    _record_publish(
        "boat/telemetry/imu/batch",
        f"IMU batch ({len(samples)} samples)",
        info
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


tasks = [

    Task("batt1", 0.20, frame_batt1),

    Task("batt2", 0.20, frame_batt2),

    Task("lv_batt", 1.00, frame_lv_battery),

    Task("gps_status", 1.00, frame_gps_status),

    Task("gps_position", 0.20, frame_gps_position),

    Task("gps_altitude", 1.00, frame_gps_altitude),

    Task("gps_attitude", 0.10, frame_gps_attitude),

    Task("gps_speed", 0.20, frame_gps_speed),

    Task("motor",    0.10, frame_motor),

    Task("dht",      1.00, frame_dht),

    Task("thrust",   0.10, frame_thrust),

    Task("rotary",   0.10, frame_rotary),

    Task("imu_batch", 1.00, publish_imu_batch),
]


# =========================================================
# MAIN LOOP
# =========================================================

def maybe_print_stats():
    global stats_last_time
    global message_count_window

    now = time.time()

    elapsed = now - stats_last_time

    if elapsed >= STATS_INTERVAL_S:
        rate = (
            message_count_window / elapsed
            if elapsed > 0
            else 0.0
        )

        print(
            f"[STATS] "
            f"total_messages={message_count_total} "
            f"| last_window_messages="
            f"{message_count_window} "
            f"| avg_rate={rate:.2f} msg/s"
        )

        stats_last_time = now

        message_count_window = 0


print(
    "[BOOT] ESP32-like simulator started"
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
