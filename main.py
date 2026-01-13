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

# --- MEMORY ---
USER_SEARCHES = {} 

# --- SERVER ---
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

# --- HELPERS ---
def escape_markdown(text):
    if not text: return ""
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!])", r"\\\1", text)

def get_pagination_keyboard(results, page, total_pages):
    kb = []
    start = page * 5
    current_books = results[start:start+5]
    for book in current_books:
        title = book.get(config.KEY_TITLE, "Book")
        if len(title) > 30: title = title[:28] + ".."
        kb.append([InlineKeyboardButton(f"📖 {title}", url=book.get(config.KEY_LINK, "#"))])
    
    nav = []
    if page > 0: nav.append(InlineKeyboardButton("⬅️ Back", callback_data=f"page_{page-1}"))
    nav.append(InlineKeyboardButton(f"📄 {page+1}/{total_pages}", callback_data="ignore"))
    if page < total_pages - 1: nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"page_{page+1}"))
    kb.append(nav)
    return InlineKeyboardMarkup(kb)

# --- HANDLERS ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats.log_user(update.effective_user.id)
    await update.message.reply_text(f"👋 **Hello!**\n\nI am the AI Library Bot.\n\n🔎 **Search:** Just type a book name.\n🤖 **Ask AI:** Type `/ask Your Question`", parse_mode="Markdown")

async def refresh_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != config.ADMIN_ID: return
    await update.message.reply_text("🔄 **Updating Database...**")
    if search_engine.refresh_database():
        await update.message.reply_text(f"✅ **Done!** Books: {search_engine.count_books()}")
    else: await update.message.reply_text("❌ Failed.")

# --- NEW: AI QUESTION HANDLER ---
async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question = " ".join(context.args)
    if not question:
        await update.message.reply_text("⚠️ Usage: `/ask Who is Imam Bukhari?`")
        return
    
    await update.message.reply_chat_action(action="typing")
    answer = ai_brain.ask_general_question(question)
    await update.message.reply_text(f"🤖 **AI Answer:**\n\n{answer}", parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats.log_user(update.effective_user.id)
    if await admin_police.check_and_moderate(update, context): return 
    if not update.message or not update.message.text: return

    user_text = update.message.text
    
    # 1. ATTEMPT NORMAL SEARCH
    matches = search_engine.search_book(user_text)

    # 2. IF NO MATCH -> ACTIVATE AI BRAIN 🧠
    if not matches:
        # Let the user know we are trying harder
        status_msg = await update.message.reply_text("🤔 **Searching deeply using AI...**")
        
        # Ask AI for better keywords
        ai_keywords = ai_brain.get_smart_keywords(user_text)
        
        if ai_keywords:
            # Try searching with each AI keyword
            for keyword in ai_keywords:
                new_matches = search_engine.search_book(keyword)
                # Avoid duplicates
                for m in new_matches:
                    if m not in matches:
                        matches.append(m)
        
        # Delete the "Searching..." message
        await status_msg.delete()

    # 3. FINAL CHECK
    if not matches:
        kb = [[InlineKeyboardButton("📝 Request Book", callback_data=f"req_{user_text[:20]}")]]
        await update.message.reply_text(f"❌ **No result for '{user_text}'.**\nRequest it?", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
        return

    USER_SEARCHES[update.effective_user.id] = matches
    total_pages = (len(matches) + 4) // 5
    
    # Custom message if AI helped
    header = f"🔍 **Found {len(matches)} books:**"
    
    await update.message.reply_text(header, reply_markup=get_pagination_keyboard(matches, 0, total_pages), parse_mode="Markdown")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try: await query.answer()
    except: pass
    
    data = query.data
    if data.startswith("req_"):
        book_name = data.split("req_")[1]
        await query.edit_message_text(f"✅ **Request Sent!**")
        try: await context.bot.send_message(chat_id=config.ADMIN_ID, text=f"🔔 **Request:**\n📖 `{book_name}`", parse_mode="Markdown")
        except: pass
        return

    if "page_" in data:
        user_id = update.effective_user.id
        if user_id not in USER_SEARCHES:
            await query.edit_message_text("⚠️ **Session Expired.** Search again.")
            return
        new_page = int(data.split("_")[1])
        matches = USER_SEARCHES[user_id]
        total_pages = (len(matches) + 4) // 5
        try: await query.edit_message_reply_markup(reply_markup=get_pagination_keyboard(matches, new_page, total_pages))
        except: pass

async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query
    if not query or len(query) < 2: return
    results = search_engine.search_book(query)[:10]
    articles = []
    for book in results:
        title = escape_markdown(book.get(config.KEY_TITLE, "Book"))
        link = book.get(config.KEY_LINK, "#")
        articles.append(InlineQueryResultArticle(
            id=str(uuid4()), title=title, description="Click to send PDF",
            input_message_content=InputTextMessageContent(f"📖 *{title}*\n🔗 [Download PDF]({link})", parse_mode="MarkdownV2")
        ))
    await update.inline_query.answer(articles, cache_time=10)

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != config.ADMIN_ID: return
    is_photo = False
    photo_id = None
    msg_text = " ".join(context.args)

    if update.message.reply_to_message:
        if update.message.reply_to_message.photo:
            is_photo = True
            photo_id = update.message.reply_to_message.photo[-1].file_id
            if not msg_text: msg_text = update.message.reply_to_message.caption or ""

    if not msg_text and not is_photo:
        await update.message.reply_text("⚠️ Usage: `/broadcast Msg` OR Reply to photo")
        return

    users = stats.get_all_users()
    await update.message.reply_text(f"📢 Sending to {len(users)} users...")
    for uid in users:
        try:
            if is_photo: await context.bot.send_photo(chat_id=uid, photo=photo_id, caption=msg_text, parse_mode="Markdown")
            else: await context.bot.send_message(chat_id=uid, text=f"📢 **Announcement:**\n\n{msg_text}", parse_mode="Markdown")
            await asyncio.sleep(0.05)
        except: pass
    await update.message.reply_text("✅ Done.")

async def send_random_book(context: ContextTypes.DEFAULT_TYPE):
    book = search_engine.get_random_book()
    if not book: return
    title = escape_markdown(book.get(config.KEY_TITLE, "Book"))
    link = book.get(config.KEY_LINK, "#")
    image = book.get(config.KEY_IMAGE)
    caption = f"✨ **Random Pick**\n\n📖 *{title}*\n\n🔗 [Read Now]({link})"
    try:
        if image and "http" in image: await context.bot.send_photo(chat_id=config.GROUP_ID, photo=image, caption=caption, parse_mode="MarkdownV2")
        else: await context.bot.send_message(chat_id=config.GROUP_ID, text=caption, parse_mode="MarkdownV2")
    except: pass

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == config.ADMIN_ID:
        await update.message.reply_text(stats.get_stats(), parse_mode="Markdown")

async def auto_update_db(context: ContextTypes.DEFAULT_TYPE):
    search_engine.refresh_database()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    search_engine.refresh_database()
    
    threading.Thread(target=start_server, daemon=True).start()
    threading.Thread(target=keep_alive, daemon=True).start()
    
    if config.BOT_TOKEN:
        app = ApplicationBuilder().token(config.BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("refresh", refresh_command))
        app.add_handler(CommandHandler("broadcast", broadcast_command))
        app.add_handler(CommandHandler("stats", stats_command))
        app.add_handler(CommandHandler("ask", ask_command)) # <--- NEW COMMAND
        
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
        app.add_handler(CallbackQueryHandler(handle_callback))
        app.add_handler(InlineQueryHandler(inline_query))
        
        if app.job_queue:
            app.job_queue.run_repeating(send_random_book, interval=config.RANDOM_BOOK_INTERVAL, first=10)
            app.job_queue.run_repeating(auto_update_db, interval=config.DB_REFRESH_INTERVAL, first=1800)
        
        print("🤖 AI Bot Started...")
        app.run_polling()
    else: print("Error: BOT_TOKEN missing")
