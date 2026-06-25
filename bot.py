import os
import json
import logging
import threading
import time
import requests
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
    try:
        requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=10)
    except Exception as e:
        logger.error(f"send_message error: {e}")

def handle_update(update):
    logger.info(f"Update reçu: {json.dumps(update)[:200]}")
    
    if "message" in update:
        message = update["message"]
        chat_id = message["chat"]["id"]
        text = message.get("text", "")

        if "/start" in text:
            send_message(chat_id, "👋 Bot tracking Clarisse actif!\n\n/stats — Stats\n/reset — Remettre à 0")
        elif "/stats" in text:
            lines = ["📊 Stats depuis activation:\n"]
            for link, info in stats.items():
                lines.append(f"👤 {info['va']}: {info['total_joins']} joins")
            send_message(chat_id, "\n".join(lines))
        elif "/reset" in text:
            for link in stats:
                stats[link]["total_joins"] = 0
            send_message(chat_id, "✅ Remis à 0.")

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
                    logger.info(f"✅ Join via {va_name} — total: {stats[link_url]['total_joins']}")

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            logger.info(f"POST {self.path} body: {body[:200]}")
            if self.path == "/webhook":
                update = json.loads(body)
                handle_update(update)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        except Exception as e:
            logger.error(f"POST error: {e}")
            self.send_response(500)
            self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot running OK")

    def log_message(self, format, *args):
        pass

def main():
    logger.info(f"Démarrage sur port {PORT}...")
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    logger.info("Serveur prêt.")
    server.serve_forever()

if __name__ == "__main__":
    main()
