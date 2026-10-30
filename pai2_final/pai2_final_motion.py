"""Allow-listed CRANE+ V2 trajectory publisher for the official ROS 2 controllers."""

from __future__ import annotations

from typing import Sequence

import rclpy
import yaml
from ament_index_python.packages import get_package_share_directory
from rclpy.node import Node
from std_msgs.msg import String
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint


class MotionNode(Node):
    def __init__(self) -> None:
        super().__init__('pai2_final_motion')
        default_config = get_package_share_directory('pai2_final') + '/config/motions.yaml'
        self.declare_parameter('config_file', default_config)
        config_path = self.get_parameter('config_file').value
        with open(config_path, encoding='utf-8') as stream:
            self.config = yaml.safe_load(stream)['motion']

        self.arm_pub = self.create_publisher(
            JointTrajectory, self.config['arm_topic'], 10)
        self.gripper_pub = self.create_publisher(
            JointTrajectory, self.config['gripper_topic'], 10)
        self.busy = False
        self.steps: list[tuple[list[tuple[str, str]], float, float]] = []
        self.step_index = 0
        self.step_timer = None
        self.subscription = self.create_subscription(
            String, '/pai2_final/motion', self.on_command, 10)
        self.get_logger().info('許可動作: celebrate, shake_no, home')

    def _trajectory(self, names: Sequence[str], positions: Sequence[float], duration: float):
        if len(names) != len(positions):
            raise ValueError('joint_namesとpositionsの数が一致しません')
        limits = {
            'crane_plus_joint1': (-2.60, 2.60),
            'crane_plus_joint2': (-1.80, 1.75),
            'crane_plus_joint3': (-2.50, 2.50),
            'crane_plus_joint4': (-1.80, 1.75),
            'crane_plus_joint_hand': (-0.70, 0.67),
        }
        checked = [float(value) for value in positions]
        for name, value in zip(names, checked):
            if name not in limits or not limits[name][0] <= value <= limits[name][1]:
                raise ValueError(f'関節目標値が未許可または範囲外です: {name}={value}')
        if duration <= 0 or duration > float(self.config['max_duration_sec']):
            raise ValueError('軌道時間が許容範囲外です')
        max_speed = float(self.config['max_velocity_rad_s'])
        if max(abs(value) / duration for value in checked) > max_speed:
            raise ValueError('設定された速度上限を超える軌道です')
        point = JointTrajectoryPoint()
        point.positions = checked
        point.time_from_start.sec = int(duration)
        point.time_from_start.nanosec = int((duration % 1.0) * 1_000_000_000)
        msg = JointTrajectory()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.joint_names = list(names)
        msg.points = [point]
        return msg

    def _publish_arm(self, preset: str, duration: float) -> None:
        values = self.config['arm'][preset]
        self.arm_pub.publish(self._trajectory(
            self.config['arm_joints'], values, duration))

    def _publish_gripper(self, preset: str, duration: float) -> None:
        values = self.config['gripper'][preset]
        self.gripper_pub.publish(self._trajectory(
            self.config['gripper_joints'], values, duration))

    def _start_step(self) -> None:
        if self.step_index >= len(self.steps):
            self.busy = False
            self.get_logger().info('動作完了')
            return

        targets, move_sec, wait_sec = self.steps[self.step_index]
        self.step_index += 1
        for target, preset in targets:
            if target == 'arm':
                self._publish_arm(preset, move_sec)
            else:
                self._publish_gripper(preset, move_sec)
        self.step_timer = self.create_timer(
            wait_sec, self._finish_step, clock=self.get_clock())

    def _finish_step(self) -> None:
        if self.step_timer is not None:
            self.step_timer.cancel()
            self.destroy_timer(self.step_timer)
            self.step_timer = None
        self._start_step()

    def on_command(self, message: String) -> None:
        command = message.data
        if command not in ('celebrate', 'shake_no', 'home'):
            self.get_logger().warning(f'未許可の動作を拒否しました: {command!r}')
            return
        if self.busy:
            self.get_logger().warning('動作中の要求を拒否しました')
            return
        if self.arm_pub.get_subscription_count() < 1 or self.gripper_pub.get_subscription_count() < 1:
            self.get_logger().error('CRANE+ V2コントローラーが見つからないため指令を送りません')
            return

        move_time = float(self.config['move_time_sec'])
        shake_time = float(self.config.get('shake_move_time_sec', move_time))
        try:
            if command == 'celebrate':
                down_step = (
                    [('arm', 'celebrate'), ('gripper', 'open')],
                    move_time,
                    move_time + float(self.config['hold_time_sec']),
                )
                up_step = ([('arm', 'home'), ('gripper', 'home')], move_time, move_time)
                self.steps = [down_step, up_step, down_step, up_step]
            elif command == 'shake_no':
                self.steps = [
                    ([('gripper', 'closed'), ('arm', 'shake_left')], shake_time, shake_time),
                ]
                for cycle in range(int(self.config['shake_cycles'])):
                    self.steps.append(([('arm', 'shake_right')], shake_time, shake_time))
                    if cycle + 1 < int(self.config['shake_cycles']):
                        self.steps.append(([('arm', 'shake_left')], shake_time, shake_time))
                self.steps.append(
                    ([('arm', 'home'), ('gripper', 'home')], shake_time, shake_time))
            else:
                self.steps = [([('arm', 'home'), ('gripper', 'home')], move_time, move_time)]
            self.step_index = 0
            self.busy = True
            self._start_step()
        except Exception as exc:  # Keep node alive, but never send another motion on error.
            self.get_logger().error(f'動作失敗: {exc}')
            self.busy = False


def main(args=None) -> None:
    rclpy.init(args=args)
    node = MotionNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
