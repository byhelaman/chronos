"""
Chronos v2 - Application Configuration
No secrets stored in the executable. Configuration is stored locally after first setup.
"""

import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict


@dataclass
class AppConfig:
    """Application configuration stored in user's home directory"""
    supabase_url: str = ""
    supabase_anon_key: str = ""
    last_email: str = ""  # Remember last logged in email
    
    # App metadata
    app_name: str = "Chronos"
    
    @classmethod
    def get_config_dir(cls) -> Path:
        """Get the configuration directory path"""
        import os
        if os.name == 'nt':  # Windows
            base = Path(os.getenv('APPDATA', Path.home()))
        else:  # Linux/Mac
            base = Path.home() / '.config'
        return base / 'Chronos'
    
    @classmethod
    def get_config_path(cls) -> Path:
        """Get the configuration file path"""
        return cls.get_config_dir() / 'config.json'
    
    @classmethod
    def get_session_path(cls) -> Path:
        """Get the session file path"""
        return cls.get_config_dir() / '.session'


class ConfigManager:
    """Manages application configuration"""
    
    _instance: Optional['ConfigManager'] = None
    _config: Optional[AppConfig] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._config is None:
            self._config = self._load_config()
    
    def _load_config(self) -> AppConfig:
        """Load configuration from disk"""
        config_path = AppConfig.get_config_path()
        
        if config_path.exists():
            try:
                data = json.loads(config_path.read_text())
                return AppConfig(**data)
            except (json.JSONDecodeError, TypeError) as e:
                print(f"Warning: Could not load config: {e}")
        
        return AppConfig()
    
    @property
    def config(self) -> AppConfig:
        """Get current configuration"""
        return self._config
    @property
    def supabase_url(self) -> str:
        return self._config.supabase_url
    
    @property
    def supabase_anon_key(self) -> str:
        return self._config.supabase_anon_key
    
    @property
    def last_email(self) -> str:
        return self._config.last_email
    
    def is_configured(self) -> bool:
        """Check if the app has been configured"""
        return bool(self._config.supabase_url and self._config.supabase_anon_key)
    
    def save(self, url: str, anon_key: str) -> None:
        """Save configuration to disk"""
        self._config.supabase_url = url
        self._config.supabase_anon_key = anon_key
        self._save_to_disk()
        print(f"✓ Configuration saved")
    
    def save_email(self, email: str) -> None:
        """Save last used email to config"""
        self._config.last_email = email
        self._save_to_disk()
    
    def _save_to_disk(self) -> None:
        """Write current config to disk"""
        config_dir = AppConfig.get_config_dir()
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = AppConfig.get_config_path()
        config_path.write_text(json.dumps(asdict(self._config), indent=2))
    
    def clear(self) -> None:
        """Clear configuration (for logout/reset)"""
        config_path = AppConfig.get_config_path()
        if config_path.exists():
            config_path.unlink()
        self._config = AppConfig()
        print("✓ Configuration cleared")


# Global instance
config = ConfigManager()
