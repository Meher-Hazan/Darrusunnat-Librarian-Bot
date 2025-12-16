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

# --- CONFIGURATION ---
BOT_TOKEN = os.getenv("BOT_TOKEN") 
DATA_URL = "https://raw.githubusercontent.com/Meher-Hazan/Darrusunnat-PDF-Library/main/books_data.json"
# ⚠️ REPLACE THIS WITH YOUR RENDER URL
RENDER_URL = "https://library-bot-amuk.onrender.com" 

BOOK_NAME_KEY = "title"
BOOK_LINK_KEY = "link"

# --- SMART SYNONYM DICTIONARY (English -> Bangla) ---
# This makes the bot understand meaning, not just letters.
SYNONYMS = {
    "biography": "jiboni",
    "history": "itihas",
    "prayer": "namaz",
    "fasting": "roza",
    "prophet": "nabi",
    "messenger": "rasul",
    "life": "jibon",
    "rules": "masala",
    "dream": "shopno",
    "women": "nari",
    "paradise": "jannat",
    "hell": "jahannam"
}

# --- PART 1: FAKE SERVER & SELF-PING (Keep Alive) ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.wfile.write(b"Einstein Bot is Active")

def start_server():
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(("0.0.0.0", port), SimpleHandler).serve_forever()

def keep_alive():
    while True:
        time.sleep(600) # Ping every 10 mins
        try:
            requests.get(RENDER_URL)
            print("Self-ping successful.")
        except:
            pass

# --- PART 2: INTELLIGENCE ENGINE ---
logging.basicConfig(level=logging.INFO)
BOOKS_DB = []
SEARCH_INDEX = {}

def smart_clean(text):
    """
    Advanced Cleaner: Handles synonyms, removes junk, normalizes text.
    """
    if not text: return ""
    text = text.lower()
    
    # 1. Remove file extensions & symbols
    text = text.replace(".pdf", "").replace("_", " ").replace("-", " ")
    text = re.sub(r'[^\w\s]', '', text) # Remove punctuation
    text = re.sub(r'\d+', '', text)    # Remove numbers
    
    # 2. Split into words
    words = text.split()
    
    # 3. Filter Junk Words & Apply Synonyms
    clean_words = []
    stop_words = {"pdf", "book", "link", "download", "dao", "chai", "plz", "admin", "er", "ar", "boi", "the"}
    
    for w in words:
        if w in stop_words: continue
        # Check if it's an English word with a Bangla synonym
        if w in SYNONYMS:
            clean_words.append(SYNONYMS[w]) # Use the Bangla version
        else:
            clean_words.append(w)
            
    return " ".join(clean_words)

def fetch_books():
    """Loads and Indexes books with the Smart Cleaner"""
    global BOOKS_DB, SEARCH_INDEX
    try:
        print("Downloading Library...")
        resp = requests.get(DATA_URL)
        if resp.status_code == 200:
            BOOKS_DB = resp.json()
            SEARCH_INDEX = {}
            for book in BOOKS_DB:
                raw_name = book.get(BOOK_NAME_KEY, "")
                # We store TWO versions: 
                # 1. The Clean Searchable Name
                # 2. The Original Book Object
                clean_name = smart_clean(raw_name)
                if clean_name:
                    SEARCH_INDEX[clean_name] = book
            print(f"Brain loaded with {len(SEARCH_INDEX)} books.")
        else:
            print("Failed to download database.")
    except Exception as e:
        print(f"Error: {e}")

# --- PART 3: THE SEARCH LOGIC (The "Brain") ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    
    query = smart_clean(update.message.text)
    if len(query) < 3: return # Ignore short junk

    clean_titles = list(SEARCH_INDEX.keys())
    if not clean_titles: return

    # --- LEVEL 1: STRICT TOKEN SEARCH (The "Librarian") ---
    # This looks for EXACT word matches (e.g. "Iman" matches "Iman", not "Biman")
    strict_matches = []
    query_tokens = set(query.split())
    
    for title in clean_titles:
        title_tokens = set(title.split())
        # Check if ALL query words exist in the title
        if query_tokens.issubset(title_tokens):
            strict_matches.append((title, 100)) # Perfect score
            
    # --- LEVEL 2: FUZZY SEARCH (The "Guesser") ---
    # Only run this to fill up the list or if strict search failed
    fuzzy_matches = process.extract(
        query, 
        clean_titles, 
        scorer=fuzz.token_sort_ratio, 
        limit=5
    )
    
    # COMBINE RESULTS (Strict first, then Fuzzy)
    # We prioritize strict matches.
    final_results = strict_matches
    
    # Add fuzzy matches if they are good (>70) and not already in the list
    existing_titles = [m[0] for m in final_results]
    for title, score in fuzzy_matches:
        if score > 70 and title not in existing_titles:
            final_results.append((title, score))
            
    if not final_results: return

    # --- PART 4: SMART DISPLAY ---
    top_match = final_results[0]
    
    # If the best match is super strong (>85), show it instantly
    if top_match[1] > 85:
        book = SEARCH_INDEX[top_match[0]]
        title = book.get(BOOK_NAME_KEY, "Book")
        link = book.get(BOOK_LINK_KEY, "#")
        
        kb = [[InlineKeyboardButton("📥 Download PDF", url=link)]]
        await update.message.reply_text(
            f"✅ **Best Match:**\n📖 `{title}`", 
            reply_markup=InlineKeyboardMarkup(kb), 
            parse_mode="Markdown"
        )
        return

    # Otherwise, show a list
    kb = []
    # Show max 3 relevant results
    for title, score in final_results[:3]:
        book = SEARCH_INDEX[title]
        real_title = book.get(BOOK_NAME_KEY, "Book")
        link = book.get(BOOK_LINK_KEY, "#")
        # Smart Truncate: Keep title short for the button
        display_name = (real_title[:35] + '..') if len(real_title) > 35 else real_title
        kb.append([InlineKeyboardButton(f"📖 {display_name}", url=link)])

    await update.message.reply_text(
        f"🤔 **Did you mean one of these?**", 
        reply_markup=InlineKeyboardMarkup(kb)
    )

if __name__ == '__main__':
    # Initialize components
    threading.Thread(target=start_server, daemon=True).start()
    threading.Thread(target=keep_alive, daemon=True).start()
    fetch_books()
    
    if BOT_TOKEN:
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
        print("Einstein Bot is Live...")
        app.run_polling()
    else:
        print("Error: No Token Found") 
