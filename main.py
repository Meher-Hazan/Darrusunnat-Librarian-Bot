import logging
import os
import requests
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from thefuzz import process, fuzz

# --- CONFIGURATION ---
BOT_TOKEN = os.getenv("BOT_TOKEN") 
DATA_URL = "https://raw.githubusercontent.com/Meher-Hazan/Darrusunnat-PDF-Library/main/books_data.json"
BOOK_NAME_KEY = "title"
BOOK_LINK_KEY = "link"

# --- LOGIC ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# GLOBAL VARIABLES
BOOKS_DB = []
SEARCH_INDEX = {} # This will hold the "Cleaned" names mapping to Real Books

def normalize_text(text):
    """
    MASTER CLEANER: Removes numbers, underscores, extensions, and Bangla junk words.
    Input: "6427_Iman_er_Shakhaprosakha.pdf"
    Output: "iman shakhaprosakha"
    """
    if not text: return ""
    
    # 1. Convert to Lowercase
    text = text.lower()
    
    # 2. Remove File Extensions (.pdf)
    text = text.replace(".pdf", "")
    
    # 3. Replace Underscores and Hyphens with Spaces
    text = text.replace("_", " ").replace("-", " ")
    
    # 4. Remove Numbers (The IDs at start of filenames)
    # This removes "6427" so matches focus on the NAME
    text = re.sub(r'\d+', '', text)
    
    # 5. Remove Bangla & English Stop Words
    # (Words people type but aren't part of the book name)
    stop_words = [
        # English / Banglish
        "pdf", "book", "link", "download", "dao", "chai", "plz", "admin", "er",
        # Bangla Script (CRITICAL)
        "বই", "এর", "পিডিএফ", "লিংক", "দাও", "চাই", "আছে", "কি", "সাহায্য", "করুন", "ভাই", "প্লিজ"
    ]
    
    for word in stop_words:
        text = re.sub(r'\b' + word + r'\b', '', text)
    
    # 6. Remove Extra Spaces
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

# Fetch and Build Index on Startup
try:
    print("Fetching and Indexing Library...")
    response = requests.get(DATA_URL)
    if response.status_code == 200:
        BOOKS_DB = response.json()
        
        # BUILD THE BRAIN (SEARCH INDEX)
        # We create a dictionary where keys are "Clean Names" and values are "Real Book Objects"
        SEARCH_INDEX = {}
        for book in BOOKS_DB:
            raw_title = book.get(BOOK_NAME_KEY, "")
            clean_title = normalize_text(raw_title)
            if clean_title:
                # Store the mapping
                SEARCH_INDEX[clean_title] = book
                
        print(f"Indexed {len(SEARCH_INDEX)} books for smart search.")
    else:
        print("Failed to load books.")
except Exception as e:
    print(f"Error: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    # 1. CLEAN THE USER'S QUERY
    user_text = update.message.text
    cleaned_query = normalize_text(user_text)
    
    # Ignore if query is empty or too short (just "hi" or "dao")
    if len(cleaned_query) < 2:
        return

    # 2. SEARCH (Compare Clean Query vs Clean Index)
    # We search against the keys of SEARCH_INDEX (the nice, clean names)
    clean_titles = list(SEARCH_INDEX.keys())
    
    if not clean_titles:
        return

    # Use WRatio (Weighted Ratio) - It handles partial matches very well
    matches = process.extract(cleaned_query, clean_titles, scorer=fuzz.WRatio, limit=5)

    # 3. FILTER BAD MATCHES
    # Since we cleaned data, matches should be high. We set threshold to 75.
    valid_matches = [m for m in matches if m[1] > 75]

    if not valid_matches:
        return 

    # 4. SMART REPLY
    best_clean_name, best_score = valid_matches[0]
    
    # Retrieve the REAL book data using the clean name key
    best_book_obj = SEARCH_INDEX[best_clean_name]
    real_title = best_book_obj.get(BOOK_NAME_KEY, "Unknown Title")
    link = best_book_obj.get(BOOK_LINK_KEY, "#")

    # A. EXACT/STRONG MATCH (90%+)
    if best_score > 90:
        keyboard = [[InlineKeyboardButton("📥 Download PDF", url=link)]]
        await update.message.reply_text(
            f"✅ **বইটি খুঁজে পেয়েছি!** (Found it)\n\n📖 {real_title}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return

    # B. SUGGESTIONS (75% - 90%)
    keyboard = []
    for clean_name, score in valid_matches[:3]:
        # Only show if score is reasonable
        if score > (best_score - 10): 
            book_obj = SEARCH_INDEX[clean_name]
            r_title = book_obj.get(BOOK_NAME_KEY, "Book")
            r_link = book_obj.get(BOOK_LINK_KEY, "#")
            
            # Button Text: Truncate if too long to fit
            btn_text = (r_title[:30] + '..') if len(r_title) > 30 else r_title
            keyboard.append([InlineKeyboardButton(f"📖 {btn_text}", url=r_link)])

    if keyboard:
        await update.message.reply_text(
            f"🔍 **আপনি কি এই বইগুলোর একটি খুঁজছেন?**\n(Did you mean one of these?)",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

if __name__ == '__main__':
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN is missing! Check Render Environment Variables.")
    else:
        application = ApplicationBuilder().token(BOT_TOKEN).build()
        echo_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)
        application.add_handler(echo_handler)
        print("Bangla Smart Bot Running...")
        application.run_polling()
