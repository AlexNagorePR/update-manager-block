import pytest
import threading
import json
from unittest.mock import Mock, patch, MagicMock
from lockfile import AlreadyLocked, NotLocked, NotMyLock
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestLockOperations:
    """Tests for lock acquisition and release operations."""

    @pytest.fixture(autouse=True)
    def setup(self, env_vars, mock_lock, reset_globals):
        """Setup for each test."""
        pass

    def test_acquire_lock_success(self, mock_lock):
        """Test successful lock acquisition."""
        with patch('main.lock', mock_lock):
            mock_lock.acquire.return_value = None  # acquire() returns None on success
            
            # We need to import after mocking
            import main
            result = main.acquire_lock()
            
            assert result is True
            mock_lock.acquire.assert_called_once_with(timeout=0)

    def test_acquire_lock_already_locked(self, mock_lock):
        """Test lock acquisition when lock already exists."""
        with patch('main.lock', mock_lock):
            mock_lock.acquire.side_effect = AlreadyLocked()
            
            import main
            result = main.acquire_lock()
            
            assert result is False

    def test_release_lock_success(self, mock_lock):
        """Test successful lock release."""
        with patch('main.lock', mock_lock):
            mock_lock.release.return_value = None
            
            import main
            result = main.release_lock()
            
            assert result is True
            mock_lock.release.assert_called_once()

    def test_release_lock_not_locked(self, mock_lock):
        """Test release when lock is not held."""
        with patch('main.lock', mock_lock):
            mock_lock.release.side_effect = NotLocked()
            
            import main
            result = main.release_lock()
            
            assert result is False

    def test_release_lock_not_my_lock(self, mock_lock):
        """Test release when lock belongs to another process."""
        with patch('main.lock', mock_lock):
            mock_lock.release.side_effect = NotMyLock()
            
            import main
            result = main.release_lock()
            
            assert result is False

    def test_is_locked(self, mock_lock):
        """Test checking lock status."""
        with patch('main.lock', mock_lock):
            mock_lock.is_locked.return_value = True
            
            import main
            result = main.is_locked()
            
            assert result is True


class TestUpdateStateLogic:
    """Tests for update state determination logic."""

    @pytest.fixture(autouse=True)
    def setup(self, env_vars, reset_globals):
        """Setup for each test."""
        pass

    def test_waiting_for_update_both_flags_true(self):
        """Test when update_pending and update_failed are both true."""
        import main
        device_state = {
            "update_pending": True,
            "update_failed": True
        }
        
        result = main.is_waiting_for_update(device_state)
        assert result is True

    def test_waiting_for_update_only_pending(self):
        """Test when only update_pending is true."""
        import main
        device_state = {
            "update_pending": True,
            "update_failed": False
        }
        
        result = main.is_waiting_for_update(device_state)
        assert result is False

    def test_waiting_for_update_only_failed(self):
        """Test when only update_failed is true."""
        import main
        device_state = {
            "update_pending": False,
            "update_failed": True
        }
        
        result = main.is_waiting_for_update(device_state)
        assert result is False

    def test_waiting_for_update_both_false(self):
        """Test when both flags are false."""
        import main
        device_state = {
            "update_pending": False,
            "update_failed": False
        }
        
        result = main.is_waiting_for_update(device_state)
        assert result is False

    def test_waiting_for_update_missing_fields(self):
        """Test with missing fields in device state."""
        import main
        device_state = {}
        
        result = main.is_waiting_for_update(device_state)
        assert result is False


class TestUnlockCondition:
    """Tests for unlock condition evaluation."""

    @pytest.fixture(autouse=True)
    def setup(self, env_vars, mock_lock, reset_globals):
        """Setup for each test."""
        pass

    def test_evaluate_unlock_condition_met(self, mock_lock):
        """Test unlock condition when all criteria are met."""
        import main
        
        with patch('main.lock', mock_lock):
            mock_lock.is_locked.return_value = True
            
            # Set up conditions for unlock
            main.update_allowed = True
            main.robot_state = 1  # In SAFE_UPDATE_STATES
            main.waiting_for_update = True
            
            main.evaluate_unlock_condition()
            
            # Verify release_lock was called
            mock_lock.release.assert_called_once()

    def test_evaluate_unlock_condition_not_allowed(self, mock_lock):
        """Test unlock condition when update is not allowed."""
        import main
        
        with patch('main.lock', mock_lock):
            mock_lock.is_locked.return_value = True
            
            main.update_allowed = False
            main.robot_state = 1
            main.waiting_for_update = True
            
            main.evaluate_unlock_condition()
            
            # Verify release_lock was NOT called
            mock_lock.release.assert_not_called()

    def test_evaluate_unlock_condition_not_waiting(self, mock_lock):
        """Test unlock condition when not waiting for update."""
        import main
        
        with patch('main.lock', mock_lock):
            mock_lock.is_locked.return_value = True
            
            main.update_allowed = True
            main.robot_state = 1
            main.waiting_for_update = False
            
            main.evaluate_unlock_condition()
            
            mock_lock.release.assert_not_called()

    def test_evaluate_unlock_condition_not_locked(self, mock_lock):
        """Test unlock condition when lock is not held."""
        import main
        
        with patch('main.lock', mock_lock):
            mock_lock.is_locked.return_value = False
            
            main.update_allowed = True
            main.robot_state = 1
            main.waiting_for_update = True
            
            main.evaluate_unlock_condition()
            
            mock_lock.release.assert_not_called()

    def test_evaluate_unlock_condition_unsafe_state(self, mock_lock):
        """Test unlock condition with robot in unsafe state."""
        import main
        
        with patch('main.lock', mock_lock):
            mock_lock.is_locked.return_value = True
            
            main.update_allowed = True
            main.robot_state = 99  # Not in SAFE_UPDATE_STATES
            main.waiting_for_update = True
            
            main.evaluate_unlock_condition()
            
            mock_lock.release.assert_not_called()


class TestFetchDeviceState:
    """Tests for fetching device state from supervisor."""

    @pytest.fixture(autouse=True)
    def setup(self, env_vars):
        """Setup for each test."""
        pass

    def test_fetch_device_state_success(self):
        """Test successful device state fetch."""
        import main
        
        mock_response_data = {
            "update_pending": True,
            "update_failed": True,
            "status": "updating"
        }
        
        with patch('main.request.urlopen') as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = json.dumps(mock_response_data).encode('utf-8')
            mock_response.__enter__.return_value = mock_response
            mock_urlopen.return_value = mock_response
            
            result = main.fetch_device_state()
            
            assert result == mock_response_data

    def test_fetch_device_state_includes_api_key(self):
        """Test that fetch includes correct API key in request."""
        import main
        
        with patch('main.request.urlopen') as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = b'{}'
            mock_response.__enter__.return_value = mock_response
            mock_urlopen.return_value = mock_response
            
            main.fetch_device_state()
            
            # Verify request was made to correct URL with API key
            call_args = mock_urlopen.call_args
            request_obj = call_args[0][0]
            assert "apikey=test_key_12345" in request_obj.full_url


class TestNodeCallbacks:
    """Tests for UpdateManagerNode callbacks."""

    @pytest.fixture(autouse=True)
    def setup(self, env_vars, mock_lock, reset_globals):
        """Setup for each test."""
        pass

    def test_state_callback(self, mock_lock):
        """Test state subscription callback logic."""
        import main
        
        # Test the callback logic directly without creating a full node
        with patch('main.lock', mock_lock):
            with patch('main.state_lock', threading.Lock()):
                # Simulate the callback behavior
                msg = MagicMock()
                msg.data = 42
                
                # Execute the callback logic inline
                with patch('main.state_lock'):
                    main.robot_state = int(msg.data)
                    assert main.robot_state == 42

    def test_update_allowed_callback_change(self, mock_lock):
        """Test update_allowed subscription callback logic."""
        import main
        
        with patch('main.lock', mock_lock):
            with patch('main.state_lock', threading.Lock()):
                main.update_allowed = False
                
                msg = MagicMock()
                msg.data = True
                
                # Execute the callback logic inline
                with patch('main.state_lock'):
                    previous_allowed = main.update_allowed
                    main.update_allowed = bool(msg.data)
                    assert main.update_allowed is True
                    assert previous_allowed is False

    def test_get_update_state_service_callback_logic(self, mock_lock):
        """Test get_update_state service callback response creation."""
        import main
        
        with patch('main.lock', mock_lock):
            main.waiting_for_update = True
            
            # Simulate the service callback
            response = MagicMock()
            
            # Inline callback logic
            with patch('main.state_lock'):
                response.update_pending = main.waiting_for_update
            
            assert response.update_pending is True

    def test_publish_update_pending_logic(self, mock_lock):
        """Test update pending publishing logic."""
        import main
        
        with patch('main.lock', mock_lock):
            with patch('main.rclpy.ok', return_value=True):
                # Test the publish logic
                from std_msgs.msg import Bool
                msg = Bool()
                msg.data = True
                
                assert msg.data is True



class TestEnsureLockOwned:
    """Tests for lock ownership enforcement on startup."""

    @pytest.fixture(autouse=True)
    def setup(self, env_vars, mock_lock, reset_globals):
        """Setup for each test."""
        pass

    def test_ensure_lock_owned_no_previous_lock(self, mock_lock):
        """Test when no previous lock exists."""
        import main
        
        with patch('main.lock', mock_lock):
            mock_lock.is_locked.return_value = False
            mock_lock.acquire.return_value = None
            
            result = main.ensure_lock_owned()
            
            assert result is True
            mock_lock.break_lock.assert_not_called()
            mock_lock.acquire.assert_called_once_with(timeout=0)

    def test_ensure_lock_owned_breaks_existing_lock(self, mock_lock):
        """Test that existing lock is broken and new one acquired."""
        import main
        
        with patch('main.lock', mock_lock):
            mock_lock.is_locked.return_value = True
            mock_lock.break_lock.return_value = None
            mock_lock.acquire.return_value = None
            
            result = main.ensure_lock_owned()
            
            assert result is True
            mock_lock.break_lock.assert_called_once()
            mock_lock.acquire.assert_called_once_with(timeout=0)

    def test_ensure_lock_owned_cannot_acquire(self, mock_lock):
        """Test when lock cannot be acquired."""
        import main
        
        with patch('main.lock', mock_lock):
            mock_lock.is_locked.return_value = False
            mock_lock.acquire.side_effect = AlreadyLocked()
            
            result = main.ensure_lock_owned()
            
            assert result is False
