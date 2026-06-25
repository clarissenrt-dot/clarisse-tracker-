import os
import json
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import Application, ChatMemberHandler, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN")
DATA_FILE = "tracking_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"links": {}}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Bot tracking Clarisse actif!\n\n"
        "Commandes:\n"
        "/addlink <nom_va> <lien> — Enregistrer un lien VA\n"
        "/stats — Stats de tous les liens\n"
    )

async def addlink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /addlink <nom_va> <lien_telegram>")
        return
    va_name = context.args[0]
    link = context.args[1]
    data = load_data()
    data["links"][link] = {
        "va": va_name,
        "total_joins": 0,
        "joins_history": [],
        "created_at": datetime.now().isoformat()
    }
    save_data(data)
    await update.message.reply_text(f"✅ Lien enregistré pour {va_name}:\n{link}")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    if not data["links"]:
        await update.message.reply_text("Aucun lien enregistré.")
        return
    lines = ["📊 Stats globales:\n"]
    for link, info in data["links"].items():
        lines.append(f"👤 {info['va']}: {info['total_joins']} entrées totales")
    await update.message.reply_text("\n".join(lines))

async def track_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.chat_member
    if result is None:
        return
    old_status = result.old_chat_member.status
    new_status = result.new_chat_member.status
    if old_status in ["left", "kicked"] and new_status == "member":
        invite_link = result.invite_link
        if invite_link:
            link_url = invite_link.invite_link
            data = load_data()
            if link_url in data["links"]:
                data["links"][link_url]["total_joins"] += 1
                data["links"][link_url]["joins_history"].append({
                    "user_id": result.new_chat_member.user.id,
                    "date": datetime.now().isoformat()
                })
                save_data(data)
                va_name = data["links"][link_url]["va"]
                logger.info(f"Nouveau membre via {va_name}")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addlink", addlink))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(ChatMemberHandler(track_member, ChatMemberHandler.CHAT_MEMBER))
    logger.info("Bot démarré...")
    app.run_polling(allowed_updates=["chat_member", "message"])

if __name__ == "__main__":
    main()
