import os
import json
import logging
from datetime import datetime
from telegram import Update, ChatMemberUpdated
from telegram.ext import Application, ChatMemberHandler, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")  # ex: -1001234567890

# Stockage en mémoire + fichier JSON
DATA_FILE = "tracking_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"links": {}, "joins": []}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Bot de tracking Clarisse actif!\n\n"
        "Commandes:\n"
        "/addlink <nom_va> <lien> — Enregistrer un lien VA\n"
        "/stats — Voir les stats de tous les liens\n"
        "/stats <nom_va> — Stats d'un VA spécifique"
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
        await update.message.reply_text("Aucun lien enregistré. Utilise /addlink pour en ajouter.")
        return
    
    if context.args:
        va_name = context.args[0]
        lines = [f"📊 Stats pour {va_name}:\n"]
        for link, info in data["links"].items():
            if info["va"].lower() == va_name.lower():
                lines.append(f"🔗 {link}")
                lines.append(f"👥 Total entrées: {info['total_joins']}")
                lines.append(f"📅 Créé le: {info['created_at'][:10]}")
        if len(lines) == 1:
            await update.message.reply_text(f"Aucun lien trouvé pour {va_name}")
        else:
            await update.message.reply_text("\n".join(lines))
    else:
        lines = ["📊 Stats globales:\n"]
        for link, info in data["links"].items():
            lines.append(f"👤 {info['va']}: {info['total_joins']} entrées")
        await update.message.reply_text("\n".join(lines))

async def track_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result: ChatMemberUpdated = update.chat_member
    
    if result is None:
        return
    
    old_status = result.old_chat_member.status
    new_status = result.new_chat_member.status
    
    # Quelqu'un vient de rejoindre
    if old_status in ["left", "kicked"] and new_status == "member":
        invite_link = result.invite_link
        if invite_link:
            link_url = invite_link.invite_link
            data = load_data()
            
            if link_url in data["links"]:
                data["links"][link_url]["total_joins"] += 1
                data["links"][link_url]["joins_history"].append({
                    "user_id": result.new_chat_member.user.id,
                    "username": result.new_chat_member.user.username,
                    "date": datetime.now().isoformat()
                })
                save_data(data)
                va_name = data["links"][link_url]["va"]
                logger.info(f"Nouveau membre via {va_name}: {result.new_chat_member.user.username}")

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
