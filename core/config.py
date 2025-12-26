import json
import os

MOCK_MODE = False  # 开发调试开关

class ConfigManager:
    def __init__(self, filename="config.json"):
        self.filename = filename
        self.config = self.load_config()

    def load_config(self):
        if not os.path.exists(self.filename):
            return {
                "api_key": "",
                "base_url": "https://api.deepseek.com",
                "model": "deepseek-chat",
                "strict_mode": False
            }
        try:
            with open(self.filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}

    def save_config(self, key, value):
        self.config[key] = value
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=4)
    
    def get(self, key, default=None):
        return self.config.get(key, default)

# 单例实例
CONFIG = ConfigManager()