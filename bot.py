import os
import json
import logging
import threading
import time
import requests
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
PORT = int(os.environ.get("PORT", 10000))

stats = {
    "https://t.me/+8FkXVyTNSB9hZGI0": {"va": "Mamonj", "total_joins": 0},
    "https://t.me/+zS3jbHJep8I2ZjE0": {"va": "Snazzy", "total_joins": 0},
    "https://t.me/+OUI_fYmb091lOTk0": {"va": "Rock", "total_joins": 0},
    "https://t.me/+-7ocRNFOJPEzZDZk": {"va": "JohnAsso", "total_joins": 0},
}

def send_message(chat_id, text):
    requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": text})

def set_webhook():
    time.sleep(3)  # Attendre que le serveur soit prêt
    url = f"{WEBHOOK_URL}/webhook" if not WEBHOOK_URL.endswith("/webhook") else WEBHOOK_URL
    r = requests.post(f"{BASE_URL}/setWebhook", json={
        "url": url,
        "allowed_updates": ["message", "chat_member"]
    })
    result = r.json()
    logger.info(f"Webhook set: {result}")

def handle_update(update):
    if "message" in update:
        message = update["message"]
        chat_id = message["chat"]["id"]
        text = message.get("text", "")

        if text.startswith("/start"):
            send_message(chat_id,
                "👋 Bot tracking Clarisse actif!\n\n"
                "/stats — Stats de tous les VAs\n"
                "/reset — Remettre à 0"
            )
        elif text.startswith("/stats"):
            lines = ["📊 Stats depuis activation:\n"]
            for link, info in stats.items():
                lines.append(f"👤 {info['va']}: {info['total_joins']} nouveaux joins")
            send_message(chat_id, "\n".join(lines))
        elif text.startswith("/reset"):
            for link in stats:
                stats[link]["total_joins"] = 0
            send_message(chat_id, "✅ Compteurs remis à 0.")

    if "chat_member" in update:
        result = update["chat_member"]
        old_status = result.get("old_chat_member", {}).get("status", "")
        new_status = result.get("new_chat_member", {}).get("status", "")
        logger.info(f"chat_member: {old_status} -> {new_status}")

        if old_status in ["left", "kicked"] and new_status in ["member", "subscriber"]:
            invite_link = result.get("invite_link", {})
            if invite_link:
                link_url = invite_link.get("invite_link", "")
                if link_url in stats:
                    stats[link_url]["total_joins"] += 1
                    va_name = stats[link_url]["va"]
                    logger.info(f"✅ Nouveau join via {va_name} — total: {stats[link_url]['total_joins']}")

class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/webhook":
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            try:
                update = json.loads(body)
                handle_update(update)
            except Exception as e:
                logger.error(f"Erreur: {e}")
            self.send_response(200)
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot running OK")

    def log_message(self, format, *args):
        pass

def main():
    logger.info(f"Bot démarré sur port {PORT}...")
    threading.Thread(target=set_webhook, daemon=True).start()
    server = HTTPServer(("0.0.0.0", PORT), WebhookHandler)
    server.serve_forever()

if __name__ == "__main__":
    main()
