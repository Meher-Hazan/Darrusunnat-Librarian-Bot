import requests
import re
from rapidfuzz import process, fuzz
from modules.config import DATA_URL, SYNONYMS, STOP_WORDS

BOOKS_DB = []
SEARCH_INDEX = {}

def clean_query(text):
    if not text: return ""
    text = text.lower()
    text = text.replace(".pdf", "").replace("_", " ").replace("-", " ")
    text = re.sub(r'[^\w\s]', '', text) 
    text = re.sub(r'\d+', '', text)    
    
    words = text.split()
    meaningful_words = []
    
    for w in words:
        if w in STOP_WORDS: continue
        if w in SYNONYMS: 
            meaningful_words.append(SYNONYMS[w])
        else:
            meaningful_words.append(w)
            
    return " ".join(meaningful_words)

def refresh_database():
    global BOOKS_DB, SEARCH_INDEX
    try:
        resp = requests.get(DATA_URL)
        if resp.status_code == 200:
            BOOKS_DB = resp.json()
            SEARCH_INDEX = {}
            for book in BOOKS_DB:
                raw_title = book.get("title", "")
                clean_t = clean_query(raw_title)
                if clean_t:
                    SEARCH_INDEX[clean_t] = book
            print(f"Database Updated: {len(SEARCH_INDEX)} books loaded.")
        else:
            print("Database update failed.")
    except Exception as e:
        print(f"DB Error: {e}")

def search_book(user_sentence):
    """
    Returns a BIG list of matches (up to 50) for pagination.
    """
    cleaned_sentence = clean_query(user_sentence)
    if len(cleaned_sentence) < 2: return []

    clean_titles = list(SEARCH_INDEX.keys())
    if not clean_titles: return []

    # 1. Use Partial Token Sort Ratio (Finds "History" inside "History of Islam")
    results = process.extract(
        cleaned_sentence, 
        clean_titles, 
        scorer=fuzz.partial_token_sort_ratio, 
        limit=50  # <--- INCREASED LIMIT TO 50
    )
    
    # 2. Filter (Must be > 60% match)
    valid_matches = []
    seen_titles = set()
    
    for title, score, _ in results:
        if score > 60:
            # Avoid duplicates if multiple file names are very similar
            real_book = SEARCH_INDEX[title]
            real_title = real_book.get("title", "")
            
            if real_title not in seen_titles:
                valid_matches.append(real_book)
                seen_titles.add(real_title)

    return valid_matches
