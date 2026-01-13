import google.generativeai as genai
import ujson
from modules import config

# Configure AI
if config.GEMINI_API_KEY:
    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-pro')
else:
    model = None

def analyze_and_reply(user_text):
    """
    The Master Brain.
    Decides if the user wants a BOOK, a CHAT, or NOTHING.
    Returns a dictionary: {"type": "SEARCH"|"CHAT"|"IGNORE", "data": ...}
    """
    if not model: return {"type": "SEARCH", "data": user_text} # Fallback if no AI

    try:
        # SUPER PROMPT: Forces AI to categorize the message
        prompt = (
            f"Analyze this user message: '{user_text}'.\n"
            "Respond in strictly valid JSON format with two keys:\n"
            "1. 'intent': Choose one of ['SEARCH', 'CHAT', 'IGNORE']\n"
            "2. 'content': \n"
            "   - If SEARCH: Extract only the core book name/keywords (remove 'pdf', 'book', 'give me').\n"
            "   - If CHAT: Write a short, helpful Islamic answer (max 30 words).\n"
            "   - If IGNORE: Leave empty string.\n\n"
            "Rules:\n"
            "- 'SEARCH': Use this if they ask for a file, pdf, book, or a specific title.\n"
            "- 'CHAT': Use this for questions like 'Who is...', 'How to...', 'Meaning of...'.\n"
            "- 'IGNORE': Use this for 'Hi', 'Hello', 'Thanks', 'Ok', 'Bot'.\n"
        )
        
        response = model.generate_content(prompt)
        cleaned_text = response.text.replace("```json", "").replace("```", "").strip()
        result = ujson.loads(cleaned_text)
        
        return {
            "type": result.get("intent", "SEARCH").upper(),
            "data": result.get("content", "")
        }

    except Exception as e:
        print(f"AI Brain Error: {e}")
        # If AI fails, assume it's a search for safety
        return {"type": "SEARCH", "data": user_text}
