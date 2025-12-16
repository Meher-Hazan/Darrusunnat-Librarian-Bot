import re
from telegram import Update, ChatPermissions
from telegram.ext import ContextTypes
import datetime

# --- CONFIGURATION ---
# 1. BAD WORDS LIST (Add more slang/porn words here)
BAD_WORDS = [
    "scam", "bitcoin", "investment", "crypto", "sex", "porn", "xxx", 
    "fucker", "bitch", "whore", "asshole",
    # Bangla Bad Words (Example list - Expand as needed)
    "কুত্তা", "হারামি", "সোনা", "বাল", "চুদ", "খানকি", "মাগি"
]

# 2. SPAM PATTERNS
# Detects telegram channel links (t.me) to prevent stealing members
LINK_PATTERN = r"(t\.me\/|telegram\.me\/)"

async def check_and_moderate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Checks the message for spam/abuse.
    Returns TRUE if the message was deleted (so the main bot knows to stop).
    Returns FALSE if the message is safe.
    """
    if not update.message or not update.message.text:
        return False
    
    # Allow Admins to do whatever they want
    user = update.message.from_user
    chat_member = await context.bot.get_chat_member(update.message.chat_id, user.id)
    if chat_member.status in ["administrator", "creator"]:
        return False

    text = update.message.text.lower()
    should_ban = False
    reason = ""

    # CHECK 1: Bad Words
    for word in BAD_WORDS:
        # Check if the bad word exists as a standalone word
        if re.search(r'\b' + re.escape(word) + r'\b', text):
            should_ban = True
            reason = "Using bad language / Slang"
            break

    # CHECK 2: Telegram Invite Links (Spam)
    if re.search(LINK_PATTERN, text):
        should_ban = True
        reason = "Posting unauthorized invite links"

    # --- PUNISHMENT BLOCK ---
    if should_ban:
        try:
            # 1. Delete the message
            await update.message.delete()
            
            # 2. Mute the user for 24 hours
            # We restrict them to only reading messages, no sending.
            permissions = ChatPermissions(can_send_messages=False)
            until_date = datetime.datetime.now() + datetime.timedelta(hours=24)
            
            await context.bot.restrict_chat_member(
                chat_id=update.message.chat_id,
                user_id=user.id,
                permissions=permissions,
                until_date=until_date
            )

            # 3. Send a warning message (Auto-delete after 10 seconds to keep chat clean)
            warning_msg = await context.bot.send_message(
                chat_id=update.message.chat_id,
                text=f"🚫 **User Muted**\n👤 {user.mention_html()}\n🛑 Reason: {reason}\n⏳ Duration: 24 Hours",
                parse_mode="HTML"
            )
            
            # (Optional) Delete warning after 10s so it doesn't clutter chat
            # Note: Requires running a separate timer task, skipping for simplicity 
            # or just leaving the warning there.
            
            return True # Tell main.py "I deleted this, stop working"
            
        except Exception as e:
            print(f"Admin Action Failed: {e}")
            # If bot isn't admin, it will fail here.
            return False

    return False # Message is safe
