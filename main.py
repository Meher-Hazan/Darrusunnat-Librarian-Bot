import logging
import threading
import time
import requests
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
from uuid import uuid4
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CallbackQueryHandler, CommandHandler, InlineQueryHandler, filters

# IMPORT MODULES
from modules import config, admin_police, search_engine, stats

# --- GLOBAL MEMORY ---
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

# --- HELPER: KEYBOARD GENERATOR ---
def get_pagination_keyboard(results, page, total_pages):
    kb = []
    
    # Calculate Slice
    start = page * 5
    end = start + 5
    current_books = results[start:end]
    
    # Book Buttons
    for book in current_books:
        title = book.get("title", "Book")
        # Smart Truncate
        if len(title) > 30: title = title[:28] + ".."
        kb.append([InlineKeyboardButton(f"📖 {title}", url=book.get("link", "#"))])
    
    # Navigation Row (Prev | Page | Next)
    nav = []
    
    # BACK BUTTON (Only if page > 0)
    if page > 0: 
        nav.append(InlineKeyboardButton("⬅️ Back", callback_data=f"page_{page-1}"))
    
    # Page Indicator (Clicking does nothing)
    nav.append(InlineKeyboardButton(f"📄 {page+1}/{total_pages}", callback_data="ignore"))
    
    # NEXT BUTTON (Only if not last page)
    if page < total_pages - 1: 
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"page_{page+1}"))
    
    kb.append(nav)
    return InlineKeyboardMarkup(kb)

# --- HANDLERS ---

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Log User & Check Spam
    stats.log_user(update.effective_user.id)
    if await admin_police.check_and_moderate(update, context): return 
    if not update.message or not update.message.text: return

    user_text = update.message.text
    stats.log_search(user_text) 
    
    # Search
    matches = search_engine.search_book(user_text)

    # NO MATCHES -> Request
    if not matches:
        kb = [[InlineKeyboardButton("📝 Request to Admin", callback_data=f"req_{user_text[:20]}")]]
        await update.message.reply_text(
            f"❌ **No books found for '{user_text}'.**\nWant to request it?",
            reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown"
        )
        return

    # MATCHES -> Show Page 0
    USER_SEARCHES[update.effective_user.id] = matches
    total_pages = (len(matches) + 4) // 5
    keyboard = get_pagination_keyboard(matches, 0, total_pages)
    
    await update.message.reply_text(
        f"🔍 **Found {len(matches)} books matching '{user_text}':**",
        reply_markup=keyboard, parse_mode="Markdown"
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    # Crucial: Always answer to stop loading circle
    try: await query.answer()
    except: pass
    
    data = query.data

    # HANDLE REQUESTS
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

    # HANDLE PAGINATION
    if data == "ignore": return
    
    if "page_" in data:
        user_id = update.effective_user.id
        
        # 1. CHECK MEMORY (Did bot restart?)
        if user_id not in USER_SEARCHES:
            await query.edit_message_text("⚠️ **Bot restarted or session expired.**\nPlease search for the book again.")
            return
        
        # 2. CALCULATE PAGE
        new_page = int(data.split("_")[1])
        matches = USER_SEARCHES[user_id]
        total_pages = (len(matches) + 4) // 5
        
        # 3. UPDATE MESSAGE
        try:
            await query.edit_message_reply_markup(
                reply_markup=get_pagination_keyboard(matches, new_page, total_pages)
            )
        except Exception as e:
            # If content is same (rare), Telegram throws error. Ignore it.
            pass

# --- INLINE SEARCH FIX ---
async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query
    if not query or len(query) < 2: return
    
    # Search and limit to 10 results for speed
    results = search_engine.search_book(query)[:15]
    articles = []
    
    for book in results:
        title = book.get("title", "Book")
        link = book.get("link", "#")
        
        # Create Result Card
        articles.append(InlineQueryResultArticle(
            id=str(uuid4()), # Unique ID required
            title=title,
            description="Click to send PDF",
            input_message_content=InputTextMessageContent(
                message_text=f"📖 **{title}**\n\n⬇️ [Download PDF]({link})", 
                parse_mode="Markdown",
                disable_web_page_preview=False
            )
        ))
    
    # Cache results for 10 seconds to save server load
    await update.inline_query.answer(articles, cache_time=10)

# --- BROADCAST FIX ---
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Security Check
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
            await asyncio.sleep(0.05) # Prevent flood wait
        except Exception as e:
            blocked += 1
            
    await update.message.reply_text(f"✅ Broadcast Done!\nSent: {success}\nFailed/Blocked: {blocked}")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != config.ADMIN_ID: return
    await update.message.reply_text(stats.get_stats(), parse_mode="Markdown")

# --- DAILY BOOK JOB ---
async def send_daily_book(context: ContextTypes.DEFAULT_TYPE):
    book = search_engine.get_random_book()
    if not book: return
    try: 
        msg = f"📅 **Daily Recommendation**\n\n📖 **{book['title']}**\n\n🔗 [Download PDF]({book['link']})"
        await context.bot.send_message(chat_id=config.GROUP_ID, text=msg, parse_mode="Markdown")
    except: pass

# --- MAIN ---
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    search_engine.refresh_database()
    
    threading.Thread(target=start_server, daemon=True).start()
    threading.Thread(target=keep_alive, daemon=True).start()
    
    if config.BOT_TOKEN:
        app = ApplicationBuilder().token(config.BOT_TOKEN).build()
        
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
        app.add_handler(CallbackQueryHandler(handle_callback))
        app.add_handler(InlineQueryHandler(inline_query)) # <--- INLINE HANDLER
        
        app.add_handler(CommandHandler("stats", stats_command))
        app.add_handler(CommandHandler("broadcast", broadcast_command))
        
        if app.job_queue:
            app.job_queue.run_repeating(send_daily_book, interval=86400, first=10)
        
        print("Bot Fully Live...")
        app.run_polling()
    else:
        print("Error: BOT_TOKEN is missing.")