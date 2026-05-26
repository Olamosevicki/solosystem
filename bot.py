import os
import json
import logging
import threading
from datetime import datetime, time
import pytz
from flask import Flask, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
USER_ID    = int(os.environ.get("USER_ID", "0"))
MINI_APP_URL = os.environ.get("MINI_APP_URL", "")
TIMEZONE   = pytz.timezone("Africa/Lagos")
JSONBIN_ID  = os.environ.get("JSONBIN_ID", "")
JSONBIN_KEY = os.environ.get("JSONBIN_KEY", "")
JSONBIN_URL = f"https://api.jsonbin.io/v3/b/{JSONBIN_ID}"
PORT       = int(os.environ.get("PORT", 8080))

# ── XP CURVE ──────────────────────────────────────────────────────────────────
def xp_for_level(level):
    return int(100 * (1.4 ** (level - 1)))

def total_xp_for_level(level):
    return sum(xp_for_level(l) for l in range(1, level))

# ── STATS ─────────────────────────────────────────────────────────────────────
STATS = ["Spirit", "Wealth", "Mind", "Body", "Relationships", "Creativity"]
STAT_EMOJI = {
    "Spirit":        "⚔️",
    "Wealth":        "💰",
    "Mind":          "🧠",
    "Body":          "💪",
    "Relationships": "🤝",
    "Creativity":    "✨",
}

# ── QUESTS ────────────────────────────────────────────────────────────────────
QUESTS = [
    ("morning_prayer",   "Morning Prayer",            "05:10", 20,  40, "Spirit",        "daily"),
    ("bible_study",      "Bible Study",               "05:30", 40,  40, "Spirit",        "daily"),
    ("workout",          "Workout",                   "06:10", 45,  35, "Body",          "daily"),
    ("night_prayer",     "Night Prayer",              "21:00", 15,  30, "Spirit",        "daily"),
    ("mon_ghl",          "GHL Business",              "13:30", 120, 50, "Wealth",        [0]),
    ("mon_study",        "Study Session",             "17:45", 75,  45, "Mind",          [0]),
    ("mon_uzaire",       "Uzaire",                    "18:30", 30,  25, "Wealth",        [0]),
    ("mon_laundry",      "Laundry",                   "19:00", 45,  15, "Body",          [0]),
    ("mon_family",       "Family Check-in",           "21:00", 15,  20, "Relationships", [0]),
    ("tue_one_thing",    "That One Thing",            "07:30", 90,  40, "Creativity",    [1]),
    ("tue_ghl1",         "GHL Business pt.1",         "12:30", 30,  25, "Wealth",        [1]),
    ("tue_ghl2",         "GHL Business pt.2",         "16:00", 90,  35, "Wealth",        [1]),
    ("tue_cooking",      "Cooking",                   "19:00", 60,  15, "Body",          [1]),
    ("tue_study",        "Study Session",             "20:00", 60,  45, "Mind",          [1]),
    ("tue_uzaire",       "Uzaire",                    "21:00", 30,  25, "Wealth",        [1]),
    ("wed_study_am",     "Morning Study",             "07:30", 60,  40, "Mind",          [2]),
    ("wed_ghl",          "GHL Business",              "14:00", 60,  35, "Wealth",        [2]),
    ("wed_uzaire",       "Uzaire",                    "18:30", 30,  25, "Wealth",        [2]),
    ("wed_laundry",      "Laundry",                   "19:00", 45,  15, "Body",          [2]),
    ("wed_study_pm",     "Evening Study",             "19:45", 75,  40, "Mind",          [2]),
    ("thu_ghl1",         "GHL Business pt.1",         "12:30", 30,  25, "Wealth",        [3]),
    ("thu_ghl2",         "GHL Business pt.2",         "16:00", 90,  35, "Wealth",        [3]),
    ("thu_siblings",     "Siblings Check-in",         "17:30", 20,  20, "Relationships", [3]),
    ("thu_discipleship", "Discipleship Meeting",      "18:00", 90,  35, "Spirit",        [3]),
    ("thu_study",        "Study Session",             "20:00", 30,  25, "Mind",          [3]),
    ("fri_study",        "Study Session [SACRED]",    "07:30", 180, 60, "Mind",          [4]),
    ("fri_one_thing",    "That One Thing",            "10:30", 90,  40, "Creativity",    [4]),
    ("fri_ghl",          "GHL Business [POWER]",      "12:30", 120, 60, "Wealth",        [4]),
    ("fri_uzaire",       "Uzaire",                    "14:30", 30,  25, "Wealth",        [4]),
    ("fri_siblings",     "Siblings Check-in",         "16:00", 30,  20, "Relationships", [4]),
    ("fri_church",       "Church",                    "18:00", 120, 30, "Spirit",        [4]),
    ("sat_study",        "Study Session",             "07:30", 180, 60, "Mind",          [5]),
    ("sat_one_thing",    "That One Thing",            "10:30", 90,  40, "Creativity",    [5]),
    ("sat_ghl",          "GHL Business",              "12:00", 60,  40, "Wealth",        [5]),
    ("sat_choir",        "Choir Rehearsal",           "14:00", 240, 35, "Spirit",        [5]),
    ("sat_family",       "Family Rotation Call",      "19:00", 30,  25, "Relationships", [5]),
    ("sat_uzaire",       "Uzaire",                    "19:30", 30,  25, "Wealth",        [5]),
    ("sun_one_thing",    "That One Thing",            "07:10", 90,  40, "Creativity",    [6]),
    ("sun_church",       "Church",                    "09:00", 180, 35, "Spirit",        [6]),
    ("sun_study",        "Study Session",             "16:00", 120, 50, "Mind",          [6]),
    ("sun_cooking",      "Cooking",                   "18:00", 60,  15, "Body",          [6]),
    ("sun_parents",      "Parents Call",              "19:00", 30,  25, "Relationships", [6]),
    ("sun_ghl",          "GHL Light Prep",            "20:00", 60,  30, "Wealth",        [6]),
]

# ── DATA ──────────────────────────────────────────────────────────────────────
def load_data():
    try:
        logger.info(f"Loading from JSONBin: {JSONBIN_URL}")
        logger.info(f"Key present: {bool(JSONBIN_KEY)}")
        res = req.get(JSONBIN_URL + "/latest",
            headers={"X-Master-Key": JSONBIN_KEY,
                     "X-Bin-Meta": "false"}, timeout=10)
        logger.info(f"JSONBin response: {res.status_code}")
        if res.ok:
            data = res.json()
            logger.info(f"JSONBin data keys: {list(data.keys())}")
            return data
    except Exception as e:
        logger.error(f"JSONBin load failed: {e}")
    return {
        "level": 2,
        "total_xp": total_xp_for_level(2),
        "stats": {s: 10 for s in STATS},
        "completed_today": [],
        "pending_penalties": [],
        "streak": 0,
        "last_reset": str(datetime.now(TIMEZONE).date()),
        "history": []
    }

def save_data(data):
    try:
        req.put(JSONBIN_URL,
            json=data,
            headers={
                "X-Master-Key": JSONBIN_KEY,
                "Content-Type": "application/json"
            }, timeout=10)
    except Exception as e:
        logger.error(f"JSONBin save failed: {e}")

def check_level_up(data):
    leveled_up = False
    while True:
        needed = xp_for_level(data["level"])
        current_level_xp = data["total_xp"] - total_xp_for_level(data["level"])
        if current_level_xp >= needed:
            data["level"] += 1
            # Bonus on level up — all stats +1
            for s in STATS:
                data["stats"][s] = min(100, data["stats"][s] + 1)
            leveled_up = True
        else:
            break
    return leveled_up

def get_xp_progress(data):
    level_start = total_xp_for_level(data["level"])
    level_xp = data["total_xp"] - level_start
    needed = xp_for_level(data["level"])
    return level_xp, needed

def get_todays_quests():
    today = datetime.now(TIMEZONE).weekday()
    return [q for q in QUESTS if q[6] == "daily" or today in q[6]]

def apply_decay(data):
    today = datetime.now(TIMEZONE).date()
    last = datetime.strptime(data["last_reset"], "%Y-%m-%d").date()
    if today > last:
        missed = [q for q in get_todays_quests() if q[0] not in data["completed_today"]]
        for q in missed:
            data["stats"][q[5]] = max(0, data["stats"][q[5]] - 2)
            if q[0] not in data["pending_penalties"]:
                data["pending_penalties"].append(q[0])
        data["completed_today"] = []
        data["last_reset"] = str(today)
        data["streak"] = data["streak"] + 1 if not missed else 0
    return data

def build_bar(value, max_val, length=10, filled="█", empty="░"):
    return filled * int((value / max_val) * length) + empty * (length - int((value / max_val) * length))

def build_status_message(data):
    level_xp, needed = get_xp_progress(data)
    xp_bar = build_bar(level_xp, needed)
    pct = int((level_xp / needed) * 100)
    lines = [
        "╔══════════════════════════╗",
        "║   ⚡ THE SYSTEM — STATUS  ║",
        "╚══════════════════════════╝",
        "",
        f"🎮 LEVEL:   {data['level']}",
        f"🔥 STREAK:  {data['streak']} days",
        "",
        "━━━ XP PROGRESS ━━━",
        f"{xp_bar} {pct}%",
        f"{level_xp} / {needed} XP → Level {data['level']+1}",
        "",
        "━━━ STATS ━━━",
    ]
    for stat in STATS:
        val = data["stats"][stat]
        lines.append(f"{STAT_EMOJI[stat]} {stat:<14} {build_bar(val,100,8)} {val}")
    if data["pending_penalties"]:
        lines.append(f"\n⚠️ PENALTIES: {len(data['pending_penalties'])} pending")
    return "\n".join(lines)

# ── FLASK API (for Mini App live data) ───────────────────────────────────────
flask_app = Flask(__name__)

@flask_app.route("/stats")
def get_stats():
    data = load_data()
    data = apply_decay(data)
    save_data(data)
    level_xp, needed = get_xp_progress(data)
    pct = int((level_xp / needed) * 100)
    todays = get_todays_quests()
    quests_out = []
    for q in todays:
        quests_out.append({
            "id": q[0], "name": q[1], "time": q[2],
            "dur": q[3], "xp": q[4], "stat": q[5],
            "done": q[0] in data["completed_today"]
        })
    return jsonify({
        "level": data["level"],
        "total_xp": data["total_xp"],
        "level_xp": level_xp,
        "needed": needed,
        "pct": pct,
        "stats": data["stats"],
        "streak": data["streak"],
        "penalties": len(data["pending_penalties"]),
        "quests": quests_out,
    })

@flask_app.route("/health")
def health():
    return jsonify({"status": "online", "system": "⚡ THE SYSTEM"})

def run_flask():
    flask_app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)

# ── TELEGRAM HANDLERS ─────────────────────────────────────────────────────────
def mini_btn():
    if not MINI_APP_URL:
        return None
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("⚡ Open The System", web_app=WebAppInfo(url=MINI_APP_URL))
    ]])

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != USER_ID: return
    data = load_data(); data = apply_decay(data); save_data(data)
    await update.message.reply_text(
        "⚡ *THE SYSTEM — ONLINE*\n\nWelcome back, Player.\n\n"
        "Commands:\n"
        "/status — View your stats\n"
        "/quests — Today's quest list\n"
        "/done [quest] — Complete a quest\n"
        "/penalty — Penalty quests\n"
        "/export — Sync code\n"
        "/help — All commands",
        parse_mode="Markdown", reply_markup=mini_btn()
    )

async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != USER_ID: return
    data = load_data(); data = apply_decay(data); save_data(data)
    await update.message.reply_text(
        f"```\n{build_status_message(data)}\n```",
        parse_mode="Markdown", reply_markup=mini_btn()
    )

async def cmd_quests(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != USER_ID: return
    data = load_data(); data = apply_decay(data); save_data(data)
    todays = get_todays_quests()
    lines = ["⚡ *TODAY'S QUEST LOG*\n"]
    for q in todays:
        done = q[0] in data["completed_today"]
        lines.append(f"{'✅' if done else '🔲'} {STAT_EMOJI[q[5]]} *{q[1]}*")
        lines.append(f"   🕐 {q[2]} | ⏱ {q[3]}m | +{q[4]}XP")
    if data["pending_penalties"]:
        lines.append(f"\n⚠️ *PENALTIES: {len(data['pending_penalties'])} pending*")
    keyboard = []
    for q in [q for q in todays if q[0] not in data["completed_today"]][:8]:
        keyboard.append([InlineKeyboardButton(f"✅ {q[1]}", callback_data=f"done_{q[0]}")])
    if MINI_APP_URL:
        keyboard.append([InlineKeyboardButton("⚡ Open The System", web_app=WebAppInfo(url=MINI_APP_URL))])
    await update.message.reply_text(
        "\n".join(lines), parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
    )

async def complete_quest(qid, data):
    matched = next((q for q in QUESTS if q[0] == qid), None)
    if not matched or qid in data["completed_today"]:
        return None, None, False
    qid_, name, t, dur, xp, stat, days = matched
    data["completed_today"].append(qid_)
    data["total_xp"] += xp
    data["stats"][stat] = min(100, data["stats"][stat] + 3)
    if qid_ in data["pending_penalties"]:
        data["pending_penalties"].remove(qid_)
    leveled_up = check_level_up(data)
    save_data(data)
    return matched, leveled_up, True

async def cmd_done(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != USER_ID: return
    data = load_data(); data = apply_decay(data)
    args = " ".join(ctx.args).lower() if ctx.args else ""
    matched = next((q for q in get_todays_quests() if args in q[1].lower() or args in q[0].lower()), None)
    if not matched:
        await update.message.reply_text("Quest not found. Use /quests to see today's quests."); return
    if matched[0] in data["completed_today"]:
        await update.message.reply_text(f"✅ *{matched[1]}* already completed!", parse_mode="Markdown"); return
    q, leveled_up, _ = await complete_quest(matched[0], data)
    level_xp, needed = get_xp_progress(data)
    msg = (f"⚡ *QUEST COMPLETE*\n\n{STAT_EMOJI[q[5]]} *{q[1]}*\n+{q[4]} XP | +3 {q[5]}\n\n"
           f"LVL {data['level']} {build_bar(level_xp,needed)} {int((level_xp/needed)*100)}%")
    if leveled_up:
        msg += f"\n\n🎉 *LEVEL UP! You are now Level {data['level']}!*\nAll stats +1"
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=mini_btn())

async def button_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if update.effective_user.id != USER_ID: return
    await query.answer()
    if not query.data.startswith("done_"): return
    qid = query.data[5:]
    data = load_data(); data = apply_decay(data)
    if qid in data["completed_today"]:
        await query.edit_message_text("✅ Already completed!", parse_mode="Markdown"); return
    q, leveled_up, ok = await complete_quest(qid, data)
    if not ok or not q: return
    level_xp, needed = get_xp_progress(data)
    msg = (f"⚡ *QUEST COMPLETE*\n\n{STAT_EMOJI[q[5]]} *{q[1]}*\n+{q[4]} XP | +3 {q[5]}\n\n"
           f"LVL {data['level']} {build_bar(level_xp,needed)} {int((level_xp/needed)*100)}%")
    if leveled_up:
        msg += f"\n\n🎉 *LEVEL UP! You are now Level {data['level']}!*\nAll stats +1"
    keyboard = [[InlineKeyboardButton("⚡ Open The System", web_app=WebAppInfo(url=MINI_APP_URL))]] if MINI_APP_URL else []
    await query.edit_message_text(msg, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None)

async def cmd_penalty(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != USER_ID: return
    data = load_data()
    if not data["pending_penalties"]:
        await update.message.reply_text("✅ No penalty quests. You're clean, Player."); return
    lines = ["⚠️ *PENALTY QUESTS*\n"]
    keyboard = []
    for qid in data["pending_penalties"]:
        q = next((q for q in QUESTS if q[0] == qid), None)
        if q:
            lines.append(f"🔴 {STAT_EMOJI[q[5]]} *{q[1]}* (+{q[4]} XP)")
            keyboard.append([InlineKeyboardButton(f"✅ Complete: {q[1]}", callback_data=f"done_{qid}")])
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard))

async def cmd_export(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != USER_ID: return
    data = load_data()
    stats_str = ",".join(str(data["stats"][s]) for s in STATS)
    code = f"LVL:{data['level']}|XP:{data['total_xp']}|STATS:{stats_str}|STREAK:{data['streak']}|PENALTIES:{len(data['pending_penalties'])}"
    await update.message.reply_text(
        f"⚡ *SYNC CODE*\n\n`{code}`\n\nPaste in the Mini App sync tab if needed.",
        parse_mode="Markdown"
    )

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != USER_ID: return
    await update.message.reply_text(
        "⚡ *THE SYSTEM — COMMANDS*\n\n"
        "/start — Boot up\n/status — Stats dashboard\n"
        "/quests — Today's quests\n/done [name] — Complete quest\n"
        "/penalty — Penalty quests\n/export — Sync code\n/help — This message",
        parse_mode="Markdown", reply_markup=mini_btn()
    )

# ── SCHEDULED NOTIFICATIONS ───────────────────────────────────────────────────
async def send_quest_notification(context: ContextTypes.DEFAULT_TYPE):
    quest = context.job.data
    qid, name, t, dur, xp, stat, days = quest
    data = load_data()
    if qid in data["completed_today"]: return
    keyboard = [[InlineKeyboardButton("✅ Mark Complete", callback_data=f"done_{qid}")]]
    if MINI_APP_URL:
        keyboard.append([InlineKeyboardButton("⚡ Open The System", web_app=WebAppInfo(url=MINI_APP_URL))])
    await context.bot.send_message(
        chat_id=USER_ID,
        text=(f"⚡ *QUEST AVAILABLE*\n\n{STAT_EMOJI[stat]} *{name}*\n"
              f"⏱ {dur} mins | 💎 +{xp} XP | +3 {stat}\n\nTap below when complete."),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

def schedule_quests(app):
    for quest in QUESTS:
        qid, name, t, dur, xp, stat, days = quest
        hour, minute = map(int, t.split(":"))
        if days == "daily":
            app.job_queue.run_daily(
                send_quest_notification,
                time=time(hour, minute, tzinfo=TIMEZONE),
                data=quest, name=f"quest_{qid}"
            )
        else:
            for day in days:
                app.job_queue.run_daily(
                    send_quest_notification,
                    time=time(hour, minute, tzinfo=TIMEZONE),
                    days=(day,), data=quest, name=f"quest_{qid}_{day}"
                )

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    # Start Flask in background thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info(f"⚡ Flask API running on port {PORT}")

    # Start Telegram bot
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("status",  cmd_status))
    app.add_handler(CommandHandler("quests",  cmd_quests))
    app.add_handler(CommandHandler("done",    cmd_done))
    app.add_handler(CommandHandler("penalty", cmd_penalty))
    app.add_handler(CommandHandler("export",  cmd_export))
    app.add_handler(CommandHandler("help",    cmd_help))
    app.add_handler(CallbackQueryHandler(button_callback))
    schedule_quests(app)
    logger.info("⚡ THE SYSTEM IS ONLINE")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
