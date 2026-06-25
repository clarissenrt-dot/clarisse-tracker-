import os
import json
import time
import logging
import requests
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
DATA_FILE = "tracking_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"links": {}}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def send_message(chat_id, text):
    requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": text})

def get_invite_link_stats(invite_link):
    """Récupère les stats d'un lien d'invitation via l'API Telegram"""
    try:
        r = requests.post(f"{BASE_URL}/getInviteLink", json={
            "chat_id": CHANNEL_ID,
            "invite_link": invite_link
        })
        result = r.json()
        if result.get("ok"):
            return result["result"].get("member_count", 0)
    except Exception as e:
        logger.error(f"Erreur getInviteLink: {e}")
    return None

def refresh_all_stats():
    """Met à jour les stats de tous les liens depuis l'API Telegram"""
    data = load_data()
    for link_url, info in data["links"].items():
        count = get_invite_link_stats(link_url)
        if count is not None:
            data["links"][link_url]["total_joins"] = count
            logger.info(f"{info['va']}: {count} joins")
    save_data(data)
    return data

def get_updates(offset=None):
    params = {"timeout": 30, "allowed_updates": ["message"]}
    if offset:
        params["offset"] = offset
    try:
        r = requests.get(f"{BASE_URL}/getUpdates", params=params, timeout=35)
        return r.json().get("result", [])
    except:
        return []

def handle_message(message):
    chat_id = message["chat"]["id"]
    text = message.get("text", "")

    if text.startswith("/start"):
        send_message(chat_id,
            "👋 Bot tracking Clarisse actif!\n\n"
            "Commandes:\n"
            "/addlink <nom_va> <lien> — Enregistrer un lien VA\n"
            "/stats — Stats de tous les liens\n"
            "/refresh — Mettre à jour les stats depuis Telegram"
        )

    elif text.startswith("/addlink"):
        parts = text.split()
        if len(parts) < 3:
            send_message(chat_id, "Usage: /addlink <nom_va> <lien_telegram>")
            return
        va_name = parts[1]
        link = parts[2]
        data = load_data()
        data["links"][link] = {
            "va": va_name,
            "total_joins": 0,
            "joins_history": [],
            "created_at": datetime.now().isoformat()
        }
        save_data(data)
        send_message(chat_id, f"✅ Lien enregistré pour {va_name}:\n{link}")

    elif text.startswith("/refresh"):
        send_message(chat_id, "🔄 Mise à jour des stats...")
        data = refresh_all_stats()
        lines = ["📊 Stats mises à jour:\n"]
        for link, info in data["links"].items():
            lines.append(f"👤 {info['va']}: {info['total_joins']} joins")
        send_message(chat_id, "\n".join(lines))

    elif text.startswith("/stats"):
        data = load_data()
        if not data["links"]:
            send_message(chat_id, "Aucun lien enregistré.")
            return
        lines = ["📊 Stats globales:\n"]
        for link, info in data["links"].items():
            lines.append(f"👤 {info['va']}: {info['total_joins']} joins")
        send_message(chat_id, "\n".join(lines))

def main():
    logger.info("Bot démarré...")
    offset = None
    refresh_counter = 0
    while True:
        updates = get_updates(offset)
        for update in updates:
            offset = update["update_id"] + 1
            if "message" in update:
                handle_message(update["message"])
        
        # Auto-refresh toutes les 10 minutes
        refresh_counter += 1
        if refresh_counter >= 600:
            refresh_all_stats()
            refresh_counter = 0
        
        time.sleep(1)

if __name__ == "__main__":
    main()
