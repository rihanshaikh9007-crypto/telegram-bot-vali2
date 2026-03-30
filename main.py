import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import sqlite3
import random
import string
import os
import time
from datetime import datetime
from flask import Flask
import threading

# Yahan apna bot token dalein
TOKEN = '8609194789:AAFf8IN6eYZ6pAgNLlBDxHGuiiz0FJzHcJc'
bot = telebot.TeleBot(TOKEN, parse_mode='HTML')

ADMIN_ID = 1484173564
APPROVAL_CHANNEL = "@ValiModes_key"

# ================= DATABASE SETUP =================
conn = sqlite3.connect('webseries_bot.db', check_same_thread=False)
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS channels (channel_id TEXT, link TEXT)''')
try: c.execute("ALTER TABLE channels ADD COLUMN style TEXT DEFAULT 'primary'")
except: pass 

c.execute('''CREATE TABLE IF NOT EXISTS join_reqs (user_id INTEGER, channel_id TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, join_date TEXT, coins INTEGER DEFAULT 0, is_banned INTEGER DEFAULT 0, last_bonus REAL DEFAULT 0)''')
c.execute('''CREATE TABLE IF NOT EXISTS pending_refs (user_id INTEGER PRIMARY KEY, referrer_id INTEGER)''')
c.execute('''CREATE TABLE IF NOT EXISTS completed_refs (user_id INTEGER PRIMARY KEY, referrer_id INTEGER)''')
c.execute('''CREATE TABLE IF NOT EXISTS vip_keys (key_code TEXT PRIMARY KEY, duration INTEGER, status TEXT DEFAULT 'UNUSED', used_by INTEGER)''')
c.execute('''CREATE TABLE IF NOT EXISTS settings (name TEXT PRIMARY KEY, value TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS promo_codes (code TEXT PRIMARY KEY, reward INTEGER, max_uses INTEGER, used_count INTEGER DEFAULT 0)''')
c.execute('''CREATE TABLE IF NOT EXISTS promo_users (user_id INTEGER, code TEXT)''')

c.execute("INSERT OR IGNORE INTO settings (name, value) VALUES ('key_link', 'https://www.mediafire.com/file/if3uvvwjbj87lo2/DRIPCLIENT_v6.2_GLOBAL_AP.apks/file')")
c.execute("INSERT OR IGNORE INTO settings (name, value) VALUES ('base_price', '15')") # Dynamic Price Feature
conn.commit()

# ================= SECURITY / ANTI-SPAM =================
user_last_msg = {}
verify_spam = {} # Temp Ban Tracking
temp_channel_data = {}

def flood_check(user_id):
    now = time.time()
    if user_id in user_last_msg and now - user_last_msg[user_id] < 1.0: return True
    user_last_msg[user_id] = now
    return False

def is_user_banned(user_id):
    c.execute("SELECT is_banned FROM users WHERE user_id=?", (user_id,))
    res = c.fetchone()
    return res and res[0] == 1

# ================= FLASK WEB SERVER =================
app = Flask(__name__)
@app.route('/')
def home(): return "V2 Ultimate Bot is Running!"
def run_web(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))


# ================= 👨‍💻 VIP ADMIN COMMANDS =================
@bot.message_handler(commands=['addcoins', 'setprice', 'promo', 'check', 'change'])
def admin_super_commands(message):
    if message.chat.id != ADMIN_ID: return
    cmd = message.text.split()[0]
    
    if cmd == '/addcoins':
        try:
            _, uid, amt = message.text.split()
            uid, amt = int(uid), int(amt)
            c.execute("UPDATE users SET coins = coins + ? WHERE user_id=?", (amt, uid))
            conn.commit()
            bot.reply_to(message, f"✅ {amt} Coins added to {uid}.")
            bot.send_message(uid, f"🎁 Admin ne aapko <b>{amt} Coins</b> bheje hain!")
        except: bot.reply_to(message, "❌ Format: `/addcoins USER_ID COINS`")

    elif cmd == '/setprice':
        try:
            _, price = message.text.split()
            c.execute("UPDATE settings SET value=? WHERE name='base_price'", (price,))
            conn.commit()
            bot.reply_to(message, f"✅ Base Key Price set to {price} Coins.")
        except: bot.reply_to(message, "❌ Format: `/setprice 15`")

    elif cmd == '/promo':
        try:
            _, code, reward, max_u = message.text.split()
            c.execute("INSERT INTO promo_codes VALUES (?, ?, ?, 0)", (code, int(reward), int(max_u)))
            conn.commit()
            bot.reply_to(message, f"✅ <b>Promo Code Created!</b>\nCode: <code>{code}</code>\nReward: {reward} Coins\nUsers Limit: {max_u}")
        except: bot.reply_to(message, "❌ Format: `/promo CODE REWARD MAX_USERS` (e.g., /promo VALIVIP 10 50)")

    elif cmd == '/check':
        try:
            uid = int(message.text.split()[1])
            c.execute("SELECT coins, join_date, is_banned FROM users WHERE user_id=?", (uid,))
            user = c.fetchone()
            if not user: return bot.reply_to(message, "❌ User not found.")
            c.execute("SELECT COUNT(*) FROM completed_refs WHERE referrer_id=?", (uid,))
            refs = c.fetchone()[0]
            status = "🔴 BANNED" if user[2] else "🟢 ACTIVE"
            bot.reply_to(message, f"🕵️ <b>User Info:</b>\n\n🆔 ID: {uid}\n💰 Coins: {user[0]}\n👥 Referrals: {refs}\n📅 Joined: {user[1]}\n📊 Status: {status}")
        except: bot.reply_to(message, "❌ Format: `/check USER_ID`")
        
    elif cmd == '/change':
        new_link = message.text.replace('/change', '').strip()
        if new_link:
            c.execute("UPDATE settings SET value=? WHERE name='key_link'", (new_link,))
            conn.commit()
            bot.reply_to(message, f"✅ <b>Link Updated!</b>\nNew link for keys:\n{new_link}")

# (Admin Panel ke baaki callbacks same as before, no changes needed to core logic)
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.chat.id != ADMIN_ID: return 
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(InlineKeyboardButton("➕ Add Channel", callback_data="add_channel"),
               InlineKeyboardButton("➖ Remove Channel", callback_data="remove_channel"))
    markup.add(InlineKeyboardButton("📋 View Added Channels", callback_data="view_channels"))
    markup.add(InlineKeyboardButton("📊 Stats & Users", callback_data="adm_stats"),
               InlineKeyboardButton("📢 Broadcast", callback_data="adm_broadcast"))
    markup.add(InlineKeyboardButton("🚫 Ban User", callback_data="adm_ban"),
               InlineKeyboardButton("✅ Unban User", callback_data="adm_unban"))
    bot.send_message(message.chat.id, "👨‍💻 <b>Admin Panel V2</b>", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ["add_channel", "remove_channel", "view_channels"] or call.data.startswith("adm_") or call.data.startswith("style_"))
def admin_callbacks(call):
    if call.message.chat.id != ADMIN_ID: return
    if call.data.startswith("style_"):
        style = call.data.split("_")[1]
        data = temp_channel_data.get(call.message.chat.id)
        if data:
            c.execute("INSERT INTO channels (channel_id, link, style) VALUES (?, ?, ?)", (data['ch_id'], data['link'], style))
            conn.commit()
            bot.edit_message_text(f"✅ Channel <code>{data['ch_id']}</code> added!\n🎨 Button: {style.upper()}", chat_id=call.message.chat.id, message_id=call.message.message_id)
            del temp_channel_data[call.message.chat.id]
        return
    if call.data == "add_channel":
        msg = bot.send_message(call.message.chat.id, "🤖 Bot ko channel me Admin banao!\nPhir Channel ID send karo:")
        bot.register_next_step_handler(msg, process_add_channel)
    elif call.data == "view_channels":
        c.execute("SELECT channel_id, link, style FROM channels")
        channels = c.fetchall()
        if not channels: return bot.send_message(call.message.chat.id, "❌ No channels.")
        text = "📋 <b>Added Channels:</b>\n\n"
        for ch in channels: text += f"ID: <code>{ch[0]}</code>\n🎨 Color: {ch[2].upper()}\nLink: {ch[1]}\n\n"
        bot.send_message(call.message.chat.id, text, disable_web_page_preview=True)
    elif call.data == "remove_channel":
        msg = bot.send_message(call.message.chat.id, "🗑️ Channel ID bhejo:")
        bot.register_next_step_handler(msg, lambda m: [c.execute("DELETE FROM channels WHERE channel_id=?", (m.text.strip(),)), conn.commit(), bot.send_message(m.chat.id, "✅ Removed!")])
    elif call.data == "adm_stats":
        c.execute("SELECT COUNT(*) FROM users")
        tot = c.fetchone()[0]
        bot.send_message(call.message.chat.id, f"📊 <b>BOT STATS</b>\n👥 Total Users: {tot}")
    elif call.data == "adm_broadcast":
        msg = bot.send_message(call.message.chat.id, "📢 Broadcast message bhejo:")
        bot.register_next_step_handler(msg, process_broadcast)
    elif call.data == "adm_ban":
        msg = bot.send_message(call.message.chat.id, "🚫 User ID to BAN:")
        bot.register_next_step_handler(msg, lambda m: toggle_ban(m, 1))
    elif call.data == "adm_unban":
        msg = bot.send_message(call.message.chat.id, "✅ User ID to UNBAN:")
        bot.register_next_step_handler(msg, lambda m: toggle_ban(m, 0))

def process_add_channel(message):
    ch_id = message.text.strip()
    try:
        invite_link = bot.create_chat_invite_link(ch_id, creates_join_request=True).invite_link
        temp_channel_data[message.chat.id] = {'ch_id': ch_id, 'link': invite_link}
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("🔵 Blue", callback_data="style_primary"),
            InlineKeyboardButton("🟢 Green", callback_data="style_success"),
            InlineKeyboardButton("🔴 Red", callback_data="style_danger"),
            InlineKeyboardButton("⚪ Grey", callback_data="style_secondary")
        )
        bot.send_message(message.chat.id, "🎨 <b>Color choose karein:</b>", reply_markup=markup)
    except Exception as e: bot.send_message(message.chat.id, f"❌ Error: {e}")

def process_broadcast(message):
    bot.send_message(message.chat.id, "⏳ Broadcasting...")
    c.execute("SELECT user_id FROM users WHERE is_banned=0")
    for u in c.fetchall():
        try: bot.copy_message(u[0], message.chat.id, message.message_id)
        except: pass
    bot.send_message(message.chat.id, "✅ <b>Broadcast Done!</b>")

def toggle_ban(message, status):
    c.execute("UPDATE users SET is_banned=? WHERE user_id=?", (status, int(message.text.strip())))
    conn.commit()
    bot.reply_to(message, "✅ Done!")

# ================= JOIN REQUEST & FORCE SUB DYNAMIC SYSTEM =================
def get_unjoined_channels(user_id):
    try: c.execute("SELECT channel_id, link, style FROM channels")
    except: c.execute("SELECT channel_id, link, 'primary' as style FROM channels")
    channels = c.fetchall()
    unjoined = []
    for ch in channels:
        joined = False
        try:
            if bot.get_chat_member(ch[0], user_id).status in ['member', 'administrator', 'creator']: joined = True
        except: pass
        if not joined:
            c.execute("SELECT * FROM join_reqs WHERE user_id=? AND channel_id=?", (user_id, ch[0]))
            if c.fetchone(): joined = True
        if not joined: unjoined.append(ch)
    return unjoined

def check_user_status(user_id):
    return len(get_unjoined_channels(user_id)) == 0

@bot.chat_join_request_handler()
def handle_join_request(message: telebot.types.ChatJoinRequest):
    c.execute("INSERT INTO join_reqs (user_id, channel_id) VALUES (?, ?)", (message.from_user.id, str(message.chat.id)))
    conn.commit()

@bot.message_handler(commands=['start'])
def start_cmd(message):
    uid = message.from_user.id
    if flood_check(uid) or is_user_banned(uid): return

    c.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    if not c.fetchone():
        c.execute("INSERT INTO users (user_id, username, join_date) VALUES (?, ?, ?)", (uid, message.from_user.username or "Unknown", datetime.now().strftime("%Y-%m-%d")))
        
        # Original Referral System (Immediate Reward)
        args = message.text.split()
        if len(args) > 1 and args[1].isdigit():
            ref_id = int(args[1])
            if ref_id != uid:
                c.execute("SELECT * FROM completed_refs WHERE user_id=?", (uid,))
                if not c.fetchone():
                    c.execute("UPDATE users SET coins = coins + 2 WHERE user_id=?", (ref_id,))
                    c.execute("INSERT INTO completed_refs (user_id, referrer_id) VALUES (?, ?)", (uid, ref_id))
                    conn.commit()
                    try: bot.send_message(ref_id, "🎉 <b>Congrats!</b>\nKisi ne aapke link se bot start kiya hai. <b>+2 Coins</b> Added!")
                    except: pass
        conn.commit()
    send_force_sub(message.chat.id, uid)

def send_force_sub(chat_id, user_id):
    unjoined = get_unjoined_channels(user_id)
    if not unjoined:
        send_main_menu(chat_id)
        return
        
    markup = InlineKeyboardMarkup()
    row = []
    for i, ch in enumerate(unjoined):
        row.append(InlineKeyboardButton(f"Join Channel", url=ch[1], style=ch[2]))
        if len(row) == 2:
            markup.add(*row)
            row = []
    if row: markup.add(*row)
    markup.add(InlineKeyboardButton("✅ Done !!", callback_data="verify_channels", style="success"))
    
    video_url = "https://files.catbox.moe/4hbu2q.mp4" 
    caption = """💎 𝗪𝗘𝗟𝗖𝗢𝗠𝗘 𝗧𝗢 𝗩𝗔𝗟𝗜 𝗠𝗢𝗗𝗦 𝗗𝗥𝗜𝗣 𝗞𝗘𝗬 

🎮 𝗬𝗼𝘂𝗿 𝗙𝗥𝗘𝗘 𝗙𝗜𝗥𝗘 𝗔𝗣𝗞𝗠𝗢𝗗 𝗞𝗘𝗬 𝗶𝘀 𝗷𝘂𝘀𝘁 𝗼𝗻𝗲 𝘀𝘁𝗲𝗽 𝗮𝘄𝗮𝘆! 🔥
━━━━━━━━━━━━━━━

🛠️ 𝗠𝗢𝗗 𝗙𝗘𝗔𝗧𝗨𝗥𝗘𝗦:
✅ 𝗦𝗶𝗹𝗲𝗻𝘁 𝗞𝗶𝗹𝗹 / 𝗦𝗶𝗹𝗲𝗻𝘁 𝗔𝗶𝗺
✅ 𝗠𝗮𝗴𝗻𝗲𝘁𝗶𝗰 𝗔𝗶𝗺
✅ 𝗔𝗻𝘁𝗶-𝗧𝗮𝘁𝘂
✅ 𝗚𝗵𝗼𝘀𝘁 𝗛𝗮𝗰𝗸 / 𝗦𝗽𝗲𝗲𝗱 𝗛𝗮𝗰𝗸
✅ 𝗘𝗦𝗣 (𝗡𝗮𝗺𝗲, 𝗟𝗶𝗻𝗲, 𝗕𝗼𝘅)

━━━━━━━━━━━━━━━
🚨 𝗔𝗖𝗖𝗘𝗦𝗦 𝗚𝗘𝗧 𝗞𝗔𝗥𝗡𝗘 𝗞𝗘 𝗟𝗜𝗬𝗘

📢 𝗡𝗶𝗰𝗵𝗲 𝗱𝗶𝘆𝗲 𝗴𝗮𝘆𝗲 𝘀𝗮𝗿𝗲 𝗰𝗵𝗮𝗻𝗻𝗲𝗹𝘀 𝗝𝗢𝗜𝗡 𝗸𝗮𝗿𝗻𝗮 𝗭𝗔𝗥𝗨𝗥𝗜 𝗵𝗮𝗶
━━━━━━━━━━━━━━━
1️⃣ 𝗦𝗮𝗯𝗵𝗶 𝗰𝗵𝗮𝗻𝗻𝗲𝗹𝘀 𝗝𝗼𝗶𝗻 𝗸𝗮𝗿𝗲𝗶𝗻
2️⃣ 𝗝𝗼𝗶𝗻 𝗸𝗲 𝗯𝗮𝗮𝗱 “✅ 𝗗𝗼𝗻𝗲 !!” 𝗯𝘂𝘁𝘁𝗼𝗻 𝗽𝗮𝗿 𝗰𝗹𝗶𝗰𝗸 𝗸𝗮𝗿𝗲𝗶𝗻
━━━━━━━━━━━━━━━"""
    bot.send_video(chat_id, video_url, caption=caption, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "verify_channels")
def verify_callback(call):
    uid = call.from_user.id
    if is_user_banned(uid): return
    
    # 🔥 TEMP BAN FEATURE FOR SPAMMERS
    now = time.time()
    if uid in verify_spam:
        if now < verify_spam[uid]['ban_until']:
            return bot.answer_callback_query(call.id, "⚠️ Spamming mat karo! 5 minute baad try karna.", show_alert=True)
    else: verify_spam[uid] = {'count': 0, 'ban_until': 0}

    unjoined = get_unjoined_channels(uid)
    if not unjoined:
        verify_spam.pop(uid, None) # Clear strikes
        bot.delete_message(call.message.chat.id, call.message.message_id)
        send_main_menu(call.message.chat.id)
        bot.answer_callback_query(call.id, "✅ Verified successfully!", show_alert=False)
    else:
        # Increase strike
        verify_spam[uid]['count'] += 1
        if verify_spam[uid]['count'] >= 4:
            verify_spam[uid]['ban_until'] = now + 300 # 5 min ban
            return bot.answer_callback_query(call.id, "🚫 Aapko 5 minute ke liye block kiya gaya hai. Pehle channels join karein!", show_alert=True)

        markup = InlineKeyboardMarkup()
        row = []
        for ch in unjoined:
            row.append(InlineKeyboardButton(f"Join Channel", url=ch[1], style=ch[2]))
            if len(row) == 2:
                markup.add(*row)
                row = []
        if row: markup.add(*row)
        markup.add(InlineKeyboardButton("🔄 Try Again", callback_data="verify_channels", style="danger"))
        
        try:
            bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup)
            bot.answer_callback_query(call.id, "❌ Aapne sabhi channels join nahi kiye!", show_alert=True)
        except: bot.answer_callback_query(call.id, "❌ Pehle join karo fir dabao!", show_alert=True)


# ================= MAIN MENU & VIP FEATURES =================
def send_main_menu(chat_id):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton("👤 My Account"), KeyboardButton("🔗 Refer & Earn"))
    markup.add(KeyboardButton("🛒 VIP Key Shop"), KeyboardButton("🎁 Daily Bonus"))
    markup.add(KeyboardButton("🏆 Leaderboard"), KeyboardButton("🎟️ Redeem Promo"))
    bot.send_message(chat_id, "✅ Use the menu below to navigate:", reply_markup=markup)

@bot.message_handler(func=lambda m: True)
def text_commands(message):
    uid = message.from_user.id
    if flood_check(uid) or is_user_banned(uid): return

    if not check_user_status(uid):
        hide_markup = telebot.types.ReplyKeyboardRemove()
        bot.reply_to(message, "❌ <b>Access Denied!</b>\n\nPehle channels join karein.", reply_markup=hide_markup)
        return send_force_sub(message.chat.id, uid)
    
    c.execute("SELECT coins, last_bonus FROM users WHERE user_id=?", (uid,))
    res = c.fetchone()
    if not res: return
    coins, last_bonus = res[0], res[1]
    text = message.text

    if text == "👤 My Account":
        bot.send_message(uid, f"👤 <b>Account Stats</b>\n\n🆔 User ID: <code>{uid}</code>\n💰 Coins: <b>{coins}</b>")
        
    elif text == "🔗 Refer & Earn":
        bot_usr = bot.get_me().username
        bot.send_message(uid, f"📢 <b>REFER & EARN</b>\n\nInvite friends & get <b>2 Coins</b> per join!\n\n🔗 Your Link:\nhttps://t.me/{bot_usr}?start={uid}")

    elif text == "🎁 Daily Bonus":
        now = time.time()
        if now - float(last_bonus) > 86400: # 24 hours
            c.execute("UPDATE users SET coins = coins + 2, last_bonus = ? WHERE user_id=?", (now, uid))
            conn.commit()
            bot.send_message(uid, "🎉 <b>Daily Bonus Claimed!</b>\nAapko <b>2 Coins</b> mil gaye hain. Kal wapas aana!")
        else:
            left = int((86400 - (now - float(last_bonus))) / 3600)
            bot.send_message(uid, f"⏳ <b>Wait!</b>\nAapne aaj ka bonus le liya hai. Agla bonus <b>{left} ghante</b> baad milega.")

    elif text == "🏆 Leaderboard":
        c.execute("SELECT referrer_id, COUNT(*) as c FROM completed_refs GROUP BY referrer_id ORDER BY c DESC LIMIT 5")
        top = c.fetchall()
        msg = "🏆 <b>TOP REFERRERS</b> 🏆\n\n"
        for i, t in enumerate(top): msg += f"{i+1}. User <code>{t[0]}</code> - {t[1]} Invites\n"
        bot.send_message(uid, msg)

    elif text == "🎟️ Redeem Promo":
        msg = bot.send_message(uid, "🎫 Apna Promo Code enter karein:")
        bot.register_next_step_handler(msg, process_promo)

    elif text == "🛒 VIP Key Shop":
        c.execute("SELECT value FROM settings WHERE name='base_price'")
        bp = int(c.fetchone()[0])
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton(f"🔑 1-Day VIP Key ({bp} Coins)", callback_data=f"buy_1_{bp}"),
            InlineKeyboardButton(f"🔑 3-Day VIP Key ({bp*2} Coins)", callback_data=f"buy_3_{bp*2}"),
            InlineKeyboardButton(f"🔑 7-Day VIP Key ({bp*4} Coins)", callback_data=f"buy_7_{bp*4}")
        )
        bot.send_message(uid, f"🛒 <b>VIP KEY SHOP</b>\n\nAapke Coins: <b>{coins}</b>\nSelect duration:", reply_markup=markup)

def process_promo(message):
    uid, code = message.from_user.id, message.text.strip().upper()
    c.execute("SELECT reward, max_uses, used_count FROM promo_codes WHERE code=?", (code,))
    promo = c.fetchone()
    if not promo: return bot.send_message(uid, "❌ Invalid Promo Code!")
    if promo[2] <= promo[1]: return bot.send_message(uid, "❌ Ye code expire ho chuka hai (Limit Reached)!")
    c.execute("SELECT * FROM promo_users WHERE user_id=? AND code=?", (uid, code))
    if c.fetchone(): return bot.send_message(uid, "❌ Aapne ye code pehle hi use kar liya hai!")
    
    c.execute("UPDATE users SET coins = coins + ? WHERE user_id=?", (promo[0], uid))
    c.execute("UPDATE promo_codes SET used_count = used_count + 1 WHERE code=?", (code,))
    c.execute("INSERT INTO promo_users VALUES (?, ?)", (uid, code))
    conn.commit()
    bot.send_message(uid, f"🎉 <b>Success!</b>\nAapko Promo Code se <b>{promo[0]} Coins</b> mil gaye hain!")

# ================= SHOP & APPROVAL LOGIC =================
@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def handle_shop_buy(call):
    uid = call.from_user.id
    _, days, price = call.data.split("_")
    days, price = int(days), int(price)
    
    # 🔥 FORCE SUB DOUBLE CHECK BEFORE BUY
    if not check_user_status(uid):
        return bot.answer_callback_query(call.id, "❌ Pehle saare channels join karo!", show_alert=True)
        
    c.execute("SELECT coins FROM users WHERE user_id=?", (uid,))
    coins = c.fetchone()[0]
    
    if coins >= price:
        c.execute("UPDATE users SET coins = coins - ? WHERE user_id=?", (price, uid))
        conn.commit()
        bot.delete_message(call.message.chat.id, call.message.message_id)
        
        req_text = f"🆕 <b>New Key Request ({days}-Day VIP)</b>\n\n👤 <b>User:</b> {call.from_user.first_name}\n🆔 <b>ID:</b> <code>{uid}</code>\n⏰ <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("✅ APPROVAL", callback_data=f"approve_{uid}_{price}"),
            InlineKeyboardButton("❌ REJECTED", callback_data=f"reject_{uid}_{price}")
        )
        try:
            bot.send_message(APPROVAL_CHANNEL, req_text, reply_markup=markup)
            bot.send_message(uid, "⏳ <b>Request Sent!</b>\nAapki VIP Key ki request Admin ko bhej di gayi hai.\n\n⚠️ <b>WARNING:</b> Agar aapne <b>@ValiModes_key</b> leave kiya toh request REJECT hogi!")
        except:
            c.execute("UPDATE users SET coins = coins + ? WHERE user_id=?", (price, uid))
            conn.commit()
            bot.send_message(uid, "❌ Error: Admin approval setup incomplete. Coins refunded.")
    else:
        bot.answer_callback_query(call.id, f"❌ Aapke paas {price} coins nahi hain!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith("approve_") or call.data.startswith("reject_"))
def handle_approval(call):
    if call.from_user.id != ADMIN_ID: return bot.answer_callback_query(call.id, "❌ Not Admin", show_alert=True)
    
    parts = call.data.split("_")
    action, uid, refund = parts[0], int(parts[1]), int(parts[2])

    if action == "approve":
        try: bot.edit_message_text(f"{call.message.text}\n\n✅ <b>APPROVED</b>", chat_id=call.message.chat.id, message_id=call.message.message_id)
        except: pass
        send_dynamic_key(uid)
    elif action == "reject":
        try: bot.edit_message_text(f"{call.message.text}\n\n❌ <b>REJECTED</b>", chat_id=call.message.chat.id, message_id=call.message.message_id)
        except: pass
        c.execute("UPDATE users SET coins = coins + ? WHERE user_id=?", (refund, uid))
        conn.commit()
        try: bot.send_message(uid, "❌ <b>Request Rejected!</b>\nAapke coins refund kar diye gaye hain. Kripya rules follow karein.")
        except: pass

def send_dynamic_key(chat_id):
    key = f"{random.randint(1000000000, 9999999999)}"
    c.execute("SELECT value FROM settings WHERE name='key_link'")
    res = c.fetchone()
    dynamic_link = res[0] if res else "No link found"
    text = f"Key - <code>{key}</code>\n\nDRIP SCINET APK - {dynamic_link}"
    try: bot.send_message(chat_id, f"🎉 <b>Congratulations!</b>\nAdmin ne approve kar diya hai👇\n\n{text}", disable_web_page_preview=True)
    except: pass

# ================= START SYSTEM =================
if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    print("V2 Ultimate VIP Bot is running...")
    bot.infinity_polling(allowed_updates=telebot.util.update_types)
