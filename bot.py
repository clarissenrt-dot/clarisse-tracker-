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

VA_LINK_NAMES = {
    "Mamonj": "Mamonj",
    "Sediy": "Sediy",
    "Minosoa": "Minosoa",
    "PAO": "PAO",
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
    for va_name in ["Mamonj", "Sediy", "Minosoa", "PAO"]:
        count = join_counts.get(va_name, 0)
        lines.append(f"👤 {va_name} : {count} join(s)")
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
        link_name = invite_link.get("name", "").strip() if invite_link else ""
        user = req.get("from", {})
        username = user.get("username", "inconnu")
        logger.info(f"chat_join_request — user: {username}, link_name: '{link_name}'")
        if link_name in VA_LINK_NAMES:
            va_name = VA_LINK_NAMES[link_name]
            join_counts[va_name] += 1
            save_counts()
            logger.info(f"✅ Join comptabilisé pour {va_name} — total: {join_counts[va_name]}")
        else:
            logger.warning(f"⚠️ Nom de lien non reconnu: '{link_name}'")

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
        if self.path == "/counts":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(dict(join_counts)).encode())
        else:
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
