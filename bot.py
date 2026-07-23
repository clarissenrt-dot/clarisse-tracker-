import os
import json
import logging
import re
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import urlparse, parse_qs
from http.server import HTTPServer, BaseHTTPRequestHandler
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN")
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
PORT = int(os.environ.get("PORT", 10000))
PARIS_TZ = ZoneInfo("Europe/Paris")
ADMIN_KEY = os.environ.get("ADMIN_KEY", "clarisse2026key")

VA_KEYWORDS = {
    "Mamonj": ["mamonj"],
    "Sediy": ["sediy"],
    "Minosoa": ["minosoa"],
    "Insta": ["insta", "facebook"],
    "TikTok": ["tiktok"],
    "Robert": ["robert"],
    "Wisdom": ["wisdom"],
}

DATA_FILE = "/data/counts.json"
DAILY_FILE = "/data/daily.json"
SEEN_FILE = "/data/seen_users.json"

def load_seen():
    try:
        if os.path.exists(SEEN_FILE):
            with open(SEEN_FILE, "r") as f:
                return set(json.load(f))
    except Exception as e:
        logger.error(f"Erreur chargement seen_users: {e}")
    return set()

def save_seen():
    try:
        with open(SEEN_FILE, "w") as f:
            json.dump(list(seen_users), f)
    except Exception as e:
        logger.error(f"Erreur sauvegarde seen_users: {e}")

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

def load_daily():
    # Format : { "2026-07-17": { "Mamonj": 3, "Insta": 1, ... } }
    # Migration douce : si une ancienne date a juste un nombre (ancien format), on la garde
    # telle quelle dans une cle speciale "_total" pour ne rien perdre, mais sans repartition par VA.
    try:
        if os.path.exists(DAILY_FILE):
            with open(DAILY_FILE, "r") as f:
                raw = json.load(f)
                result = {}
                for date_str, val in raw.items():
                    if isinstance(val, dict):
                        result[date_str] = defaultdict(int, val)
                    else:
                        result[date_str] = defaultdict(int, {"_total": val})
                return result
    except Exception as e:
        logger.error(f"Erreur chargement daily: {e}")
    return {}

def save_daily():
    try:
        serializable = {date: dict(vas) for date, vas in daily_counts.items()}
        with open(DAILY_FILE, "w") as f:
            json.dump(serializable, f)
        logger.info(f"✅ Sauvegarde daily OK: {serializable}")
    except Exception as e:
        logger.error(f"Erreur sauvegarde daily: {e}")

join_counts = load_counts()
daily_counts = load_daily()
seen_users = load_seen()

def send_message(chat_id, text):
    try:
        r = requests.post(f"{BASE_URL}/sendMessage",
            json={"chat_id": chat_id, "text": text}, timeout=10)
        logger.info(f"sendMessage: {r.status_code}")
    except Exception as e:
        logger.error(f"send_message error: {e}")

def get_stats_text():
    lines = ["📊 Stats joins par VA :\n"]
    for va_name in ["Mamonj", "Sediy", "Minosoa", "Insta", "TikTok", "Robert", "Wisdom"]:
        count = join_counts.get(va_name, 0)
        lines.append(f"👤 {va_name} : {count} join(s)")
    lines.append(f"\nTotal : {sum(join_counts.values())}")
    return "\n".join(lines)

def normalize_name(name):
    cleaned = re.sub(r"[^\w\s]", "", name, flags=re.UNICODE)
    return re.sub(r"\s+", " ", cleaned).strip().lower()

def match_va(norm_name):
    for va_name, keywords in VA_KEYWORDS.items():
        for kw in keywords:
            if kw in norm_name:
                return va_name
    return None

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
        link_name_raw = invite_link.get("name", "") if invite_link else ""
        link_name = link_name_raw.strip()
        user = req.get("from", {})
        user_id = user.get("id")
        chat_id_req = req.get("chat", {}).get("id")
        username = user.get("username", "inconnu")
        logger.info(f"chat_join_request — user: {username}, link_name: '{link_name}', repr: {repr(link_name_raw)}")

        dedup_key = f"{chat_id_req}:{user_id}"
        if dedup_key in seen_users:
            logger.warning(f"⚠️ Doublon ignoré: {username} (id {user_id}) a déjà été comptabilisé, requête renvoyée par Telegram")
            return

        norm = normalize_name(link_name_raw)
        va_name = match_va(norm)
        if va_name:
            seen_users.add(dedup_key)
            save_seen()
            join_counts[va_name] += 1
            save_counts()
            today_str = datetime.now(PARIS_TZ).strftime("%Y-%m-%d")
            if today_str not in daily_counts:
                daily_counts[today_str] = defaultdict(int)
            daily_counts[today_str][va_name] += 1
            save_daily()
            logger.info(f"✅ Join comptabilisé pour {va_name} — total: {join_counts[va_name]} — jour {today_str}: {dict(daily_counts[today_str])}")
        else:
            logger.warning(f"⚠️ Nom de lien non reconnu: '{link_name}' — repr: {repr(link_name_raw)}")

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
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == "/counts":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(dict(join_counts)).encode())
        elif path == "/history":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            serializable = {date: dict(vas) for date, vas in daily_counts.items()}
            self.wfile.write(json.dumps(serializable).encode())
        elif path == "/adjust":
            key = params.get("key", [""])[0]
            if key != ADMIN_KEY:
                self.send_response(403)
                self.end_headers()
                self.wfile.write(b"Forbidden")
                return
            date_str = params.get("date", [""])[0]
            va_name = params.get("va", [""])[0]
            try:
                amount = int(params.get("amount", ["0"])[0])
            except ValueError:
                amount = 0
            if not date_str or amount == 0:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Usage: /adjust?date=YYYY-MM-DD&amount=14&va=TikTok&key=...")
                return
            if date_str not in daily_counts:
                daily_counts[date_str] = defaultdict(int)
            if va_name:
                daily_counts[date_str][va_name] += amount
                join_counts[va_name] += amount
                save_counts()
            else:
                daily_counts[date_str]["_total"] += amount
            save_daily()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            result = {"date": date_str, "amount": amount, "va": va_name or None,
                      "daily_total_that_day": sum(daily_counts[date_str].values())}
            self.wfile.write(json.dumps(result).encode())
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
