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
TMDB_API_KEY = os.environ.get("TMDB_API_KEY")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "🎬 **All-In-One Movie & Streaming Bot**\n\n"
        "Je movie joiye tenu name lakhi ne moklo.\n"
        "Ex: `Inception`, `Avatar`, athva `Golmaal`"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

def search_yts(query: str):
    try:
        url = f"https://yts.mx/api/v2/list_movies.json?query_term={query}&limit=1"
        res = requests.get(url, timeout=10).json()
        if res.get("status") == "ok" and res.get("data", {}).get("movie_count", 0) > 0:
            movie = res["data"]["movies"][0]
            return {
                "title": movie.get("title_long", query),
                "cover": movie.get("large_cover_image"),
                "rating": movie.get("rating", "N/A"),
                "torrents": movie.get("torrents", [])
            }
    except Exception as e:
        print(f"YTS Error: {e}")
    return None

def search_tmdb(query: str):
    if not TMDB_API_KEY:
        return None
    try:
        url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={query}"
        res = requests.get(url, timeout=10).json()
        if not res.get("results"):
            return None
        movie = res["results"][0]
        movie_id = movie["id"]

        watch_url = f"https://api.themoviedb.org/3/movie/{movie_id}/watch/providers?api_key={TMDB_API_KEY}"
        watch_res = requests.get(watch_url, timeout=10).json()
        in_providers = watch_res.get("results", {}).get("IN", {})

        return {
            "title": movie.get("title"),
            "rating": movie.get("vote_average", "N/A"),
            "poster": f"https://image.tmdb.org/t/p/w500{movie.get('poster_path')}" if movie.get("poster_path") else None,
            "streams": in_providers.get("ads", []) + in_providers.get("flatrate", []),
            "tmdb_url": in_providers.get("link")
        }
    except Exception as e:
        print(f"TMDB Error: {e}")
        return None

def search_archive(query: str):
    try:
        url = f"https://archive.org/advancedsearch.php?q={query}+AND+mediatype:movies&fl[]=identifier,title&rows=1&output=json"
        res = requests.get(url, timeout=10).json()
        docs = res.get("response", {}).get("docs", [])
        if docs:
            ident = docs[0]["identifier"]
            return f"https://archive.org/details/{ident}"
    except Exception as e:
        print(f"Archive Error: {e}")
    return None

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    wait_msg = await update.message.reply_text(f"🔍 `{query}` mate direct downloads ane streaming links shodhie chhiye...", parse_mode="Markdown")

    yts_data = search_yts(query)
    tmdb_data = search_tmdb(query)
    archive_link = search_archive(query)

    keyboard = []

    if yts_data and yts_data.get("torrents"):
        for t in yts_data["torrents"]:
            q = t.get("quality", "HD")
            size = t.get("size", "")
            link = t.get("url", "")
            keyboard.append([InlineKeyboardButton(f"📥 Direct Download {q} ({size})", url=link)])

    if tmdb_data and tmdb_data.get("streams"):
        for provider in tmdb_data["streams"][:2]:
            p_name = provider.get("provider_name", "Stream")
            link = tmdb_data.get("tmdb_url") or "https://www.themoviedb.org"
            keyboard.append([InlineKeyboardButton(f"▶️ Watch on {p_name}", url=link)])

    if archive_link:
        keyboard.append([InlineKeyboardButton("🌐 Free Public Stream / Download (Archive)", url=archive_link)])

    yt_url = f"https://www.youtube.com/results?search_query={query}+full+movie"
    keyboard.append([InlineKeyboardButton("🎬 Search Full Movie on YouTube", url=yt_url)])

    if not keyboard:
        await wait_msg.edit_text(f"❌ `{query}` mate koi links mali nathi. Spelling check karo.")
        return

    markup = InlineKeyboardMarkup(keyboard)

    title = yts_data["title"] if yts_data else (tmdb_data["title"] if tmdb_data else query)
    rating = yts_data["rating"] if yts_data else (tmdb_data["rating"] if tmdb_data else "N/A")
    poster = yts_data["cover"] if (yts_data and yts_data.get("cover")) else (tmdb_data["poster"] if tmdb_data else None)

    caption = (
        f"🎬 **{title}**\n"
        f"⭐ Rating: {rating}/10\n\n"
        f"Niche aapela options mathi download athva stream karo:"
    )

    if poster:
        await update.message.reply_photo(photo=poster, caption=caption, reply_markup=markup, parse_mode="Markdown")
        await wait_msg.delete()
    else:
        await wait_msg.edit_text(caption, reply_markup=markup, parse_mode="Markdown")

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    print("[*] All-in-one Movie Bot Running...")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    app.run_polling()