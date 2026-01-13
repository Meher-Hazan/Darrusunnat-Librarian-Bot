import google.generativeai as genai
import ujson
from modules import config

# Configure AI
model = None
if config.GEMINI_API_KEY:
    try:
        genai.configure(api_key=config.GEMINI_API_KEY)
        # Switched to 1.5-flash (Faster & Better for Free Tier)
        model = genai.GenerativeModel('gemini-1.5-flash')
    except Exception as e:
        print(f"AI Config Error: {e}")

def analyze_and_reply(user_text):
    """
    The Master Brain.
    Decides if the user wants a BOOK, a CHAT, or NOTHING.
    """
    # 1. DEBUG: If API Key is missing/invalid, tell the user immediately.
    if not model: 
        return {
            "type": "CHAT", 
            "data": "⚠️ **System Error:** AI is disabled. Please check your `GEMINI_API_KEY` in Render Environment Variables."
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
        print(f"AI Brain Error: {e}")
        # If AI crashes, we return the error message so you can see it in the bot
        return {"type": "CHAT", "data": f"⚠️ **AI Error:** {str(e)}"}
