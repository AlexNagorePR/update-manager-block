"""
Pytest configuration to work around ROS2 plugin conflicts.
This blocks problematic ROS2 modules before they can cause issues.
"""
import sys
from unittest.mock import MagicMock

# Block launch_testing and related modules before they can cause import errors
sys.modules['launch_testing'] = MagicMock()
sys.modules['launch_testing_ros_pytest_entrypoint'] = MagicMock()
sys.modules['launch'] = MagicMock()
sys.modules['lark'] = MagicMock()




