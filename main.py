import logging
import threading
import time
import requests
import asyncio
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
from uuid import uuid4
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CallbackQueryHandler, CommandHandler, InlineQueryHandler, filters

# IMPORT MODULES
from modules import config, admin_police, search_engine, stats

# --- GLOBAL MEMORY ---
USER_SEARCHES = {} 

# --- SERVER & KEEP ALIVE ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.wfile.write(b"Bot Active")

def start_server(): HTTPServer(("0.0.0.0", 8080), SimpleHandler).serve_forever()

def keep_alive():
    while True:
        time.sleep(600)
        try: requests.get(config.RENDER_URL)
        except: pass

# --- HELPER: KEYBOARD GENERATOR ---
def get_pagination_keyboard(results, page, total_pages):
    kb = []
    start = page * 5
    end = start + 5
    current_books = results[start:end]
    
    for book in current_books:
        title = book.get("title", "Book")
        if len(title) > 30: title = title[:28] + ".."
        kb.append([InlineKeyboardButton(f"📖 {title}", url=book.get("link", "#"))])
    
    nav = []
    if page > 0: nav.append(InlineKeyboardButton("⬅️ Back", callback_data=f"page_{page-1}"))
    nav.append(InlineKeyboardButton(f"📄 {page+1}/{total_pages}", callback_data="ignore"))
    if page < total_pages - 1: nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"page_{page+1}"))
    
    kb.append(nav)
    return InlineKeyboardMarkup(kb)

# --- HELPER: ESCAPE MARKDOWN ---
def escape_markdown(text):
    """Escapes special characters so Telegram doesn't crash"""
    if not text: return ""
    # Escape chars: _ * [ ] ( ) ~ ` > # + - = | { } . !
    escape_chars = r"([_*\[\]()~`>#+\-=|{}.!])"
    return re.sub(escape_chars, r"\\\1", text)

# --- HANDLERS ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ Catches /start to log the user immediately """
    user = update.effective_user
    stats.log_user(user.id) # <--- Log User Instantly
    await update.message.reply_text(
        f"👋 **Hello {user.first_name}!**\n\nI am the Library Bot. Type a book name to search!",
        parse_mode="Markdown"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats.log_user(update.effective_user.id) # Log user on every message
    if await admin_police.check_and_moderate(update, context): return 
    if not update.message or not update.message.text: return

    user_text = update.message.text
    stats.log_search(user_text) 
    
    matches = search_engine.search_book(user_text)

    if not matches:
        kb = [[InlineKeyboardButton("📝 Request to Admin", callback_data=f"req_{user_text[:20]}")]]
        await update.message.reply_text(
            f"❌ **No books found for '{user_text}'.**\nWant to request it?",
            reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown"
        )
        return

    USER_SEARCHES[update.effective_user.id] = matches
    total_pages = (len(matches) + 4) // 5
    keyboard = get_pagination_keyboard(matches, 0, total_pages)
    
    await update.message.reply_text(
        f"🔍 **Found {len(matches)} books matching '{user_text}':**",
        reply_markup=keyboard, parse_mode="Markdown"
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try: await query.answer()
    except: pass
    
    data = query.data

    if data.startswith("req_"):
        book_name = data.split("req_")[1]
        await query.edit_message_text(f"✅ **Request Sent!**\nAdmin notified for: `{book_name}`")
        try: 
            await context.bot.send_message(
                chat_id=config.ADMIN_ID, 
                text=f"🔔 **New Request!**\n👤 {query.from_user.mention_html()}\n📖 `{book_name}`", 
                parse_mode="HTML"
            )
        except Exception as e: print(f"Admin send error: {e}")
        return

    if data == "ignore": return
    
    if "page_" in data:
        user_id = update.effective_user.id
        if user_id not in USER_SEARCHES:
            await query.edit_message_text("⚠️ **Session expired. Search again.**")
            return
        
        new_page = int(data.split("_")[1])
        matches = USER_SEARCHES[user_id]
        total_pages = (len(matches) + 4) // 5
        
        try:
            await query.edit_message_reply_markup(
                reply_markup=get_pagination_keyboard(matches, new_page, total_pages)
            )
        except: pass

# --- INLINE SEARCH FIX ---
async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query
    if not query or len(query) < 2: return
    
    results = search_engine.search_book(query)[:15]
    articles = []
    
    for book in results:
        raw_title = book.get("title", "Book")
        link = book.get("link", "#")
        
        # 1. ESCAPE TITLE FOR MARKDOWN
        safe_title = escape_markdown(raw_title)

        articles.append(InlineQueryResultArticle(
            id=str(uuid4()),
            title=raw_title, # Plain text for the list title (No markdown needed here)
            description="Click to send PDF",
            input_message_content=InputTextMessageContent(
                # Use the SAFE title inside the bold ** tags
                message_text=f"📖 *{safe_title}*\n\n⬇️ [Download PDF]({link})", 
                parse_mode="MarkdownV2", # Use V2 for better escaping support
                disable_web_page_preview=False
            )
        ))
    
    await update.inline_query.answer(articles, cache_time=10)

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != config.ADMIN_ID: 
        await update.message.reply_text("⛔ You are not the admin.")
        return

    msg = " ".join(context.args)
    if not msg:
        await update.message.reply_text("⚠️ Usage: `/broadcast Hello everyone!`")
        return
    
    users = stats.get_all_users()
    await update.message.reply_text(f"📢 Starting broadcast to {len(users)} users...")
    
    success = 0
    blocked = 0
    
    for uid in users:
        try:
            await context.bot.send_message(chat_id=uid, text=f"📢 **Announcement:**\n\n{msg}", parse_mode="Markdown")
            success += 1
            await asyncio.sleep(0.05) 
        except:
            blocked += 1
            
    await update.message.reply_text(f"✅ Broadcast Done!\nSent: {success}\nBlocked/Failed: {blocked}")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != config.ADMIN_ID: return
    await update.message.reply_text(stats.get_stats(), parse_mode="Markdown")

async def send_daily_book(context: ContextTypes.DEFAULT_TYPE):
    book = search_engine.get_random_book()
    if not book: return
    try: 
        safe_title = escape_markdown(book['title'])
        msg = f"📅 **Daily Recommendation**\n\n📖 *{safe_title}*\n\n🔗 [Download PDF]({book['link']})"
        await context.bot.send_message(chat_id=config.GROUP_ID, text=msg, parse_mode="MarkdownV2")
    except: pass

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    search_engine.refresh_database()
    
    threading.Thread(target=start_server, daemon=True).start()
    threading.Thread(target=keep_alive, daemon=True).start()
    
    if config.BOT_TOKEN:
        app = ApplicationBuilder().token(config.BOT_TOKEN).build()
        
        # Handlers
        app.add_handler(CommandHandler("start", start_command)) # <--- NEW HANDLER FOR START
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
        app.add_handler(CallbackQueryHandler(handle_callback))
        app.add_handler(InlineQueryHandler(inline_query))
        
        app.add_handler(CommandHandler("stats", stats_command))
        app.add_handler(CommandHandler("broadcast", broadcast_command))
        
        if app.job_queue:
            app.job_queue.run_repeating(send_daily_book, interval=86400, first=10)
        
        print("Bot Fully Live with Fixes...")
        app.run_polling()
    else:
        print("Error: BOT_TOKEN is missing.")