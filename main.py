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
from modules import config, admin_police, search_engine, stats, ai_brain

# --- GLOBAL MEMORY ---
USER_SEARCHES = {} 

# --- SERVER & KEEP ALIVE (For Render) ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.wfile.write(b"Bot Active")

def start_server(): 
    HTTPServer(("0.0.0.0", 8080), SimpleHandler).serve_forever()

def keep_alive():
    while True:
        time.sleep(600) # Ping every 10 minutes
        try: requests.get(config.RENDER_URL)
        except: pass

# --- HELPERS ---
def escape_markdown(text):
    """Escapes special characters for Telegram MarkdownV2"""
    if not text: return ""
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!])", r"\\\1", text)

def get_pagination_keyboard(results, page, total_pages):
    kb = []
    start = page * 5
    end = start + 5
    current_books = results[start:end]
    
    # Book Buttons
    for book in current_books:
        title = book.get(config.KEY_TITLE, "Book")
        # Truncate long titles
        if len(title) > 30: title = title[:28] + ".."
        kb.append([InlineKeyboardButton(f"📖 {title}", url=book.get(config.KEY_LINK, "#"))])
    
    # Navigation Buttons
    nav = []
    if page > 0: 
        nav.append(InlineKeyboardButton("⬅️ Back", callback_data=f"page_{page-1}"))
    
    nav.append(InlineKeyboardButton(f"📄 {page+1}/{total_pages}", callback_data="ignore"))
    
    if page < total_pages - 1: 
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"page_{page+1}"))
    
    kb.append(nav)
    return InlineKeyboardMarkup(kb)

# --- HANDLERS ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Logs user and sends welcome message"""
    stats.log_user(update.effective_user.id)
    await update.message.reply_text(
        f"👋 **Hello!**\n\nI am your AI Library Assistant.\n"
        f"📚 Books Loaded: `{search_engine.count_books()}`\n\n"
        f"🔎 **To Search:** Just type the book name.\n"
        f"🤖 **To Chat:** Just ask me any question!",
        parse_mode="Markdown"
    )

async def refresh_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to force update the book list"""
    if update.effective_user.id != config.ADMIN_ID: return
    
    await update.message.reply_text("🔄 **Updating Database...**")
    if search_engine.refresh_database():
        await update.message.reply_text(f"✅ **Update Complete!**\nTotal Books: {search_engine.count_books()}")
    else:
        await update.message.reply_text("❌ **Update Failed.** Check server logs.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The Master Handler: Uses AI to decide between Chat, Search, or Ignore"""
    user = update.effective_user
    
    # 1. Log User & Check Security (Spam/Bad Words)
    stats.log_user(user.id)
    if await admin_police.check_and_moderate(update, context): return 
    if not update.message or not update.message.text: return

    user_text = update.message.text
    
    # --- PHASE 1: AI BRAIN ANALYSIS ---
    # The AI decides if this is a SEARCH, a CHAT, or IGNORE
    decision = ai_brain.analyze_and_reply(user_text)
    
    intent = decision.get("type", "SEARCH")
    content = decision.get("data", user_text)

    # --- PHASE 2: EXECUTE DECISION ---
    
    # CASE A: IGNORE (e.g. "Hi", "Thanks")
    if intent == "IGNORE":
        return 

    # CASE B: CHAT (e.g. "Who is Imam Bukhari?")
    if intent == "CHAT":
        await update.message.reply_text(f"🤖 **AI:** {content}", parse_mode="Markdown")
        return

    # CASE C: SEARCH (e.g. "Give me Bukhari PDF")
    if intent == "SEARCH":
        # Log the search term for analytics
        stats.log_search(content) 

        # Search using the cleaned keyword from AI
        matches = search_engine.search_book(content)

        # 1. Matches Found
        if matches:
            USER_SEARCHES[user.id] = matches
            total_pages = (len(matches) + 4) // 5
            await update.message.reply_text(
                f"🔍 **Found {len(matches)} books for '{content}':**", 
                reply_markup=get_pagination_keyboard(matches, 0, total_pages), 
                parse_mode="Markdown"
            )
        
        # 2. No Matches Found
        else:
            kb = [[InlineKeyboardButton("📝 Request to Admin", callback_data=f"req_{user_text[:20]}")]]
            await update.message.reply_text(
                f"❌ **I couldn't find '{content}'.**\nWould you like to request it?", 
                reply_markup=InlineKeyboardMarkup(kb), 
                parse_mode="Markdown"
            )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles button clicks (Pagination & Requests)"""
    query = update.callback_query
    try: await query.answer()
    except: pass
    
    data = query.data

    # HANDLE BOOK REQUESTS
    if data.startswith("req_"):
        book_name = data.split("req_")[1]
        await query.edit_message_text(f"✅ **Request Sent!**\nI notified the admin.")
        try: 
            await context.bot.send_message(
                chat_id=config.ADMIN_ID, 
                text=f"🔔 **New Book Request!**\n👤 {query.from_user.mention_html()}\n📖 `{book_name}`", 
                parse_mode="HTML"
            )
        except Exception as e: print(f"Admin send error: {e}")
        return

    # HANDLE PAGINATION
    if "page_" in data:
        user_id = update.effective_user.id
        if user_id not in USER_SEARCHES:
            await query.edit_message_text("⚠️ **Session Expired.** Please search again.")
            return
        
        new_page = int(data.split("_")[1])
        matches = USER_SEARCHES[user_id]
        total_pages = (len(matches) + 4) // 5
        
        try:
            await query.edit_message_reply_markup(
                reply_markup=get_pagination_keyboard(matches, new_page, total_pages)
            )
        except: pass

async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles Inline Mode (@BotName keyword)"""
    query = update.inline_query.query
    if not query or len(query) < 2: return
    
    results = search_engine.search_book(query)[:10]
    articles = []
    
    for book in results:
        raw_title = book.get(config.KEY_TITLE, "Book")
        link = book.get(config.KEY_LINK, "#")
        safe_title = escape_markdown(raw_title)

        articles.append(InlineQueryResultArticle(
            id=str(uuid4()),
            title=raw_title,
            description="Click to send PDF",
            input_message_content=InputTextMessageContent(
                message_text=f"📖 *{safe_title}*\n\n⬇️ [Download PDF]({link})", 
                parse_mode="MarkdownV2",
                disable_web_page_preview=False
            )
        ))
    
    await update.inline_query.answer(articles, cache_time=10)

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a message or photo to ALL users"""
    if update.effective_user.id != config.ADMIN_ID: return

    is_photo = False
    photo_id = None
    msg_text = " ".join(context.args)

    # Check if replying to a photo
    if update.message.reply_to_message:
        if update.message.reply_to_message.photo:
            is_photo = True
            photo_id = update.message.reply_to_message.photo[-1].file_id
            if not msg_text: msg_text = update.message.reply_to_message.caption or ""

    if not msg_text and not is_photo:
        await update.message.reply_text("⚠️ Usage: `/broadcast Message` OR Reply to a photo with `/broadcast`")
        return

    users = stats.get_all_users()
    await update.message.reply_text(f"📢 Broadcasting to {len(users)} users...")
    
    count = 0
    for uid in users:
        try:
            if is_photo:
                await context.bot.send_photo(chat_id=uid, photo=photo_id, caption=msg_text, parse_mode="Markdown")
            else:
                await context.bot.send_message(chat_id=uid, text=f"📢 **Announcement:**\n\n{msg_text}", parse_mode="Markdown")
            count += 1
            await asyncio.sleep(0.05) # Prevent flood limits
        except: pass
    await update.message.reply_text(f"✅ Done. Sent to {count} users.")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == config.ADMIN_ID:
        await update.message.reply_text(stats.get_stats(), parse_mode="Markdown")

# --- AUTOMATION JOBS ---
async def auto_update_db(context: ContextTypes.DEFAULT_TYPE):
    search_engine.refresh_database()

async def send_random_book(context: ContextTypes.DEFAULT_TYPE):
    book = search_engine.get_random_book()
    if not book: return
    
    title = escape_markdown(book.get(config.KEY_TITLE, "Book"))
    link = book.get(config.KEY_LINK, "#")
    image = book.get(config.KEY_IMAGE) # Image Support

    caption = f"✨ **Random Pick**\n\n📖 *{title}*\n\n🔗 [Read Now]({link})"

    try:
        if image and "http" in image:
            await context.bot.send_photo(chat_id=config.GROUP_ID, photo=image, caption=caption, parse_mode="MarkdownV2")
        else:
            await context.bot.send_message(chat_id=config.GROUP_ID, text=caption, parse_mode="MarkdownV2")
    except: pass

# --- MAIN EXECUTION ---
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    # Load Data Immediately
    search_engine.refresh_database()
    
    # Start Keep-Alive Server
    threading.Thread(target=start_server, daemon=True).start()
    threading.Thread(target=keep_alive, daemon=True).start()
    
    if config.BOT_TOKEN:
        app = ApplicationBuilder().token(config.BOT_TOKEN).build()
        
        # Commands
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("refresh", refresh_command))
        app.add_handler(CommandHandler("broadcast", broadcast_command))
        app.add_handler(CommandHandler("stats", stats_command))
        
        # Message Handlers
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
        app.add_handler(CallbackQueryHandler(handle_callback))
        app.add_handler(InlineQueryHandler(inline_query))
        
        # Automation Jobs
        if app.job_queue:
            # Random Book every 4 hours (14400s)
            app.job_queue.run_repeating(send_random_book, interval=config.RANDOM_BOOK_INTERVAL, first=10)
            # Update DB every 30 mins
            app.job_queue.run_repeating(auto_update_db, interval=config.DB_REFRESH_INTERVAL, first=1800)
        
        print("🚀 AI Library Bot is Fully Live...")
        app.run_polling()
    else:
        print("Error: BOT_TOKEN is missing in Environment Variables.")
