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
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN")
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
PORT = int(os.environ.get("PORT", 10000))
PARIS_TZ = ZoneInfo("Europe/Paris")
ADMIN_KEY = os.environ.get("ADMIN_KEY", "clarisse2026key")

DISCORD_PUBLIC_KEY = os.environ.get("DISCORD_PUBLIC_KEY", "")
_discord_verify_key = VerifyKey(bytes.fromhex(DISCORD_PUBLIC_KEY)) if DISCORD_PUBLIC_KEY else None

DASH_PLATFORM_EMOJI = {"Instagram": "\U0001F4F8", "Facebook": "\U0001F535", "TikTok": "\U0001F3B5"}
DASH_LANG_FLAG = {
    "en": "\U0001F1EC\U0001F1E7", "es": "\U0001F1EA\U0001F1F8", "fr": "\U0001F1EB\U0001F1F7",
    "pt": "\U0001F1E7\U0001F1F7", "tr": "\U0001F1F9\U0001F1F7", "it": "\U0001F1EE\U0001F1F9",
    "de": "\U0001F1E9\U0001F1EA", "ar": "\U0001F1F8\U0001F1E6", "ru": "\U0001F1F7\U0001F1FA",
    "pl": "\U0001F1F5\U0001F1F1", "nl": "\U0001F1F3\U0001F1F1", "unknown": "❓",
}

VA_KEYWORDS = {
    "Mamonj": ["mamonj"],
    "Sediy": ["sediy"],
    "Minosoa": ["minosoa"],
    "TikTok": ["tiktok"],
    "Robert": ["robert"],
    "Wisdom": ["wisdom"],
    "Andy": ["andy"],
}

PLATFORM_KEYWORDS = {
    "Instagram": ["instagram", "insta"],
    "Facebook": ["facebook"],
    "TikTok": ["tiktok"],
}

DATA_FILE = "/data/counts.json"
DAILY_FILE = "/data/daily.json"
SEEN_FILE = "/data/seen_users.json"
PLATFORM_LANG_FILE = "/data/platform_lang.json"

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

def load_platform_lang():
    try:
        if os.path.exists(PLATFORM_LANG_FILE):
            with open(PLATFORM_LANG_FILE, "r") as f:
                raw = json.load(f)
                result = {}
                for date_str, platforms in raw.items():
                    result[date_str] = {p: defaultdict(int, langs) for p, langs in platforms.items()}
                return result
    except Exception as e:
        logger.error(f"Erreur chargement platform_lang: {e}")
    return {}

def save_platform_lang():
    try:
        serializable = {
            date: {p: dict(langs) for p, langs in platforms.items()}
            for date, platforms in platform_lang_counts.items()
        }
        with open(PLATFORM_LANG_FILE, "w") as f:
            json.dump(serializable, f)
        logger.info(f"✅ Sauvegarde platform_lang OK: {serializable}")
    except Exception as e:
        logger.error(f"Erreur sauvegarde platform_lang: {e}")

join_counts = load_counts()
daily_counts = load_daily()
seen_users = load_seen()
platform_lang_counts = load_platform_lang()

def send_message(chat_id, text):
    try:
        r = requests.post(f"{BASE_URL}/sendMessage",
            json={"chat_id": chat_id, "text": text}, timeout=10)
        logger.info(f"sendMessage: {r.status_code}")
    except Exception as e:
        logger.error(f"send_message error: {e}")

def get_stats_text():
    lines = ["📊 Stats joins par VA :\n"]
    for va_name in ["Mamonj", "Sediy", "Minosoa", "TikTok", "Robert", "Wisdom", "Andy"]:
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

def match_platform(norm_name):
    for platform, keywords in PLATFORM_KEYWORDS.items():
        for kw in keywords:
            if kw in norm_name:
                return platform
    return None

def base_lang(code):
    return (code or "unknown").split("-")[0].lower()

def build_dash_message():
    today_str = datetime.now(PARIS_TZ).strftime("%Y-%m-%d")
    day_label = datetime.now(PARIS_TZ).strftime("%d/%m/%Y")
    raw = platform_lang_counts.get(today_str, {})

    grand_total = sum(sum(langs.values()) for langs in raw.values())
    lines = [f"\U0001F4CA **Subs Instagram/Facebook/TikTok du {day_label} : {grand_total} nouveaux abonnes**", ""]

    for platform in ["Instagram", "Facebook", "TikTok"]:
        raw_langs = raw.get(platform, {})
        lang_counts = {}
        for code, count in raw_langs.items():
            lang = base_lang(code)
            lang_counts[lang] = lang_counts.get(lang, 0) + count

        platform_total = sum(lang_counts.values())
        if platform_total == 0:
            continue
        pct = 100 * platform_total / grand_total if grand_total else 0
        emoji = DASH_PLATFORM_EMOJI.get(platform, "")
        lines.append(f"{emoji} **{platform} : {platform_total} subs ({pct:.1f}%)**")
        for lang, count in sorted(lang_counts.items(), key=lambda kv: -kv[1]):
            lang_pct = 100 * count / platform_total if platform_total else 0
            flag = DASH_LANG_FLAG.get(lang, DASH_LANG_FLAG["unknown"])
            lines.append(f"{flag} {lang} : {count} ({lang_pct:.1f}%)")
        lines.append("")

    if grand_total == 0:
        lines.append("_Aucun sub enregistre aujourd'hui pour l'instant._")

    return "\n".join(lines).strip()

def verify_discord_signature(headers, body):
    if not _discord_verify_key:
        return False
    signature = headers.get("X-Signature-Ed25519")
    timestamp = headers.get("X-Signature-Timestamp")
    if not signature or not timestamp:
        return False
    try:
        _discord_verify_key.verify(timestamp.encode() + body, bytes.fromhex(signature))
        return True
    except (BadSignatureError, ValueError):
        return False

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
        language_code = user.get("language_code") or "unknown"
        logger.info(f"chat_join_request — user: {username}, lang: {language_code}, link_name: '{link_name}', repr: {repr(link_name_raw)}")

        dedup_key = f"{chat_id_req}:{user_id}"
        if dedup_key in seen_users:
            logger.warning(f"⚠️ Doublon ignoré: {username} (id {user_id}) a déjà été comptabilisé, requête renvoyée par Telegram")
            return

        norm = normalize_name(link_name_raw)
        va_name = match_va(norm)
        platform = match_platform(norm)

        if not va_name and not platform:
            logger.warning(f"⚠️ Nom de lien non reconnu: '{link_name}' — repr: {repr(link_name_raw)}")
            return

        seen_users.add(dedup_key)
        save_seen()
        today_str = datetime.now(PARIS_TZ).strftime("%Y-%m-%d")

        if va_name:
            join_counts[va_name] += 1
            save_counts()
            if today_str not in daily_counts:
                daily_counts[today_str] = defaultdict(int)
            daily_counts[today_str][va_name] += 1
            save_daily()

        if platform:
            if today_str not in platform_lang_counts:
                platform_lang_counts[today_str] = {}
            if platform not in platform_lang_counts[today_str]:
                platform_lang_counts[today_str][platform] = defaultdict(int)
            platform_lang_counts[today_str][platform][language_code] += 1
            save_platform_lang()

        logger.info(f"✅ Join comptabilisé — va: {va_name or 'n/a'}, platform: {platform or 'n/a'}, lang: {language_code} — jour {today_str}")

class Handler(BaseHTTPRequestHandler):
    def _send_json(self, status, obj):
        payload = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(payload)

    def handle_discord_interaction(self, body):
        if not verify_discord_signature(self.headers, body):
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b"invalid request signature")
            return

        payload = json.loads(body)
        interaction_type = payload.get("type")

        if interaction_type == 1:
            self._send_json(200, {"type": 1})
            return

        if interaction_type == 2 and payload.get("data", {}).get("name") == "dash":
            self._send_json(200, {"type": 4, "data": {"content": build_dash_message()}})
            return

        self._send_json(200, {"type": 4, "data": {"content": "Commande inconnue."}})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)

            if self.path.startswith("/discord-interactions"):
                self.handle_discord_interaction(body)
                return

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
        elif path == "/platform-lang":
            date_str = params.get("date", [""])[0] or datetime.now(PARIS_TZ).strftime("%Y-%m-%d")
            day_data = platform_lang_counts.get(date_str, {})
            serializable = {p: dict(langs) for p, langs in day_data.items()}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"date": date_str, "data": serializable}).encode())
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
