import logging
import os
import requests
import re
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from rapidfuzz import process, fuzz, utils

# IMPORT THE ADMIN MODULE
import group_admin 

# --- CONFIGURATION ---
BOT_TOKEN = os.getenv("BOT_TOKEN") 
DATA_URL = "https://raw.githubusercontent.com/Meher-Hazan/Darrusunnat-PDF-Library/main/books_data.json"
# ⚠️ MAKE SURE THIS IS YOUR RENDER URL
RENDER_URL = "https://library-bot-amuk.onrender.com" 

BOOK_NAME_KEY = "title"
BOOK_LINK_KEY = "link"

SYNONYMS = {
    "biography": "jiboni", "history": "itihas", "prayer": "namaz",
    "fasting": "roza", "prophet": "nabi", "messenger": "rasul",
    "life": "jibon", "rules": "masala", "dream": "shopno",
    "women": "nari", "paradise": "jannat", "hell": "jahannam"
}

# --- PART 1: SERVER & PING ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.wfile.write(b"Einstein Bot is Active")

def start_server():
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(("0.0.0.0", port), SimpleHandler).serve_forever()

def keep_alive():
    while True:
        time.sleep(600)
        try:
            requests.get(RENDER_URL)
        except:
            pass

# --- PART 2: LOADING ---
logging.basicConfig(level=logging.INFO)
BOOKS_DB = []
SEARCH_INDEX = {}

def smart_clean(text):
    if not text: return ""
    text = text.lower()
    text = text.replace(".pdf", "").replace("_", " ").replace("-", " ")
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\d+', '', text)
    words = text.split()
    clean_words = []
    stop_words = {"pdf", "book", "link", "download", "dao", "chai", "plz", "admin", "er", "ar", "boi", "the"}
    for w in words:
        if w in stop_words: continue
        if w in SYNONYMS: clean_words.append(SYNONYMS[w])
        else: clean_words.append(w)
    return " ".join(clean_words)

def fetch_books():
    global BOOKS_DB, SEARCH_INDEX
    try:
        print("Downloading Library...")
        resp = requests.get(DATA_URL)
        if resp.status_code == 200:
            BOOKS_DB = resp.json()
            SEARCH_INDEX = {}
            for book in BOOKS_DB:
                raw_name = book.get(BOOK_NAME_KEY, "")
                clean_name = smart_clean(raw_name)
                if clean_name:
                    SEARCH_INDEX[clean_name] = book
            print(f"Brain loaded with {len(SEARCH_INDEX)} books.")
        else:
            print("Failed to download database.")
    except Exception as e:
        print(f"Error: {e}")

# --- PART 3: MAIN LOGIC ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # SECURITY CHECK
    if await group_admin.check_and_moderate(update, context):
        return 

    if not update.message or not update.message.text: return
    
    query = smart_clean(update.message.text)
    if len(query) < 3: return 

    clean_titles = list(SEARCH_INDEX.keys())
    if not clean_titles: return

    # STRICT SEARCH
    strict_matches = []
    query_tokens = set(query.split())
    for title in clean_titles:
        title_tokens = set(title.split())
        if query_tokens.issubset(title_tokens):
            strict_matches.append((title, 100))
            
    # FUZZY SEARCH
    # RapidFuzz returns (Title, Score, Index). We use limit=5
    fuzzy_results = process.extract(query, clean_titles, scorer=fuzz.token_sort_ratio, limit=5)
    
    final_results = strict_matches
    existing_titles = [m[0] for m in final_results]
    
    # --- BUG FIX IS HERE ---
    # We ignore the 3rd value (_) which caused the crash
    for title, score, _ in fuzzy_results:
        if score > 70 and title not in existing_titles:
            final_results.append((title, score))
            
    if not final_results: return

    # DISPLAY
    top_match = final_results[0]
    if top_match[1] > 85:
        book = SEARCH_INDEX[top_match[0]]
        title = book.get(BOOK_NAME_KEY, "Book")
        link = book.get(BOOK_LINK_KEY, "#")
        kb = [[InlineKeyboardButton("📥 Download PDF", url=link)]]
        await update.message.reply_text(f"✅ **Best Match:**\n📖 `{title}`", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
        return

    kb = []
    for title, score in final_results[:3]:
        book = SEARCH_INDEX[title]
        real_title = book.get(BOOK_NAME_KEY, "Book")
        link = book.get(BOOK_LINK_KEY, "#")
        display_name = (real_title[:35] + '..') if len(real_title) > 35 else real_title
        kb.append([InlineKeyboardButton(f"📖 {display_name}", url=link)])

    await update.message.reply_text(f"🤔 **Did you mean one of these?**", reply_markup=InlineKeyboardMarkup(kb))

if __name__ == '__main__':
    threading.Thread(target=start_server, daemon=True).start()
    threading.Thread(target=keep_alive, daemon=True).start()
    fetch_books()
    
    if BOT_TOKEN:
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
        print("Einstein Admin Bot is Live...")
        app.run_polling()
    else:
        print("Error: No Token Found")
