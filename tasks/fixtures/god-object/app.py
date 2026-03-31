"""A monolithic AppManager class mixing multiple responsibilities.

This is a classic 'God Object' anti-pattern that needs refactoring.
"""
import json
import time
from typing import Optional, Any, dict as DictType
from pathlib import Path


class AppManager:
    """A monolithic manager handling users, email, logging, and configuration.
    
    This class violates the Single Responsibility Principle by mixing:
    - User management (create_user, authenticate, list_users)
    - Email operations (send_email, send_welcome)
    - Logging operations (log_info, log_error, rotate_logs)
    - Configuration management (load_config, get_setting, update_setting)
    """

    def __init__(self, config_path: str = "config.json"):
        """Initialize the AppManager.
        
        Args:
            config_path: Path to configuration file
        """
        self.config_path = config_path
        self.users: dict[str, dict[str, Any]] = {}
        self.config: dict[str, Any] = {}
        self.logs: list[str] = []
        self.email_queue: list[dict[str, str]] = []
        self._next_user_id = 1
        self._load_config()

    # User management methods
    def create_user(self, username: str, password: str, email: str) -> dict[str, Any]:
        """Create a new user.
        
        Args:
            username: Username
            password: Password
            email: Email address
            
        Returns:
            Created user data
        """
        if username in self.users:
            self.log_error(f"User {username} already exists")
            return {}
        
        user = {
            "id": self._next_user_id,
            "username": username,
            "password": password,
            "email": email,
            "created_at": time.time(),
            "active": True
        }
        self._next_user_id += 1
        self.users[username] = user
        self.log_info(f"Created user {username}")
        self.send_welcome(email, username)
        return user

    def authenticate(self, username: str, password: str) -> bool:
        """Authenticate a user.
        
        Args:
            username: Username
            password: Password
            
        Returns:
            True if authenticated
        """
        if username not in self.users:
            self.log_error(f"User {username} not found")
            return False
        
        user = self.users[username]
        if user["password"] != password:
            self.log_error(f"Invalid password for {username}")
            return False
        
        self.log_info(f"User {username} authenticated")
        return True

    def list_users(self) -> list[dict[str, Any]]:
        """List all users.
        
        Returns:
            List of user data
        """
        self.log_info(f"Listed {len(self.users)} users")
        return list(self.users.values())

    # Email sending methods
    def send_email(self, to: str, subject: str, body: str) -> None:
        """Send an email.
        
        Args:
            to: Recipient email
            subject: Email subject
            body: Email body
        """
        email = {
            "to": to,
            "subject": subject,
            "body": body,
            "timestamp": time.time()
        }
        self.email_queue.append(email)
        self.log_info(f"Email queued to {to}: {subject}")

    def send_welcome(self, email: str, username: str) -> None:
        """Send a welcome email to a new user.
        
        Args:
            email: User email
            username: Username
        """
        subject = f"Welcome to AppManager, {username}!"
        body = f"Hello {username}, welcome to our application."
        self.send_email(email, subject, body)

    def flush_email_queue(self) -> int:
        """Send all queued emails.
        
        Returns:
            Number of emails sent
        """
        count = len(self.email_queue)
        self.log_info(f"Flushed {count} emails from queue")
        self.email_queue.clear()
        return count

    # Logging methods
    def log_info(self, message: str) -> None:
        """Log an info message.
        
        Args:
            message: Log message
        """
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] INFO: {message}"
        self.logs.append(log_entry)

    def log_error(self, message: str) -> None:
        """Log an error message.
        
        Args:
            message: Log message
        """
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] ERROR: {message}"
        self.logs.append(log_entry)

    def get_logs(self) -> list[str]:
        """Get all logs.
        
        Returns:
            List of log entries
        """
        return self.logs.copy()

    def rotate_logs(self, max_size: int = 1000) -> None:
        """Rotate logs if they exceed max size.
        
        Args:
            max_size: Maximum number of log entries
        """
        if len(self.logs) > max_size:
            self.logs = self.logs[-max_size:]
            self.log_info("Logs rotated")

    # Configuration methods
    def _load_config(self) -> None:
        """Load configuration from file."""
        if Path(self.config_path).exists():
            with open(self.config_path) as f:
                self.config = json.load(f)
        else:
            self.config = self._get_default_config()
            self._save_config()

    def _get_default_config(self) -> dict[str, Any]:
        """Get default configuration."""
        return {
            "app_name": "AppManager",
            "version": "1.0.0",
            "debug": False,
            "max_users": 1000
        }

    def _save_config(self) -> None:
        """Save configuration to file."""
        with open(self.config_path, "w") as f:
            json.dump(self.config, f, indent=2)

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a configuration setting.
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        return self.config.get(key, default)

    def update_setting(self, key: str, value: Any) -> None:
        """Update a configuration setting.
        
        Args:
            key: Configuration key
            value: New value
        """
        self.config[key] = value
        self._save_config()
        self.log_info(f"Updated setting {key}")

    def get_all_settings(self) -> dict[str, Any]:
        """Get all configuration settings.
        
        Returns:
            Configuration dictionary
        """
        return self.config.copy()
