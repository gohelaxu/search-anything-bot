import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "🎬 **Search Anything Bot**\n\n"
        "Je movie joiye tenu name lakhi ne moklo.\n"
        "Ex: `Inception` athva `Avatar`"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

def search_movie(query: str):
    url = f"https://yts.mx/api/v2/list_movies.json?query_term={query}&limit=1"
    try:
        res = requests.get(url, timeout=10)
        data = res.json()
        if data.get("status") == "ok" and data.get("data", {}).get("movie_count", 0) > 0:
            movie = data["data"]["movies"][0]
            return {
                "found": True,
                "title": movie.get("title_long", query),
                "cover": movie.get("large_cover_image"),
                "rating": movie.get("rating", "N/A"),
                "torrents": movie.get("torrents", [])
            }
    except Exception as e:
        print(f"Error: {e}")
    return {"found": False}

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    wait_msg = await update.message.reply_text(f"🔍 `{query}` mate links shodhie chhiye...", parse_mode="Markdown")

    data = search_movie(query)
    if not data["found"]:
        await wait_msg.edit_text(f"❌ `{query}` ni direct link mali nathi. Spelling check karo.")
        return

    keyboard = []
    for t in data["torrents"]:
        q = t.get("quality", "HD")
        size = t.get("size", "")
        link = t.get("url", "")
        keyboard.append([InlineKeyboardButton(f"📥 {q} ({size})", url=link)])

    markup = InlineKeyboardMarkup(keyboard)
    caption = f"🎬 **{data['title']}**\n⭐ Rating: {data['rating']}/10\n\nDownload karva mate quality select karo:"

    if data.get("cover"):
        await update.message.reply_photo(photo=data["cover"], caption=caption, reply_markup=markup, parse_mode="Markdown")
        await wait_msg.delete()
    else:
        await wait_msg.edit_text(caption, reply_markup=markup, parse_mode="Markdown")

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    print("[*] Starting Search Anything Bot...")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    app.run_polling()
