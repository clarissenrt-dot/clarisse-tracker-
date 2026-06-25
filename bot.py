import os
import json
import time
import logging
import requests
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN")
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

def get_updates(offset=None):
    params = {"timeout": 30, "allowed_updates": ["message", "chat_member"]}
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
            "/stats — Stats de tous les liens"
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
    
    elif text.startswith("/stats"):
        data = load_data()
        if not data["links"]:
            send_message(chat_id, "Aucun lien enregistré.")
            return
        lines = ["📊 Stats globales:\n"]
        for link, info in data["links"].items():
            lines.append(f"👤 {info['va']}: {info['total_joins']} entrées totales")
        send_message(chat_id, "\n".join(lines))

def handle_chat_member(update):
    result = update.get("chat_member", {})
    old_status = result.get("old_chat_member", {}).get("status", "")
    new_status = result.get("new_chat_member", {}).get("status", "")
    
    if old_status in ["left", "kicked"] and new_status == "member":
        invite_link = result.get("invite_link", {})
        if invite_link:
            link_url = invite_link.get("invite_link", "")
            data = load_data()
            if link_url in data["links"]:
                data["links"][link_url]["total_joins"] += 1
                data["links"][link_url]["joins_history"].append({
                    "user_id": result.get("new_chat_member", {}).get("user", {}).get("id"),
                    "date": datetime.now().isoformat()
                })
                save_data(data)
                va_name = data["links"][link_url]["va"]
                logger.info(f"Nouveau membre via {va_name}")

def main():
    logger.info("Bot démarré...")
    offset = None
    while True:
        updates = get_updates(offset)
        for update in updates:
            offset = update["update_id"] + 1
            if "message" in update:
                handle_message(update["message"])
            if "chat_member" in update:
                handle_chat_member(update)
        time.sleep(1)

if __name__ == "__main__":
    main()
