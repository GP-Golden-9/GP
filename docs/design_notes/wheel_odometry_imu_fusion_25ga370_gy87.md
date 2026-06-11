# Wheel Odometry + IMU Fusion Guide: 25GA370 Encoder Motors + GY-87 IMU

**Hardware:** 4× Slamtec 25GA370 DC Gear Motor with Encoder (170 RPM, 12V) | IMU: GY-87 (MPU6050 + HMC5883L + BMP180)  
**Stack:** ROS / ROS2 — Differential Drive / Mecanum Drive

---

## Executive Summary

Accurate odometry on a wheeled robot requires fusing wheel encoder data with IMU measurements through an Extended Kalman Filter (EKF). The 25GA370 motors provide 408 encoder counts per revolution (12 PPR × 34 gear ratio), giving good positional resolution. The GY-87's MPU6050 provides gyroscope and accelerometer data, while the HMC5883L adds magnetometer-based heading. Individually, each source drifts over time; fused via `robot_localization`, they produce stable, long-duration odometry. This document covers the math, code, common failures, and community-reported fixes.

---

## 1. Hardware Specifications

### 1.1 25GA370 Encoder Motor

| Parameter | Value |
|---|---|
| Voltage | 12V DC |
| Speed (no load) | 170 RPM |
| Gear Ratio | 1:34 |
| Raw Encoder PPR | 12 PPR |
| **Effective Encoder CPR (after gearbox)** | **408 counts/rev** (12 × 34) |
| Encoder Type | Quadrature Hall Effect (2 channels: A & B) |
| Quadrature Decoded CPR | 1,632 counts/rev (408 × 4) |

With quadrature decoding, a 10 cm wheel gives a linear resolution of approximately **0.19 mm per tick** — more than sufficient for indoor navigation.[cite:109][cite:118]

### 1.2 GY-87 IMU

| Chip | Function | Key Specs |
|---|---|---|
| MPU6050 | 3-axis gyro + 3-axis accel | ±250–2000 °/s gyro; ±2–16g accel; I2C |
| HMC5883L | 3-axis magnetometer | ±8 Gauss; 0.73–4.35 mGauss/LSB |
| BMP180 | Barometric pressure | ±1 hPa accuracy |

The HMC5883L is connected through MPU6050's auxiliary I2C bus, requiring a special bypass mode to be enabled in firmware.[cite:104]

---

## 2. Odometry Mathematics

### 2.1 Differential Drive Kinematics

For a differential-drive or skid-steer 4-wheel robot, the standard kinematic model uses only the two driven sides (left average and right average encoder ticks):

```
ΔS_left  = (ticks_left  / CPR) × π × wheel_diameter
ΔS_right = (ticks_right / CPR) × π × wheel_diameter

ΔS       = (ΔS_left + ΔS_right) / 2         # linear displacement
Δθ       = (ΔS_right - ΔS_left) / wheelbase  # angular change

x_new    = x + ΔS × cos(θ + Δθ/2)
y_new    = y + ΔS × sin(θ + Δθ/2)
θ_new    = θ + Δθ
```

**Critical parameters to measure accurately:**
- `wheel_diameter` (meters) — measure physically, do not rely on datasheet
- `wheelbase` (meters) — distance between left and right wheel contact points
- `CPR` — 1,632 for 25GA370 with quadrature decoding[cite:109][cite:118]

### 2.2 Error Sources in Encoder Odometry

These are the three dominant error sources documented across the robotics community[cite:119][cite:122]:

| Error Type | Cause | Effect |
|---|---|---|
| **Drift Error** | Different effective wheel diameters | Constant angular drift even in straight lines |
| **Scale Error** | Wrong wheel diameter or CPR value | Wrong distance estimation |
| **Wheelbase Error** | Incorrect `L` parameter | Turns are off by a constant factor |

Over long distances, angular drift dominates and causes the robot's heading to diverge significantly from reality. This is why IMU fusion is essential.[cite:119]

---

## 3. System Architecture

The recommended architecture layers sensors as follows:

```
┌─────────────────────────────────────────────────────┐
│                  robot_localization                  │
│          Extended Kalman Filter (EKF)                │
│  Inputs:  /odom (encoders)  +  /imu/data (GY-87)    │
│  Output:  /odometry/filtered  →  odom→base_link TF  │
└─────────────────────────────────────────────────────┘
           ↑                          ↑
┌──────────────────┐        ┌─────────────────────┐
│  Arduino / STM32  │        │  ROS IMU Driver     │
│  Encoder counter  │        │  (mpu6050_serial or │
│  → /odom topic    │        │   ros2_mpu6050)     │
└──────────────────┘        └─────────────────────┘
           ↑                          ↑
    4× 25GA370                    GY-87 IMU
  encoder motors                (MPU6050 + HMC5883L)
```

The Arduino/microcontroller handles real-time encoder counting and publishes raw `nav_msgs/Odometry`. The IMU driver publishes `sensor_msgs/Imu`. The `robot_localization` EKF node fuses both into a single filtered odometry output.[cite:88][cite:91]

---

## 4. Step-by-Step Implementation

### 4.1 Arduino Firmware (Encoder → /odom)

Wire each motor's encoder A/B channels to Arduino interrupt pins. For 4 motors, use pins D2, D3, D18, D19 (Mega) for hardware interrupts.

```cpp
#include <ros.h>
#include <nav_msgs/Odometry.h>
#include <geometry_msgs/TransformStamped.h>

// === PARAMETERS — MEASURE THESE PHYSICALLY ===
const float WHEEL_DIAMETER = 0.065;    // meters — measure your actual wheel
const float WHEELBASE      = 0.180;    // meters — left to right contact points
const int   CPR            = 1632;     // 12 PPR × 34 gear ratio × 4 (quadrature)

volatile long enc_left  = 0;
volatile long enc_right = 0;

void IRAM_ATTR encoderLeftA()  { enc_left  += (digitalRead(ENC_L_B) == LOW) ? 1 : -1; }
void IRAM_ATTR encoderRightA() { enc_right += (digitalRead(ENC_R_B) == LOW) ? 1 : -1; }

// In loop(): compute ΔS, Δθ, update x, y, θ, publish to /odom
```

**Key firmware rules:**
- Use hardware interrupts (not polling) for encoder A channels
- Read B channel inside the ISR to determine direction
- Keep the ISR as short as possible — only increment/decrement counter
- Publish `/odom` at 20–50 Hz minimum

### 4.2 GY-87 IMU Driver Setup

The GY-87's HMC5883L is on the MPU6050 auxiliary I2C bus. To access it from the master (Arduino/RPi), enable bypass mode[cite:104]:

```cpp
// Arduino: Enable MPU6050 I2C bypass so HMC5883L is visible on main I2C bus
accelgyro.initialize();
accelgyro.setI2CBypassEnabled(true);  // CRITICAL — without this, HMC5883L is invisible
// Now initialize HMC5883L separately on the same I2C bus
```

For ROS2, use the `ros2_mpu6050` package and run calibration before deployment[cite:114]:

```bash
# Install
sudo apt install ros-humble-imu-tools

# Run calibration (robot must be perfectly stationary and level)
ros2 run ros2_mpu6050 ros2_mpu6050_calibrate

# Apply offsets in params.yaml:
# gyro_x_offset: <value from calibration>
# gyro_y_offset: <value>
# gyro_z_offset: <value>
# accel_x_offset: <value>
# accel_y_offset: <value>
# accel_z_offset: <value>
```

### 4.3 robot_localization EKF Configuration

Install and configure[cite:91][cite:93]:

```bash
sudo apt install ros-$ROS_DISTRO-robot-localization
```

**`ekf.yaml` — Tuned for 25GA370 + GY-87:**

```yaml
frequency: 30           # Filter update rate (Hz)
sensor_timeout: 0.1
two_d_mode: true        # Ground robot — disable Z axis

odom_frame: odom
base_link_frame: base_link
world_frame: odom

# --- Encoder Odometry ---
odom0: /odom
odom0_config: [true,  true,  false,   # x, y, z position
               false, false, true,    # roll, pitch, yaw
               true,  true,  false,   # vx, vy, vz
               false, false, true,    # vroll, vpitch, vyaw
               false, false, false]   # ax, ay, az
odom0_differential: false
odom0_relative: false
odom0_queue_size: 10

# --- IMU (MPU6050) ---
imu0: /imu/data
imu0_config: [false, false, false,   # x, y, z position (IMU doesn't give position)
              false, false, true,    # roll, pitch, YAW — fuse heading
              false, false, false,   # vx, vy, vz
              true,  true,  true,    # angular velocity (all 3 axes)
              true,  true,  false]   # linear acceleration (ax, ay only for ground robot)
imu0_differential: false
imu0_relative: true     # Use relative heading changes, not absolute (avoids mag issues)
imu0_remove_gravitational_acceleration: true
imu0_queue_size: 10

# Process noise covariance — tune these based on your robot's behavior
process_noise_covariance: [0.05, 0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,
                           0,    0.05, 0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,
                           0,    0,    0.06, 0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,
                           0,    0,    0,    0.03, 0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,
                           0,    0,    0,    0,    0.03, 0,    0,    0,    0,    0,    0,    0,    0,    0,    0,
                           0,    0,    0,    0,    0,    0.06, 0,    0,    0,    0,    0,    0,    0,    0,    0,
                           0,    0,    0,    0,    0,    0,    0.025,0,    0,    0,    0,    0,    0,    0,    0,
                           0,    0,    0,    0,    0,    0,    0,    0.025,0,    0,    0,    0,    0,    0,    0,
                           0,    0,    0,    0,    0,    0,    0,    0,    0.04, 0,    0,    0,    0,    0,    0,
                           0,    0,    0,    0,    0,    0,    0,    0,    0,    0.01, 0,    0,    0,    0,    0,
                           0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0.01, 0,    0,    0,    0,
                           0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0.02, 0,    0,    0,
                           0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0.01, 0,    0,
                           0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0.01, 0,
                           0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0.015]
```

### 4.4 Launch File (ROS2)

```python
# odometry_fusion.launch.py
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        # Static TF: robot body to IMU
        Node(package='tf2_ros', executable='static_transform_publisher',
             arguments=['0', '0', '0.05', '0', '0', '0', 'base_link', 'imu_link']),

        # Static TF: robot body to wheel base
        Node(package='tf2_ros', executable='static_transform_publisher',
             arguments=['0', '0', '0', '0', '0', '0', 'base_link', 'base_footprint']),

        # EKF Node
        Node(package='robot_localization', executable='ekf_node',
             name='ekf_filter_node',
             parameters=['/path/to/ekf.yaml'],
             remappings=[('odometry/filtered', '/odom/filtered')]),
    ])
```

---

## 5. Common Problems & Community-Reported Solutions

### 5.1 Robot Drifts in Straight Lines

**Cause:** Unequal effective wheel diameters — even 0.5mm difference between two wheels causes constant angular drift[cite:119][cite:122].

**Fix:**
1. Drive the robot exactly 2 meters in a straight line
2. Measure the actual distance traveled by each side
3. Adjust `wheel_diameter` per motor in firmware:
   ```
   wheel_diameter_left  = measured_distance_left  / (encoder_ticks_left / CPR)  / π
   wheel_diameter_right = measured_distance_right / (encoder_ticks_right / CPR) / π
   ```
4. If using the same value for both sides, use the average of the two measurements

### 5.2 Turns Are Off by a Constant Factor

**Cause:** `wheelbase` parameter is incorrect[cite:110][cite:116].

**Fix:**
1. Command the robot to rotate exactly 360° in place
2. Measure actual rotation with a compass or protractor
3. Adjust wheelbase: `L_corrected = L_nominal × (360 / actual_degrees)`
4. Repeat until 360° command = 360° actual rotation

### 5.3 MPU6050 Gyro Drift (Yaw Keeps Changing When Robot is Still)

**Cause:** Gyro bias not calibrated[cite:99][cite:111][cite:123].

**Fix — Collect static offsets at startup:**
```cpp
// Average 500 readings while robot is perfectly still
long sumGx = 0, sumGy = 0, sumGz = 0;
for (int i = 0; i < 500; i++) {
    sumGx += mpu.getRotationX();
    sumGy += mpu.getRotationY();
    sumGz += mpu.getRotationZ();
    delay(5);
}
gyro_offset_x = sumGx / 500;
gyro_offset_y = sumGy / 500;
gyro_offset_z = sumGz / 500;
// Subtract these offsets from every subsequent reading
```
The community also recommends waiting **40 seconds** after startup before trusting yaw data, as the MPU6050 DMP requires this warm-up time to stabilize[cite:123].

### 5.4 HMC5883L Not Detected on I2C Bus

**Cause:** The HMC5883L is on MPU6050's auxiliary I2C bus, not the main bus[cite:104].

**Fix:** Enable I2C bypass mode before initializing HMC5883L:
```cpp
accelgyro.setI2CBypassEnabled(true);
```
Without this line, `i2c_scan` will never show the HMC5883L even though it is physically present.

### 5.5 robot_localization Produces Oscillating / Jumpy Pose

**Cause:** Incorrect `differential` setting, or fusing absolute orientation (yaw) from both odom and IMU[cite:97][cite:100].

**Fix:**
- Set `imu0_relative: true` so only **changes** in heading are fused, not absolute values
- Never set massive covariance values for variables you want to ignore — use the boolean config vector to disable them instead[cite:97]
- Start with just odom EKF, verify it looks correct, then add IMU

### 5.6 Magnetic Field Declination Causing Wrong Heading

**Cause:** If `magnetic_declination` is set in `ekf.yaml` with a wrong value, heading rotates incorrectly[cite:105].

**Fix:**
```yaml
# In ekf.yaml — disable magnetic declination for indoor robots
magnetic_declination_radians: 0.0
```
Indoor environments have strong magnetic interference from motors, wiring, and metal structures — the magnetometer heading is not reliable indoors. **For indoor robots, fuse only gyroscope angular velocity, not magnetometer absolute heading.**

### 5.7 Encoder Counts Skipped Under Load

**Cause:** ISR (interrupt service routine) takes too long, or encoder A/B signals are connected to non-interrupt pins[cite:86].

**Fix:**
- Always connect encoder A channel to hardware interrupt pins (D2, D3 on Uno; D2, D3, D18, D19, D20, D21 on Mega)
- Use minimal ISR code (single increment/decrement)
- Add 100nF capacitor on each encoder signal line to debounce

### 5.8 Odometry Jumps When IMU Covariance is Wrong

**Cause:** Publishing `covariance[0] = -1` (means "sensor does not measure this") or wrong covariance values causes EKF to over-trust or under-trust the sensor[cite:97][cite:108].

**Fix:**
- Set realistic covariance values in your `Imu` and `Odometry` messages
- For MPU6050 gyro: `angular_velocity_covariance = 0.02` per axis is a safe starting point
- For encoder odom: `pose_covariance = 0.01` for x/y, `0.03` for yaw

---

## 6. Calibration Procedures

### 6.1 Wheel Geometry Calibration

Run this 3-step procedure before any navigation test[cite:116][cite:110]:

1. **Distance test:** Drive 2m forward, measure actual distance → calibrate `wheel_diameter`
2. **Rotation test:** Rotate 360°, measure actual angle → calibrate `wheelbase`
3. **Repeatability test:** Drive a 1m × 1m square, check return to origin

Accept less than 2 cm position error and less than 2° heading error after a 4m square path.

### 6.2 MPU6050 Calibration

Run with robot perfectly stationary and level for 2–3 minutes[cite:99][cite:101][cite:120]:

```bash
# ROS2
ros2 run ros2_mpu6050 ros2_mpu6050_calibrate

# ROS1
roslaunch mpu6050_driver mpu6050_calibration.launch
```

Save the output offsets permanently in `params.yaml`. Re-run calibration every time the sensor is physically repositioned on the robot.

### 6.3 EKF Covariance Tuning

Use this systematic approach[cite:97][cite:100]:

1. Run only encoder odometry (no IMU) and verify the EKF output tracks it correctly
2. Add IMU angular velocity only — check that heading is smoother
3. Add IMU linear acceleration — monitor for oscillation
4. If oscillation appears, increase the corresponding process noise covariance values

---

## 7. Complete Topic & TF Tree Reference

```
Published topics:
  /odom              → raw encoder odometry     (nav_msgs/Odometry)
  /imu/data          → raw IMU data             (sensor_msgs/Imu)
  /odometry/filtered → EKF-fused output         (nav_msgs/Odometry)

TF Tree:
  map (if SLAM used)
   └── odom
        └── base_link  ← published by EKF node
             ├── imu_link    (static TF)
             └── base_footprint (static TF)

Required for SLAM (if added later):
  /scan → from RPLIDAR A1M8
  SLAM node subscribes to /odometry/filtered as its odom source
```

---

## 8. Community Experience Summary

| Problem Reported | Root Cause | Solution Applied | Outcome |
|---|---|---|---|
| Robot curves left on straight path | Left/right wheel diameter mismatch | Per-wheel diameter calibration | Drift reduced to < 1° over 5m[cite:119] |
| Yaw drifts 20° while stationary | MPU6050 gyro bias not subtracted | 500-sample startup calibration | Drift eliminated[cite:111][cite:99] |
| HMC5883L never found on I2C | Aux I2C bypass not enabled | `setI2CBypassEnabled(true)` | Magnetometer accessible[cite:104] |
| EKF output jumps on turns | Fusing absolute yaw from IMU + odom | Set `imu0_relative: true` | Smooth heading fusion[cite:97][cite:100] |
| Encoder counts lost at high speed | A channel on non-interrupt pin | Moved to hardware interrupt pins | Zero missed counts[cite:86] |
| Wrong heading indoors | Magnetic declination parameter wrong | Set `magnetic_declination: 0.0` | Correct heading restored[cite:105] |
| EKF diverges after 30 seconds | Covariance values too small (over-trust IMU) | Increased process noise covariance | Filter stable for 10+ minute runs[cite:97] |

---

## 9. Conclusion

The 25GA370's 408 CPR (1,632 with quadrature decoding) gives sub-millimeter resolution that is sufficient for indoor navigation. The primary challenge is not sensor resolution but systematic errors: wheel diameter mismatch, gyro bias, and incorrect EKF configuration. Following the calibration procedures in Section 6 and the EKF configuration in Section 4.3 — especially setting `imu0_relative: true` and disabling the magnetometer for indoor use — produces stable odometry suitable for SLAM and autonomous navigation. Adding the RPLIDAR A1M8 as a third input to the EKF (via rf2o or direct scan matching) will further improve long-term consistency.
