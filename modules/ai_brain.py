import google.generativeai as genai
from modules import config

# Configure the AI
if config.GEMINI_API_KEY:
    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-pro')
else:
    model = None

def get_smart_keywords(user_text):
    """
    Asks AI to translate a complex request into simple search keywords.
    Example: "I am sad" -> ["Chinta", "Hutasha", "Sabr"]
    """
    if not model: return []
    
    try:
        # We tell the AI to act like a Librarian
        prompt = (
            f"Act as a Library Assistant. The user wants a book related to: '{user_text}'. "
            "Suggest 3 simple, single-word search keywords (in Bangla or Banglish) "
            "that are most likely to match Islamic book titles. "
            "Output ONLY the words separated by commas. No explanations."
        )
        
        response = model.generate_content(prompt)
        # Clean up the AI response
        keywords = response.text.replace("\n", "").split(",")
        # Clean whitespace
        return [k.strip() for k in keywords]
    except Exception as e:
        print(f"AI Error: {e}")
        return []

def ask_general_question(question):
    """
    Answers general Islamic questions using AI.
    """
    if not model: return "⚠️ AI is not configured."
    
    try:
        prompt = (
            f"You are a helpful Islamic Assistant. Answer this question concisely (max 50 words): {question}"
        )
        response = model.generate_content(prompt)
        return response.text
    except:
        return "⚠️ I am currently overloaded. Please try again later."
