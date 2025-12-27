from dotenv import load_dotenv
import json
import os
from pathlib import Path

# Load environment variables from .env file if it exists
load_dotenv()

MOCK_MODE = os.getenv("FLOWMATE_MOCK_MODE", "false").lower() == "true"

class ConfigManager:
    """
    Industry-standard configuration manager supporting:
    1. Environment variables (highest priority)
    2. Local config.json file
    3. Default fallbacks
    """
    def __init__(self, filename="config.json"):
        self.filename = filename
        self.defaults = {
            "api_key": "",
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-chat",
            "strict_mode": False
        }
        self.config = self._load_initial_config()

    def _load_initial_config(self) -> dict:
        config = self.defaults.copy()
        
        # 1. Load from config.json if exists
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    config.update(json.load(f))
            except Exception as e:
                print(f"Error loading config.json: {e}")

        # 2. Override with Environment Variables (prefixed with FLOWMATE_)
        # This allows CI/CD or Docker/Dev environments to override local settings
        config["api_key"] = os.getenv("FLOWMATE_API_KEY", config["api_key"])
        config["base_url"] = os.getenv("FLOWMATE_BASE_URL", config["base_url"])
        config["model"] = os.getenv("FLOWMATE_MODEL", config["model"])
        
        strict_env = os.getenv("FLOWMATE_STRICT_MODE")
        if strict_env is not None:
            config["strict_mode"] = strict_env.lower() == "true"
            
        return config

    def save_config(self, key: str, value):
        """Save settings back to local config.json while maintaining current session state."""
        self.config[key] = value
        
        # Only persist user-configurable fields
        persistence_keys = ["api_key", "base_url", "model", "strict_mode"]
        data_to_save = {k: self.config.get(k) for k in persistence_keys}
        
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=4)
        except Exception as e:
            print(f"Error saving config.json: {e}")

    def get(self, key: str, default=None):
        return self.config.get(key, default if default is not None else self.defaults.get(key))

# Singleton instance
CONFIG = ConfigManager()