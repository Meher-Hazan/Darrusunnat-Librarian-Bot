import google.generativeai as genai
import ujson
from modules import config

# Configure AI
model = None

def configure_model():
    """Initializes the AI Model with a safe fallback"""
    global model
    if not config.GEMINI_API_KEY:
        return

    try:
        genai.configure(api_key=config.GEMINI_API_KEY)
        # We use 'gemini-pro' because it is the most stable and available model
        model = genai.GenerativeModel('gemini-pro')
    except Exception as e:
        print(f"AI Config Error: {e}")

# Run configuration immediately
configure_model()

def analyze_and_reply(user_text):
    """
    The Master Brain.
    Decides if the user wants a BOOK, a CHAT, or NOTHING.
    """
    # 1. Safety Check: Is AI alive?
    if not model: 
        return {
            "type": "CHAT", 
            "data": "⚠️ **System Error:** AI is disabled. Please check your `GEMINI_API_KEY` in Render."
        }

    try:
        # SUPER PROMPT: Forces AI to categorize the message
        prompt = (
            f"Analyze this user message: '{user_text}'.\n"
            "Respond in strictly valid JSON format with two keys:\n"
            "1. 'intent': Choose one of ['SEARCH', 'CHAT', 'IGNORE']\n"
            "2. 'content': \n"
            "   - If SEARCH: Extract only the core book name/keywords (remove 'pdf', 'book', 'give me').\n"
            "   - If CHAT: Write a short, helpful Islamic answer (max 50 words).\n"
            "   - If IGNORE: Leave empty string.\n\n"
            "Rules:\n"
            "- 'SEARCH': Use this if they ask for a file, pdf, book, or a specific title.\n"
            "- 'CHAT': Use this for questions like 'Who is...', 'How to...', 'Meaning of...', 'Hi', 'Hello', 'Kemon acho'.\n"
            "- 'IGNORE': Use this for short spam or nonsense.\n"
        )
        
        response = model.generate_content(prompt)
        
        # Clean up the AI response (sometimes it adds ```json markers)
        cleaned_text = response.text.replace("```json", "").replace("```", "").strip()
        result = ujson.loads(cleaned_text)
        
        return {
            "type": result.get("intent", "SEARCH").upper(),
            "data": result.get("content", "")
        }

    except Exception as e:
        # If the AI fails (e.g., 404 or Overloaded), we Default to Search to be safe
        print(f"AI Brain Error: {e}")
        return {"type": "SEARCH", "data": user_text}
