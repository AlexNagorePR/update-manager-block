import pytest
import threading
from unittest.mock import Mock, patch, MagicMock
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def mock_rclpy():
    """Mock rclpy module for testing without ROS2 installation."""
    with patch('rclpy.init'):
        with patch('rclpy.ok', return_value=True):
            with patch('rclpy.spin_once'):
                with patch('rclpy.shutdown'):
                    yield


@pytest.fixture
def mock_supervisor_response():
    """Mock Balena supervisor response."""
    return {
        "update_pending": False,
        "update_failed": False,
        "status": "idle"
    }


@pytest.fixture
def mock_lock():
    """Mock lockfile for testing."""
    with patch('lockfile.LockFile') as mock_lock_class:
        mock_instance = MagicMock()
        mock_instance.is_locked.return_value = False
        mock_lock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def env_vars(monkeypatch):
    """Set required environment variables for testing."""
    monkeypatch.setenv("BALENA_SUPERVISOR_ADDRESS", "http://localhost:48484")
    monkeypatch.setenv("BALENA_SUPERVISOR_API_KEY", "test_key_12345")
    monkeypatch.setenv("FLE_SAFE_UPDATE_STATES", "1,2,3")
    yield


@pytest.fixture
def reset_globals():
    """Reset global state between tests."""
    yield
    # Import after path is set up
    import importlib
    if 'main' in sys.modules:
        main_module = sys.modules['main']
        main_module.waiting_for_update = False
        main_module.update_allowed = False
        main_module.robot_state = -1
        main_module.lock_released_for_update = False


@pytest.fixture
def mock_rclpy_node():
    """Mock rclpy.node.Node for testing node callbacks."""
    with patch('rclpy.init', return_value=None) as mock_init:
        mock_init.return_value = None
        # Mock the Node class creation
        with patch('rclpy.node.Node.__init__', return_value=None):
            yield mock_init

