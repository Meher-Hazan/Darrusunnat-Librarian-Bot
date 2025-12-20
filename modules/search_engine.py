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
        if w in SYNONYMS: meaningful_words.append(SYNONYMS[w])
        else: meaningful_words.append(w)
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
                if clean_t: SEARCH_INDEX[clean_t] = book
            print(f"Database Updated: {len(SEARCH_INDEX)} books loaded.")
        else: print("Database update failed.")
    except Exception as e: print(f"DB Error: {e}")

def search_book(user_sentence):
    cleaned_sentence = clean_query(user_sentence)
    if len(cleaned_sentence) < 2: return []
    clean_titles = list(SEARCH_INDEX.keys())
    if not clean_titles: return []

    # STEP 1: Search using WRatio (Weighted Ratio)
    # WRatio is smarter than partial_ratio. It penalizes matches where 
    # the lengths are very different (e.g., "Man" vs "Spiderman").
    results = process.extract(
        cleaned_sentence, 
        clean_titles, 
        scorer=fuzz.WRatio, 
        limit=50
    )
    
    # STEP 2: Pre-Filter Garbage (Score < 60)
    # If the score is too low, it's definitely not what the user wants.
    valid_candidates = []
    for title, score, _ in results:
        if score > 60:
            valid_candidates.append((title, score))

    if not valid_candidates: 
        return []

    # STEP 3: The "Perfect Match" Check
    # Look at the highest score found
    top_score = valid_candidates[0][1] # Score of the #1 result

    final_results = []
    seen_titles = set()

    # LOGIC: 
    # If we found a "Perfect/High" match (> 90), we ONLY show high matches.
    # We do NOT show the weak partial matches in this case.
    if top_score > 90:
        threshold = 90
    else:
        # If no perfect match, we accept the "Okay" matches (> 60)
        threshold = 60

    # Collect the final list based on the dynamic threshold
    for title, score in valid_candidates:
        if score >= threshold:
            book = SEARCH_INDEX[title]
            real_title = book.get("title", "")
            
            # Remove duplicates
            if real_title not in seen_titles:
                final_results.append(book)
                seen_titles.add(real_title)

    return final_results

def get_random_book():
    import random
    if not BOOKS_DB: return None
    return random.choice(BOOKS_DB)