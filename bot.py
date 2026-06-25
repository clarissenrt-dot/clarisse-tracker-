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
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
PORT = int(os.environ.get("PORT", 10000))

# Liens VA — le bot va récupérer les stats directement depuis l'API Telegram
VA_LINKS = {
    "https://t.me/+8FkXVyTNSB9hZGI0": "Mamonj",
    "https://t.me/+zS3jbHJep8I2ZjE0": "Snazzy",
    "https://t.me/+OUI_fYmb091lOTk0": "Rock",
    "https://t.me/+-7ocRNFOJPEzZDZk": "JohnAsso",
}

def get_invite_link_info(link):
    """Récupère les infos d'un lien d'invitation via l'API"""
    try:
        r = requests.post(f"{BASE_URL}/exportChatInviteLink", json={}, timeout=10)
        logger.info(f"exportChatInviteLink: {r.json()}")
    except Exception as e:
        logger.error(f"Erreur: {e}")

def get_all_invite_links(chat_id):
    """Récupère tous les liens d'invitation du canal"""
    try:
        r = requests.post(f"{BASE_URL}/getChatAdministrators", 
            json={"chat_id": chat_id}, timeout=10)
        result = r.json()
        logger.info(f"Admins: {result}")
        return result
    except Exception as e:
        logger.error(f"Erreur getChatAdministrators: {e}")
        return None

def fetch_stats_for_link(link):
    """Utilise getInviteLink pour récupérer le nombre de joins"""
    try:
        # On utilise revokeChatInviteLink pour récupérer les stats sans révoquer
        r = requests.post(f"{BASE_URL}/getChatInviteLink",
            json={"invite_link": link},
            timeout=10)
        result = r.json()
        logger.info(f"Stats pour {link}: {result}")
        if result.get("ok"):
            return result["result"].get("member_count", 0), result["result"].get("pending_join_request_count", 0)
    except Exception as e:
        logger.error(f"Erreur fetch_stats: {e}")
    return 0, 0

def send_message(chat_id, text):
    try:
        requests.post(f"{BASE_URL}/sendMessage", 
            json={"chat_id": chat_id, "text": text}, timeout=10)
    except Exception as e:
        logger.error(f"send_message error: {e}")

def get_stats_text():
    lines = ["📊 Stats par VA (joins totaux depuis création du lien):\n"]
    for link, va_name in VA_LINKS.items():
        count, pending = fetch_stats_for_link(link)
        lines.append(f"👤 {va_name}: {count} membres actifs")
    return "\n".join(lines)

def handle_update(update):
    logger.info(f"Update: {str(update)[:100]}")
    if "message" in update:
        chat_id = update["message"]["chat"]["id"]
        text = update["message"].get("text", "")
        if "/start" in text or "/stats" in text:
            send_message(chat_id, get_stats_text())
        elif "/test" in text:
            send_message(chat_id, "✅ Bot actif et webhook fonctionnel!")

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
