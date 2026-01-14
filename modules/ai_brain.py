import google.generativeai as genai
import ujson
import time
from modules import config

# List of models to try (in order of preference)
MODELS_TO_TRY = ["gemini-1.5-flash", "gemini-pro", "gemini-1.0-pro"]
active_model = None

def configure_model():
    """Tries to connect to ANY working Google Model"""
    global active_model
    
    if not config.GEMINI_API_KEY:
        print("❌ No API Key found.")
        return

    genai.configure(api_key=config.GEMINI_API_KEY)

    for model_name in MODELS_TO_TRY:
        try:
            print(f"🔄 Testing Model: {model_name}...")
            model = genai.GenerativeModel(model_name)
            # Test it with a tiny prompt
            model.generate_content("Test")
            print(f"✅ Success! Connected to {model_name}")
            active_model = model
            return
        except Exception as e:
            print(f"⚠️ Failed to load {model_name}: {e}")
    
    print("❌ ALL AI Models failed. Switching to Offline Mode.")

# Run setup immediately
configure_model()

# --- OFFLINE BACKUP BRAIN ---
# If AI fails, this simple logic handles greetings so the bot doesn't look stupid.
OFFLINE_GREETINGS = {
    "hi", "hello", "salam", "assalamu", "alaikum", "hey", "bot", "kemon", "acho"
}

def fallback_logic(user_text):
    """
    Used when AI is broken.
    Detects basic greetings and returns CHAT intent.
    Everything else becomes SEARCH.
    """
    text_lower = user_text.lower()
    
    # Check if any word is a greeting
    words = text_lower.split()
    for w in words:
        if w in OFFLINE_GREETINGS:
            return {
                "type": "CHAT", 
                "data": "👋 **Hello!**\nI am currently in 'Offline Mode' (AI is reconnecting), but I can still search for books! Just type the name."
            }
    
    # Default to Search
    return {"type": "SEARCH", "data": user_text}

def analyze_and_reply(user_text):
    """
    The Master Brain.
    Tries AI first. If AI crashes/fails, uses Fallback Logic.
    """
    global active_model

    # 1. If AI is dead, use Offline Backup
    if not active_model:
        return fallback_logic(user_text)

    try:
        # 2. Ask AI
        prompt = (
            f"Analyze this user message: '{user_text}'.\n"
            "Respond in strictly valid JSON format with two keys:\n"
            "1. 'intent': Choose one of ['SEARCH', 'CHAT', 'IGNORE']\n"
            "2. 'content': \n"
            "   - If SEARCH: Extract only the book title (remove 'pdf', 'book').\n"
            "   - If CHAT: Write a short, helpful Islamic answer (max 50 words).\n"
            "   - If IGNORE: Leave empty string.\n"
        )
        
        response = active_model.generate_content(prompt)
        cleaned_text = response.text.replace("```json", "").replace("```", "").strip()
        result = ujson.loads(cleaned_text)
        
        return {
            "type": result.get("intent", "SEARCH").upper(),
            "data": result.get("content", "")
        }

    except Exception as e:
        print(f"AI Runtime Error: {e}")
        # If AI fails mid-conversation, use fallback
        return fallback_logic(user_text)
