import os
import ujson
from groq import Groq
from modules import config

# Initialize Groq Client
client = None
if config.GROQ_API_KEY:
    try:
        client = Groq(api_key=config.GROQ_API_KEY)
    except Exception as e:
        print(f"Groq Config Error: {e}")

# --- OFFLINE BACKUP (Safety Net) ---
OFFLINE_GREETINGS = {
    "hi", "hello", "salam", "assalamu", "alaikum", "hey", "bot", "kemon", "acho"
}

def fallback_logic(user_text):
    """Used if AI fails or Internet is down"""
    text_lower = user_text.lower()
    words = text_lower.split()
    for w in words:
        if w in OFFLINE_GREETINGS:
            return {
                "type": "CHAT", 
                "data": "👋 **Hello!**\nI am connected to the library. Type a book name to search!"
            }
    # Default assumption: It's a search
    return {"type": "SEARCH", "data": user_text}

def analyze_and_reply(user_text):
    """
    The Master Brain (Powered by Groq/Llama-3)
    """
    # 1. Safety Check
    if not client:
        return fallback_logic(user_text)

    try:
        # 2. THE LIBRARIAN PROMPT
        # We teach the AI to understand Bangla/English requests and extract the core title.
        system_instruction = (
            "You are a smart Library Assistant for an Islamic PDF Bot. "
            "Your job is to classify the user's message into one of three intents.\n\n"
            
            "OUTPUT FORMAT: strictly valid JSON with keys 'intent' and 'content'.\n\n"
            
            "INTENT RULES:\n"
            "1. 'SEARCH': User wants a book, pdf, or topic. (e.g., 'Give me Bukhari', 'Iman books', 'Namazer boi')\n"
            "   -> CONTENT: Extract ONLY the core book name or topic. Remove words like 'pdf', 'file', 'boi', 'dao', 'plz', 'amake', 'chai'.\n"
            "   -> Example: 'Amake Bukhari Sharif er pdf dao' -> content: 'Bukhari Sharif'\n"
            "   -> Example: 'History of Islam' -> content: 'History of Islam'\n\n"
            
            "2. 'CHAT': User is greeting or asking a general question. (e.g., 'Hi', 'Kemon acho', 'Who is Allah?', 'Meaning of Sabr')\n"
            "   -> CONTENT: Write a short, helpful, polite answer (max 40 words).\n\n"
            
            "3. 'IGNORE': User is spamming or sending nonsense.\n"
            "   -> CONTENT: Leave empty.\n"
        )

        completion = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_text}
            ],
            temperature=0.3, # Low temperature = More precise/less creative
            max_tokens=150,
            response_format={"type": "json_object"}
        )
        
        # Parse Response
        response_text = completion.choices[0].message.content
        result = ujson.loads(response_text)
        
        return {
            "type": result.get("intent", "SEARCH").upper(),
            "data": result.get("content", "")
        }

    except Exception as e:
        print(f"Groq Brain Error: {e}")
        return fallback_logic(user_text)
