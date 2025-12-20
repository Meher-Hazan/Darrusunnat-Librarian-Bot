import ujson
import os
from modules import config

# Ensure files exist
if not os.path.exists(config.USERS_FILE):
    with open(config.USERS_FILE, 'w') as f: ujson.dump([], f)

if not os.path.exists(config.STATS_FILE):
    with open(config.STATS_FILE, 'w') as f: ujson.dump({"searches": 0, "top_terms": {}}, f)

def log_user(user_id):
    """Saves User ID instantly to disk"""
    try:
        # Load current list
        with open(config.USERS_FILE, 'r') as f: 
            users = ujson.load(f)
        
        # Only add if new
        if user_id not in users:
            users.append(user_id)
            # Save immediately
            with open(config.USERS_FILE, 'w') as f: 
                ujson.dump(users, f)
    except Exception as e:
        print(f"Stats Error: {e}")

def get_all_users():
    """Returns list of all user IDs"""
    try:
        with open(config.USERS_FILE, 'r') as f: return ujson.load(f)
    except: return []

def log_search(term):
    if len(term) < 3: return
    try:
        with open(config.STATS_FILE, 'r') as f: data = ujson.load(f)
        data["searches"] += 1
        data["top_terms"][term] = data["top_terms"].get(term, 0) + 1
        with open(config.STATS_FILE, 'w') as f: ujson.dump(data, f)
    except: pass

def get_stats():
    try:
        with open(config.USERS_FILE, 'r') as f: users = len(ujson.load(f))
        with open(config.STATS_FILE, 'r') as f: data = ujson.load(f)
        
        top = sorted(data["top_terms"].items(), key=lambda x: x[1], reverse=True)[:5]
        top_str = "\n".join([f"• {k}: {v}" for k,v in top])
        
        return (
            f"📊 **Bot Statistics**\n\n"
            f"👥 Total Users: `{users}`\n"
            f"🔎 Total Searches: `{data['searches']}`\n\n"
            f"🔥 **Top Searches:**\n{top_str}"
        )
    except: return "No stats available yet."