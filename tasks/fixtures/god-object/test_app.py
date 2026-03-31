"""Tests for the AppManager class."""
import json
import tempfile
import os
from pathlib import Path
from app import AppManager


def test_user_creation():
    """Test creating a new user."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.json")
        manager = AppManager(config_path)
        
        user = manager.create_user("alice", "password123", "alice@example.com")
        assert user["username"] == "alice"
        assert user["email"] == "alice@example.com"
        assert user["id"] == 1


def test_authentication():
    """Test user authentication."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.json")
        manager = AppManager(config_path)
        
        manager.create_user("bob", "secret", "bob@example.com")
        assert manager.authenticate("bob", "secret") is True
        assert manager.authenticate("bob", "wrong") is False


def test_list_users():
    """Test listing users."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.json")
        manager = AppManager(config_path)
        
        manager.create_user("user1", "pass1", "user1@example.com")
        manager.create_user("user2", "pass2", "user2@example.com")
        
        users = manager.list_users()
        assert len(users) == 2


def test_email_queue():
    """Test email queue operations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.json")
        manager = AppManager(config_path)
        
        manager.send_email("test@example.com", "Test", "Test body")
        assert len(manager.email_queue) == 1
        
        count = manager.flush_email_queue()
        assert count == 1
        assert len(manager.email_queue) == 0


def test_logging():
    """Test logging functionality."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.json")
        manager = AppManager(config_path)
        
        manager.log_info("Test message")
        logs = manager.get_logs()
        assert len(logs) > 0
        assert "INFO" in logs[-1]
        assert "Test message" in logs[-1]


def test_configuration():
    """Test configuration management."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.json")
        manager = AppManager(config_path)
        
        # Check default config
        assert manager.get_setting("app_name") == "AppManager"
        
        # Update setting
        manager.update_setting("app_name", "MyApp")
        assert manager.get_setting("app_name") == "MyApp"
        
        # Check persistence
        manager2 = AppManager(config_path)
        assert manager2.get_setting("app_name") == "MyApp"


def test_full_workflow():
    """Test a complete workflow."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.json")
        manager = AppManager(config_path)
        
        # Create users
        manager.create_user("admin", "admin123", "admin@example.com")
        manager.create_user("user", "user123", "user@example.com")
        
        # Authenticate
        assert manager.authenticate("admin", "admin123") is True
        
        # Check email queue (welcome emails sent)
        assert len(manager.email_queue) == 2
        
        # Flush emails
        manager.flush_email_queue()
        
        # Check logs
        logs = manager.get_logs()
        assert len(logs) > 0
        
        # Update config
        manager.update_setting("max_users", 500)
        assert manager.get_setting("max_users") == 500
