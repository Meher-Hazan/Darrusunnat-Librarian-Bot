import os

# --- SECURITY ---
BOT_TOKEN = os.getenv("BOT_TOKEN") 
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

DATA_URL = "https://raw.githubusercontent.com/Meher-Hazan/Darrusunnat-PDF-Library/main/books_data.json"
RENDER_URL = "https://library-bot-amuk.onrender.com" 

# --- ADMIN SETTINGS ---
ADMIN_ID = 123456789  
GROUP_ID = -1001234567890 

# TIMERS
RANDOM_BOOK_INTERVAL = 14400 
DB_REFRESH_INTERVAL = 1800

# JSON KEYS
KEY_TITLE = "title"
KEY_LINK = "link"
KEY_IMAGE = "image"

# --- FILES ---
STATS_FILE = "stats.json"
USERS_FILE = "user_database.json"

# --- LISTS ---
SYNONYMS = {
    "biography": "jiboni", "history": "itihas", "prayer": "namaz",
    "fasting": "roza", "prophet": "nabi", "messenger": "rasul",
    "life": "jibon", "rules": "masala", "dream": "shopno",
    "women": "nari", "paradise": "jannat", "hell": "jahannam",
    "vol": "khondo", "part": "part"
}

BAD_WORDS = [
    "scam", "bitcoin", "investment", "crypto", "sex", "porn", "xxx", 
    "fucker", "bitch", "whore", "asshole", "casino", "betting",
    "signals", "pump", "trading", "traders", "profit", "giveaway",
    "doubling", "airdrop", "presale", "elon", "musk", "saylor",
    "shiba", "doge", "forex", "binary", "binance", "coinbase",
    "join now", "join here", "click here", "dm me", "inbox me",
    "investment plan", "make money",
    "কুত্তা", "হারামি", "সোনা", "বাল", "চুদ", "খানকি", "মাগি",
    "ল্যাংটা", "চুদির", "বোকাচোদা"
]

STOP_WORDS = {
    "pdf", "book", "link", "download", "dao", "chai", "plz", "admin", "er", "ar", "boi", 
    "the", "please", "give", "me", "koto", "dam", "ace", "ase", "ki",
    "বই", "এর", "পিডিএফ", "লিংক", "দাও", "চাই", "আছে", "কি", "সাহায্য", "করুন", "ভাই", "প্লিজ"
}
