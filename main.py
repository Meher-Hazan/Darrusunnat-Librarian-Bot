import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CallbackQueryHandler, filters
from thefuzz import process, fuzz

# --- CONFIGURATION ---
BOT_TOKEN = "8431621681:AAEfrtw9mvHIazZaZUZtjWEGRoavXfmCisk"
DATA_URL = "https://raw.githubusercontent.com/Meher-Hazan/Darrusunnat-PDF-Library/main/books_data.json"
BOOK_NAME_KEY = "title"
BOOK_LINK_KEY = "link"

# --- LOGIC ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Fetch books on startup
try:
    print("Fetching book database...")
    response = requests.get(DATA_URL)
    if response.status_code == 200:
        BOOKS_DB = response.json()
        print(f"Loaded {len(BOOKS_DB)} books.")
    else:
        BOOKS_DB = []
except Exception as e:
    BOOKS_DB = []
    print(f"Error: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_text = update.message.text.lower().strip()
    
    # IGNORE very short messages (e.g. "hi", "salam", "ok", "boi")
    if len(user_text) < 4:
        return

    # Prepare titles
    book_map = {b[BOOK_NAME_KEY]: b for b in BOOKS_DB if b.get(BOOK_NAME_KEY)}
    titles = list(book_map.keys())
    
    if not titles:
        return

    # --- INTELLIGENT SEARCH ---
    # We use 'token_sort_ratio' instead of 'token_set_ratio'.
    # Why? 'token_set' matches partial words (like "er") giving 100% score.
    # 'token_sort' forces the bot to match the MAIN words of the book.
    matches = process.extract(user_text, titles, scorer=fuzz.token_sort_ratio, limit=5)

    # Filter: Only keep matches with score > 65
    valid_matches = [m for m in matches if m[1] > 65]

    if not valid_matches:
        return # Silence if no good match found

    # --- INTERACTIVE REPLY ---
    
    # 1. PERFECT MATCH (Confidence > 88)
    # If we are super sure, just give the button immediately.
    best_match = valid_matches[0]
    if best_match[1] > 88:
        book = book_map[best_match[0]]
        link = book.get(BOOK_LINK_KEY, "#")
        
        keyboard = [[InlineKeyboardButton("📥 Download PDF", url=link)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ **Found it!**\n\n📖 {best_match[0]}",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        return

    # 2. MAYBE MATCH (Confidence 65-88)
    # Give the user a choice.
    keyboard = []
    for name, score in valid_matches[:3]: # Show top 3 options
        book = book_map[name]
        link = book.get(BOOK_LINK_KEY, "#")
        # Button label: Book Title
        keyboard.append([InlineKeyboardButton(f"📖 {name}", url=link)])

    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🤔 **Did you mean one of these?**",
        reply_markup=reply_markup
    )

if __name__ == '__main__':
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Handle text messages
    echo_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)
    application.add_handler(echo_handler)
    
    print("Bot is restarting and listening...")
    application.run_polling()

