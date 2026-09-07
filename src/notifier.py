"""
Multi-Channel Alert Notifier (WhatsApp & Companion)
Enterprise Trading Corporation

Delivers executive alerts via:
  1. WhatsApp Gateway (Green-API / UltraMsg / Twilio)
  2. Telegram Bot (Instant free companion channel)
  3. Console Simulator (Zero-setup local testing)
"""

import os, json, requests
from pathlib import Path
from typing import Dict, Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
NOTIFIER_CONFIG = CONFIG_DIR / "notifier_config.json"

class Notifier:
    """Dispatches formatted alerts to mobile channels."""

    def __init__(self, config_path: Path = NOTIFIER_CONFIG):
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "channel": "console", # 'whatsapp_greenapi', 'whatsapp_ultramsg', 'telegram', or 'console'
            "recipient_phone": "+8801700000000", # Executive's number
            "test_phone": "+8801XXXXXXXXX",      # User's test number
            "greenapi": {"idInstance": "", "apiTokenInstance": ""},
            "ultramsg": {"instance_id": "", "token": ""},
            "telegram": {"bot_token": "", "chat_id": ""}
        }

    def send_alert(self, message_text: str, recipient_override: Optional[str] = None) -> Dict[str, Any]:
        """
        Sends the alert message to the configured channel.
        Falls back to console simulator if no external API is configured.
        """
        channel = self.config.get("channel", "console")
        target_phone = recipient_override or self.config.get("recipient_phone")

        # 1. WhatsApp via Green-API
        if channel == "whatsapp_greenapi":
            id_inst = self.config.get("greenapi", {}).get("idInstance")
            token = self.config.get("greenapi", {}).get("apiTokenInstance")
            if id_inst and token:
                host = self.config.get("greenapi", {}).get("host") or (f"https://{id_inst[:4]}.api.greenapi.com" if len(id_inst) >= 4 else "https://api.green-api.com")
                url = f"{host.rstrip('/')}/waInstance{id_inst}/sendMessage/{token}"
                chat_id = f"{target_phone.replace('+', '').replace('-', '').replace(' ', '')}@c.us"
                try:
                    res = requests.post(url, json={"chatId": chat_id, "message": message_text}, timeout=10)
                    return {"status": "sent", "channel": "whatsapp_greenapi", "response": res.json()}
                except Exception as e:
                    return {"status": "error", "channel": "whatsapp_greenapi", "error": str(e)}

        # 2. WhatsApp via UltraMsg
        elif channel == "whatsapp_ultramsg":
            inst_id = self.config.get("ultramsg", {}).get("instance_id")
            token = self.config.get("ultramsg", {}).get("token")
            if inst_id and token:
                url = f"https://api.ultramsg.com/{inst_id}/messages/chat"
                payload = {
                    "token": token,
                    "to": target_phone,
                    "body": message_text
                }
                try:
                    res = requests.post(url, data=payload, timeout=10)
                    return {"status": "sent", "channel": "whatsapp_ultramsg", "response": res.json()}
                except Exception as e:
                    return {"status": "error", "channel": "whatsapp_ultramsg", "error": str(e)}

        # 3. Telegram Bot Companion
        elif channel == "telegram":
            bot_token = self.config.get("telegram", {}).get("bot_token")
            chat_id = self.config.get("telegram", {}).get("chat_id")
            if bot_token and chat_id:
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                try:
                    res = requests.post(url, json={"chat_id": chat_id, "text": message_text}, timeout=10)
                    return {"status": "sent", "channel": "telegram", "response": res.json()}
                except Exception as e:
                    return {"status": "error", "channel": "telegram", "error": str(e)}

        # 4. Default Console / Dry-Run Mode
        return {
            "status": "simulated",
            "channel": "console",
            "target": target_phone,
            "message_length": len(message_text),
            "preview": message_text[:120]
        }
