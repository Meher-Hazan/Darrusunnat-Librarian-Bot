import os

# 1. SECURITY
# Load Token from Render Environment (Secure)
BOT_TOKEN = os.getenv("BOT_TOKEN") 
# Your Book Database URL
DATA_URL = "https://raw.githubusercontent.com/Meher-Hazan/Darrusunnat-PDF-Library/main/books_data.json"
# Your Render URL (For self-pinging)
RENDER_URL = "https://library-bot-amuk.onrender.com"

# 2. SYNONYMS (The "Translator")
# English -> Bangla concepts
SYNONYMS = {
    "biography": "jiboni", "history": "itihas", "prayer": "namaz",
    "fasting": "roza", "prophet": "nabi", "messenger": "rasul",
    "life": "jibon", "rules": "masala", "dream": "shopno",
    "women": "nari", "paradise": "jannat", "hell": "jahannam",
    "vol": "khondo", "part": "part"
}

# 3. BAD WORDS (For Admin Police)
BAD_WORDS = [
    "scam", "bitcoin", "investment", "crypto", "sex", "porn", "xxx", 
    "fucker", "bitch", "whore", "asshole", "casino", "betting",
    # Bangla
    "কুত্তা", "হারামি", "সোনা", "বাল", "চুদ", "খানকি", "মাগি"
]

# 4. STOP WORDS (Junk words to remove before searching)
STOP_WORDS = {
    "pdf", "book", "link", "download", "dao", "chai", "plz", "admin", "er", "ar", "boi", 
    "the", "please", "give", "me", "koto", "dam", "ace", "ase", "ki",
    "বই", "এর", "পিডিএফ", "লিংক", "দাও", "চাই", "আছে", "কি", "সাহায্য", "করুন", "ভাই", "প্লিজ"
}
