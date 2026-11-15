#!/usr/bin/env python3
"""
SOLUTION.PY — MÃ NGUỒN MẪU BÀI THI VÒNG 1 (AI DRONE CHALLENGE FA26)
Hành trình: Bay quét vùng thi 100m x 100m theo hình Zíc-zắc (Lawnmower),
tích hợp gửi báo cáo nạn nhân chuẩn cho hệ thống chấm tự động.
"""
import math
import time
import sys
import json
from pymavlink import mavutil
from victim_report import report_person

# --- CẤU HÌNH THAM SỐ BAY (SINH VIÊN CÓ THỂ ĐIỀU CHỈNH) ---
ALTITUDE = 12.0       # Độ cao bay quét (Hành lang an toàn: 8m <= H <= 20m)
SPEED = 3.5          # Vận tốc bay m/s (Khuyến nghị 3.0 - 4.5 m/s)
SURVEY_SIZE = 100.0   # Kích thước vùng thi 100m x 100m
LANE_SPACING = 20.0   # Khoảng cách giữa các làn bay (m)


MIN_CONFIDENCE = 0.35
DEDUP_RADIUS_M = 6.0


class PersonReporter:
    """Optional ROS2 baseline for the downward camera (yaw commanded to zero).

    Report coordinates are PX4 local NED metres; sim_s uses MAVLink boot time.
    Without ROS2 the waypoint mission continues, but produces no AI reports.
    """
    def __init__(self):
        self.node = None
        self.context = None
        self.executor = None
        self.position = None
        self.reported = []
        self.camera = {}
        try:
            with open('/opt/kit/camera.json') as stream:
                self.camera = json.load(stream)
        except (OSError, ValueError):
            pass
        try:
            import rclpy
            from rclpy.context import Context
            from rclpy.executors import SingleThreadedExecutor
            from rclpy.qos import qos_profile_sensor_data
            from vision_msgs.msg import Detection2DArray
            self.ros = rclpy
            self.context = Context()
            rclpy.init(context=self.context)
            self.node = rclpy.create_node('solution_person_reporter', context=self.context)
            self.executor = SingleThreadedExecutor(context=self.context)
            self.executor.add_node(self.node)
            self.node.create_subscription(Detection2DArray, '/yolo_detect/detections',
                                          self.on_detections, qos_profile_sensor_data)
            print('[AI] ROS2 person baseline ready')
        except Exception as exc:
            print(f'[AI] ROS2 unavailable; continuing flight without reports: {exc}')
            self.close()

    def update_position(self, msg):
        values = (msg.x, msg.y, -msg.z, msg.time_boot_ms / 1000.0)
        if all(math.isfinite(v) for v in values):
            self.position = (*values, time.monotonic())

    def on_detections(self, msg):
        if self.position is None or time.monotonic() - self.position[4] > 1.0:
            return
        north, east, height, sim_s, _ = self.position
        if height < 2.0:
            return
        for detection in msg.detections:
            scores = [float(r.hypothesis.score) for r in detection.results
                      if str(r.hypothesis.class_id).lower() in ('person', '0')]
            confidence = max(scores, default=0.0)
            if not math.isfinite(confidence) or not MIN_CONFIDENCE <= confidence <= 1.0:
                continue
            n, e = north, east
            # Nadir pinhole projection: image right = East, image up = North.
            # Fallback is the drone position if camera intrinsics are unavailable.
            if all(k in self.camera for k in ('width', 'height', 'hfov_rad')) and abs(float(self.camera.get('pitch_deg', 90)) - 90) < 1:
                width, image_h = float(self.camera['width']), float(self.camera['height'])
                focal = width / (2 * math.tan(float(self.camera['hfov_rad']) / 2))
                center = detection.bbox.center.position
                n -= (center.y - image_h / 2) * height / focal
                e += (center.x - width / 2) * height / focal
            if not all(math.isfinite(v) for v in (n, e)):
                continue
            if any(math.hypot(n - old_n, e - old_e) <= DEDUP_RADIUS_M
                   for old_n, old_e in self.reported):
                continue
            report_person(north_m=n, east_m=e, confidence=confidence, sim_s=sim_s)
            self.reported.append((n, e))
            print(f'[AI] person N={n:.1f} E={e:.1f} confidence={confidence:.2f}')

    def poll(self):
        if self.node is not None:
            try:
                self.executor.spin_once(timeout_sec=0.0)
            except Exception as exc:
                print(f'[AI] Subscriber error; continuing flight: {exc}')
                self.close()

    def close(self):
        if self.executor is not None:
            self.executor.shutdown(timeout_sec=0.0)
            self.executor = None
        if self.node is not None:
            self.node.destroy_node()
            self.node = None
        if self.context is not None and self.context.ok():
            self.context.shutdown()


def send_setpoint(master, x, y, z, yaw=0.0):
    """Gửi setpoint vị trí cục bộ NED tới Autopilot PX4 (tần số 10Hz)."""
    master.mav.set_position_target_local_ned_send(
        0, master.target_system, master.target_component,
        mavutil.mavlink.MAV_FRAME_LOCAL_NED,
        0b0000101111111000, # Chỉ điều khiển x, y, z, yaw
        x, y, -z,           # Hệ NED: z âm là độ cao hướng lên trời
        0, 0, 0, 0, 0, 0,
        yaw, 0
    )

def fly_mission(reporter):
    print("[SOLUTION] Đang kết nối tới PX4 qua MAVLink UDP 14540...")
    # Cùng cổng Offboard trên PX4 SITL native và container; chỉ chạy một client nhận 14540.
    master = mavutil.mavlink_connection('udpin:0.0.0.0:14540')
    master.wait_heartbeat()
    print("[SOLUTION] Đã nhận Heartbeat từ Autopilot PX4!")

    # 1. Chờ lấy tọa độ Home (vị trí cất cánh ban đầu)
    home_x, home_y, home_z = 0.0, 0.0, 0.0
    while True:
        msg = master.recv_match(type='LOCAL_POSITION_NED', blocking=True, timeout=2.0)
        if msg:
            home_x, home_y, home_z = msg.x, msg.y, -msg.z
            break

    # 2. Sinh danh sách các điểm Waypoint hình zíc-zắc phủ kín 100m x 100m
    waypoints = []
    lanes = int(SURVEY_SIZE / LANE_SPACING)
    for i in range(lanes + 1):
        y_lane = home_y + (i * LANE_SPACING)
        if i % 2 == 0:
            waypoints.append((home_x, y_lane, home_z + ALTITUDE))
            waypoints.append((home_x + SURVEY_SIZE, y_lane, home_z + ALTITUDE))
        else:
            waypoints.append((home_x + SURVEY_SIZE, y_lane, home_z + ALTITUDE))
            waypoints.append((home_x, y_lane, home_z + ALTITUDE))

    # 3. Phát setpoint mồi trước khi chuyển sang OFFBOARD mode
    for _ in range(20):
        send_setpoint(master, home_x, home_y, home_z + ALTITUDE)
        time.sleep(0.05)

    # 4. Chuyển chế độ OFFBOARD & ARM cất cánh
    master.set_mode('OFFBOARD')
    master.mav.command_long_send(
        master.target_system, master.target_component,
        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
        0, 1, 0, 0, 0, 0, 0, 0
    )
    print("[SOLUTION] Drone đã ARM và cất cánh lên độ cao trinh sát!")

    # 5. Vòng lặp bay theo hành trình Waypoint đã lập
    for idx, (target_x, target_y, target_z) in enumerate(waypoints):
        print(f"[MISSION] Đang bay tới Waypoint {idx+1}/{len(waypoints)}: ({target_x:.1f}, {target_y:.1f})")
        
        while True:
            # Gửi nhịp điều khiển 10Hz
            send_setpoint(master, target_x, target_y, target_z)
            msg = master.recv_match(type='LOCAL_POSITION_NED', blocking=False)
            
            if msg:
                cur_x, cur_y, cur_z = msg.x, msg.y, -msg.z
                dist = math.sqrt((target_x - cur_x)**2 + (target_y - cur_y)**2)
                
                reporter.update_position(msg)
                reporter.poll()
                
                # Khi drone cách điểm đích dưới 1.5m, chuyển sang Waypoint kế tiếp
                if dist < 1.5 and abs(target_z - cur_z) < 1.5:
                    break
            time.sleep(0.05)

    # 6. Hoàn thành nhiệm vụ: Bay về Home và Tự động Hạ cánh
    print("[MISSION] Quét xong vùng 100x100m. Đang bay về Home...")
    for _ in range(60):
        send_setpoint(master, home_x, home_y, home_z + ALTITUDE)
        time.sleep(0.05)

    print("[MISSION] Hạ cánh (LAND)...")
    master.set_mode('LAND')
    time.sleep(10)
    print("[MISSION] Hoàn tất bài thi an toàn!")

def main():
    reporter = PersonReporter()
    try:
        fly_mission(reporter)
    finally:
        reporter.close()


if __name__ == '__main__':
    main()
