import os
import json
import logging
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN")
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
PORT = int(os.environ.get("PORT", 10000))

VA_NAMES = {
    "https://t.me/+8FkXVyTNSB9hZGI0": "Mamonj",
    "https://t.me/+zS3jbHJep8I2ZjE0": "Snazzy",
    "https://t.me/+OUI_fYmb091lOTk0": "Rock",
    "https://t.me/+-7ocRNFOJPEzZDZk": "JohnAsso",
}

DATA_FILE = "/data/counts.json"

def load_counts():
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                return defaultdict(int, json.load(f))
    except Exception as e:
        logger.error(f"Erreur chargement counts: {e}")
    return defaultdict(int)

def save_counts():
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(dict(join_counts), f)
        logger.info(f"✅ Sauvegarde OK: {dict(join_counts)}")
    except Exception as e:
        logger.error(f"Erreur sauvegarde counts: {e}")

join_counts = load_counts()

def send_message(chat_id, text):
    try:
        r = requests.post(f"{BASE_URL}/sendMessage",
            json={"chat_id": chat_id, "text": text}, timeout=10)
        logger.info(f"sendMessage: {r.status_code}")
    except Exception as e:
        logger.error(f"send_message error: {e}")

def get_stats_text():
    lines = ["📊 Stats joins par VA :\n"]
    for link, name in VA_NAMES.items():
        count = join_counts.get(name, 0)
        lines.append(f"👤 {name} : {count} join(s)")
    lines.append(f"\nTotal : {sum(join_counts.values())}")
    return "\n".join(lines)

def handle_update(update):
    logger.info(f"Update reçu: {str(update)[:1000]}")

    if "message" in update:
        chat_id = update["message"]["chat"]["id"]
        text = update["message"].get("text", "")
        if "/stats" in text or "/start" in text:
            send_message(chat_id, get_stats_text())
        elif "/test" in text:
            send_message(chat_id, "✅ Bot actif!")

    if "chat_join_request" in update:
        req = update["chat_join_request"]
        invite_link = req.get("invite_link", {})
        link_url = invite_link.get("invite_link", "").strip() if invite_link else ""
        user = req.get("from", {})
        username = user.get("username", "inconnu")
        logger.info(f"LIEN COMPLET: '{link_url}'")
        logger.info(f"MATCH: {link_url in VA_NAMES}")
        if link_url in VA_NAMES:
            va_name = VA_NAMES[link_url]
            join_counts[va_name] += 1
            save_counts()
            logger.info(f"✅ Join comptabilisé pour {va_name} — total: {join_counts[va_name]}")
        else:
            logger.warning(f"⚠️ Lien non reconnu: '{link_url}'")

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
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
