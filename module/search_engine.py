import requests
import re
from rapidfuzz import process, fuzz
from modules.config import DATA_URL, SYNONYMS, STOP_WORDS

BOOKS_DB = []
SEARCH_INDEX = {}

def clean_query(text):
    """
    Cleans up the user's sentence to find the 'core' book name.
    """
    if not text: return ""
    text = text.lower()
    text = text.replace(".pdf", "").replace("_", " ").replace("-", " ")
    text = re.sub(r'[^\w\s]', '', text) # Remove punctuation
    text = re.sub(r'\d+', '', text)    # Remove numbers (ids)
    
    words = text.split()
    meaningful_words = []
    
    for w in words:
        if w in STOP_WORDS: continue
        # Apply Synonym (Biography -> Jiboni)
        if w in SYNONYMS: 
            meaningful_words.append(SYNONYMS[w])
        else:
            meaningful_words.append(w)
            
    return " ".join(meaningful_words)

def refresh_database():
    """Downloads and rebuilds the search index"""
    global BOOKS_DB, SEARCH_INDEX
    try:
        resp = requests.get(DATA_URL)
        if resp.status_code == 200:
            BOOKS_DB = resp.json()
            SEARCH_INDEX = {}
            for book in BOOKS_DB:
                raw_title = book.get("title", "")
                # We use the clean title as the 'Key' for search
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
    Smart Search: Handles long sentences and finds the book inside them.
    Returns: (best_match_book, list_of_suggestions)
    """
    cleaned_sentence = clean_query(user_sentence)
    if len(cleaned_sentence) < 3: return None, []

    # Get all book titles
    clean_titles = list(SEARCH_INDEX.keys())
    if not clean_titles: return None, []

    # --- THE IMPROVED LOGIC ---
    # 1. partial_token_sort_ratio: Great for finding "Book Title" inside "Long Sentence"
    # It ignores word order and extra words.
    results = process.extract(
        cleaned_sentence, 
        clean_titles, 
        scorer=fuzz.partial_token_sort_ratio, 
        limit=10 
    )
    
    # Filter results (Remove trash matches)
    # We require at least 65% similarity to even consider it
    valid_matches = []
    for title, score, _ in results:
        if score > 65:
            valid_matches.append((title, score))

    if not valid_matches:
        return None, []

    # Separate "Exact" from "Suggestions"
    top_title, top_score = valid_matches[0]
    
    # If score is > 85, we treat it as a "Direct Hit"
    if top_score > 85:
        best_book = SEARCH_INDEX[top_title]
        # Suggestions are the rest of the list
        suggestions = [SEARCH_INDEX[t] for t, s in valid_matches[1:6]] # Next 5
        return best_book, suggestions
    
    # If no direct hit, return Top 6 as suggestions
    suggestions = [SEARCH_INDEX[t] for t, s in valid_matches[:6]]
    return None, suggestions
