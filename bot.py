import os
import json
import asyncio
import logging
from datetime import datetime, time, timedelta
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── CONFIG ────────────────────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
USER_ID    = int(os.environ.get("USER_ID", "0"))
TIMEZONE   = pytz.timezone("Africa/Lagos")
DATA_FILE  = "player_data.json"

# ── XP CURVE (Solo Leveling style — gets harder) ─────────────────────────────
def xp_for_level(level):
    """XP needed to reach next level from current level"""
    return int(100 * (1.4 ** (level - 1)))

def total_xp_for_level(level):
    """Total XP needed to reach this level from level 1"""
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

# ── QUESTS (your actual schedule) ────────────────────────────────────────────
# Format: (quest_id, name, time_str, duration_mins, xp, stat, days)
# days: list of weekday numbers 0=Mon,1=Tue,...,6=Sun or "daily"
QUESTS = [
    # ── DAILY (every day) ────────────────────────────────────────────────────
    ("morning_prayer",   "Morning Prayer",           "05:10", 20,  40, "Spirit",        "daily"),
    ("bible_study",      "Bible Study",              "05:30", 40,  40, "Spirit",        "daily"),
    ("workout",          "Workout",                  "06:10", 45,  35, "Body",          "daily"),
    ("night_prayer",     "Night Prayer",             "21:00", 15,  30, "Spirit",        "daily"),

    # ── MONDAY ───────────────────────────────────────────────────────────────
    ("mon_ghl",          "GHL Business",             "13:30", 120, 50, "Wealth",        [0]),
    ("mon_study",        "Study Session",            "17:45", 75,  45, "Mind",          [0]),
    ("mon_uzaire",       "Uzaire",                   "18:30", 30,  25, "Wealth",        [0]),
    ("mon_laundry",      "Laundry",                  "19:00", 45,  15, "Body",          [0]),
    ("mon_family",       "Family Check-in",          "21:00", 15,  20, "Relationships", [0]),

    # ── TUESDAY ──────────────────────────────────────────────────────────────
    ("tue_one_thing",    "That One Thing",           "07:30", 90,  40, "Creativity",    [1]),
    ("tue_ghl1",         "GHL Business pt.1",        "12:30", 30,  25, "Wealth",        [1]),
    ("tue_ghl2",         "GHL Business pt.2",        "16:00", 90,  35, "Wealth",        [1]),
    ("tue_cooking",      "Cooking",                  "19:00", 60,  15, "Body",          [1]),
    ("tue_study",        "Study Session",            "20:00", 60,  45, "Mind",          [1]),
    ("tue_uzaire",       "Uzaire",                   "21:00", 30,  25, "Wealth",        [1]),

    # ── WEDNESDAY ────────────────────────────────────────────────────────────
    ("wed_study_am",     "Morning Study",            "07:30", 60,  40, "Mind",          [2]),
    ("wed_ghl",          "GHL Business",             "14:00", 60,  35, "Wealth",        [2]),
    ("wed_uzaire",       "Uzaire",                   "18:30", 30,  25, "Wealth",        [2]),
    ("wed_laundry",      "Laundry",                  "19:00", 45,  15, "Body",          [2]),
    ("wed_study_pm",     "Evening Study",            "19:45", 75,  40, "Mind",          [2]),

    # ── THURSDAY ─────────────────────────────────────────────────────────────
    ("thu_ghl1",         "GHL Business pt.1",        "12:30", 30,  25, "Wealth",        [3]),
    ("thu_ghl2",         "GHL Business pt.2",        "16:00", 90,  35, "Wealth",        [3]),
    ("thu_siblings",     "Siblings Check-in",        "17:30", 20,  20, "Relationships", [3]),
    ("thu_discipleship", "Discipleship Meeting",     "18:00", 90,  35, "Spirit",        [3]),
    ("thu_study",        "Study Session",            "20:00", 30,  25, "Mind",          [3]),

    # ── FRIDAY ───────────────────────────────────────────────────────────────
    ("fri_study",        "Study Session [SACRED]",   "07:30", 180, 60, "Mind",          [4]),
    ("fri_one_thing",    "That One Thing",           "10:30", 90,  40, "Creativity",    [4]),
    ("fri_ghl",          "GHL Business [POWER]",     "12:30", 120, 60, "Wealth",        [4]),
    ("fri_uzaire",       "Uzaire",                   "14:30", 30,  25, "Wealth",        [4]),
    ("fri_siblings",     "Siblings Check-in",        "16:00", 30,  20, "Relationships", [4]),
    ("fri_church",       "Church",                   "18:00", 120, 30, "Spirit",        [4]),

    # ── SATURDAY ─────────────────────────────────────────────────────────────
    ("sat_study",        "Study Session",            "07:30", 180, 60, "Mind",          [5]),
    ("sat_one_thing",    "That One Thing",           "10:30", 90,  40, "Creativity",    [5]),
    ("sat_ghl",          "GHL Business",             "12:00", 60,  40, "Wealth",        [5]),
    ("sat_choir",        "Choir Rehearsal",          "14:00", 240, 35, "Spirit",        [5]),
    ("sat_family",       "Family Rotation Call",     "19:00", 30,  25, "Relationships", [5]),
    ("sat_uzaire",       "Uzaire",                   "19:30", 30,  25, "Wealth",        [5]),

    # ── SUNDAY ───────────────────────────────────────────────────────────────
    ("sun_one_thing",    "That One Thing",           "07:10", 90,  40, "Creativity",    [6]),
    ("sun_church",       "Church",                   "09:00", 180, 35, "Spirit",        [6]),
    ("sun_study",        "Study Session",            "16:00", 120, 50, "Mind",          [6]),
    ("sun_cooking",      "Cooking",                  "18:00", 60,  15, "Body",          [6]),
    ("sun_parents",      "Parents Call",             "19:00", 30,  25, "Relationships", [6]),
    ("sun_ghl",          "GHL Light Prep",           "20:00", 60,  30, "Wealth",        [6]),
]

# ── DATA MANAGEMENT ───────────────────────────────────────────────────────────
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
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
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def check_level_up(data):
    """Check and apply level ups"""
    leveled_up = False
    while True:
        needed = xp_for_level(data["level"])
        current_level_xp = data["total_xp"] - total_xp_for_level(data["level"])
        if current_level_xp >= needed:
            data["level"] += 1
            leveled_up = True
        else:
            break
    return leveled_up

def get_xp_progress(data):
    """Get XP progress within current level"""
    level_start = total_xp_for_level(data["level"])
    level_xp = data["total_xp"] - level_start
    needed = xp_for_level(data["level"])
    return level_xp, needed

def get_todays_quests():
    """Get quests for today"""
    today = datetime.now(TIMEZONE).weekday()
    todays = []
    for q in QUESTS:
        qid, name, t, dur, xp, stat, days = q
        if days == "daily" or today in days:
            todays.append(q)
    return todays

def apply_decay(data):
    """Apply stat decay for missed quests"""
    today = datetime.now(TIMEZONE).date()
    last = datetime.strptime(data["last_reset"], "%Y-%m-%d").date()
    if today > last:
        # Check how many quests were missed yesterday
        todays_quests = get_todays_quests()
        missed = [q for q in todays_quests if q[0] not in data["completed_today"]]
        for q in missed:
            stat = q[6] if q[6] != "daily" else q[5]
            stat = q[5]
            data["stats"][stat] = max(0, data["stats"][stat] - 2)
            data["pending_penalties"].append(q[0])
        # Reset daily
        data["completed_today"] = []
        data["last_reset"] = str(today)
        if len(missed) == 0:
            data["streak"] += 1
        else:
            data["streak"] = 0
    return data

# ── STATUS BAR BUILDER ────────────────────────────────────────────────────────
def build_bar(value, max_val, length=10, filled="█", empty="░"):
    filled_count = int((value / max_val) * length)
    return filled * filled_count + empty * (length - filled_count)

def build_status_message(data):
    level_xp, needed = get_xp_progress(data)
    xp_bar = build_bar(level_xp, needed)
    pct = int((level_xp / needed) * 100)

    lines = [
        "╔══════════════════════════╗",
        f"║   ⚡ THE SYSTEM — STATUS  ║",
        "╚══════════════════════════╝",
        "",
        f"👤 PLAYER:  — Active",
        f"🎮 LEVEL:   {data['level']}",
        f"🔥 STREAK:  {data['streak']} days",
        "",
        f"━━━ XP PROGRESS ━━━",
        f"{xp_bar} {pct}%",
        f"{level_xp} / {needed} XP to Level {data['level']+1}",
        "",
        "━━━ STATS ━━━",
    ]
    for stat in STATS:
        val = data["stats"][stat]
        bar = build_bar(val, 100, length=8)
        emoji = STAT_EMOJI[stat]
        lines.append(f"{emoji} {stat:<14} {bar} {val}")

    if data["pending_penalties"]:
        lines.append("")
        lines.append(f"⚠️ PENALTY QUESTS: {len(data['pending_penalties'])} pending")

    return "\n".join(lines)

# ── COMMAND HANDLERS ──────────────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != USER_ID:
        return
    data = load_data()
    data = apply_decay(data)
    save_data(data)
    await update.message.reply_text(
        "⚡ *THE SYSTEM — ONLINE*\n\n"
        "Welcome back, Player.\n\n"
        "Commands:\n"
        "/status — View your stats\n"
        "/quests — Today's quest list\n"
        "/done [quest] — Complete a quest\n"
        "/penalty — View penalty quests\n"
        "/help — All commands",
        parse_mode="Markdown"
    )

async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != USER_ID:
        return
    data = load_data()
    data = apply_decay(data)
    save_data(data)
    await update.message.reply_text(
        f"```\n{build_status_message(data)}\n```",
        parse_mode="Markdown"
    )

async def cmd_quests(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != USER_ID:
        return
    data = load_data()
    data = apply_decay(data)
    save_data(data)
    todays = get_todays_quests()
    now = datetime.now(TIMEZONE)

    lines = ["⚡ *TODAY'S QUEST LOG*\n"]
    for q in todays:
        qid, name, t, dur, xp, stat, days = q
        done = qid in data["completed_today"]
        status = "✅" if done else "🔲"
        emoji = STAT_EMOJI[stat]
        lines.append(f"{status} {emoji} *{name}*")
        lines.append(f"   🕐 {t} | ⏱ {dur}m | +{xp}XP")

    if data["pending_penalties"]:
        lines.append(f"\n⚠️ *PENALTY QUESTS: {len(data['pending_penalties'])} pending*")
        lines.append("Use /penalty to view them")

    # Inline buttons for quick completion
    keyboard = []
    incomplete = [q for q in todays if q[0] not in data["completed_today"]]
    for q in incomplete[:6]:  # Show up to 6 buttons
        qid, name, t, dur, xp, stat, days = q
        keyboard.append([InlineKeyboardButton(f"✅ {name}", callback_data=f"done_{qid}")])

    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def cmd_done(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != USER_ID:
        return
    data = load_data()
    data = apply_decay(data)

    # Find quest by partial name match
    args = " ".join(ctx.args).lower() if ctx.args else ""
    todays = get_todays_quests()
    matched = None
    for q in todays:
        if args in q[1].lower() or args in q[0].lower():
            matched = q
            break

    if not matched:
        await update.message.reply_text(
            "Quest not found. Use /quests to see today's quests and tap the buttons to complete them."
        )
        return

    qid, name, t, dur, xp, stat, days = matched
    if qid in data["completed_today"]:
        await update.message.reply_text(f"✅ *{name}* already completed!", parse_mode="Markdown")
        return

    # Complete quest
    data["completed_today"].append(qid)
    data["total_xp"] += xp
    data["stats"][stat] = min(100, data["stats"][stat] + 3)

    # Remove from penalties if it was one
    if qid in data["pending_penalties"]:
        data["pending_penalties"].remove(qid)

    leveled_up = check_level_up(data)
    save_data(data)

    level_xp, needed = get_xp_progress(data)
    xp_bar = build_bar(level_xp, needed)

    msg = (
        f"⚡ *QUEST COMPLETE*\n\n"
        f"{STAT_EMOJI[stat]} *{name}*\n"
        f"+{xp} XP | +3 {stat}\n\n"
        f"LVL {data['level']} {xp_bar} {int((level_xp/needed)*100)}%"
    )

    if leveled_up:
        msg += f"\n\n🎉 *LEVEL UP! You are now Level {data['level']}!*"

    await update.message.reply_text(msg, parse_mode="Markdown")

async def button_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if update.effective_user.id != USER_ID:
        return
    await query.answer()

    data = load_data()
    data = apply_decay(data)

    if query.data.startswith("done_"):
        qid = query.data[5:]
        matched = next((q for q in QUESTS if q[0] == qid), None)
        if not matched:
            return

        qid, name, t, dur, xp, stat, days = matched
        if qid in data["completed_today"]:
            await query.edit_message_text(f"✅ *{name}* already completed!", parse_mode="Markdown")
            return

        data["completed_today"].append(qid)
        data["total_xp"] += xp
        data["stats"][stat] = min(100, data["stats"][stat] + 3)

        if qid in data["pending_penalties"]:
            data["pending_penalties"].remove(qid)

        leveled_up = check_level_up(data)
        save_data(data)

        level_xp, needed = get_xp_progress(data)
        xp_bar = build_bar(level_xp, needed)

        msg = (
            f"⚡ *QUEST COMPLETE*\n\n"
            f"{STAT_EMOJI[stat]} *{name}*\n"
            f"+{xp} XP | +3 {stat}\n\n"
            f"LVL {data['level']} {xp_bar} {int((level_xp/needed)*100)}%"
        )
        if leveled_up:
            msg += f"\n\n🎉 *LEVEL UP! You are now Level {data['level']}!*"

        await query.edit_message_text(msg, parse_mode="Markdown")

async def cmd_penalty(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != USER_ID:
        return
    data = load_data()
    if not data["pending_penalties"]:
        await update.message.reply_text("✅ No penalty quests. You're clean, Player.")
        return

    lines = ["⚠️ *PENALTY QUESTS*\n", "Complete these to recover lost stats:\n"]
    keyboard = []
    for qid in data["pending_penalties"]:
        matched = next((q for q in QUESTS if q[0] == qid), None)
        if matched:
            _, name, t, dur, xp, stat, days = matched
            lines.append(f"🔴 {STAT_EMOJI[stat]} *{name}* (+{xp} XP)")
            keyboard.append([InlineKeyboardButton(f"✅ Complete: {name}", callback_data=f"done_{qid}")])

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != USER_ID:
        return
    await update.message.reply_text(
        "⚡ *THE SYSTEM — COMMANDS*\n\n"
        "/start — Boot up the System\n"
        "/status — Full stats dashboard\n"
        "/quests — Today's quest log\n"
        "/done [name] — Complete a quest by name\n"
        "/penalty — View & complete penalty quests\n"
        "/help — This message\n\n"
        "💡 *Tip:* Use the buttons in /quests to complete quests with one tap.",
        parse_mode="Markdown"
    )

# ── SCHEDULED NOTIFICATIONS ───────────────────────────────────────────────────
async def send_quest_notification(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    quest = job.data
    qid, name, t, dur, xp, stat, days = quest

    data = load_data()
    if qid in data["completed_today"]:
        return  # Already done, no reminder

    keyboard = [[InlineKeyboardButton(f"✅ Mark Complete", callback_data=f"done_{qid}")]]
    await context.bot.send_message(
        chat_id=USER_ID,
        text=(
            f"⚡ *QUEST AVAILABLE*\n\n"
            f"{STAT_EMOJI[stat]} *{name}*\n"
            f"⏱ Duration: {dur} mins\n"
            f"💎 Reward: +{xp} XP | +3 {stat}\n\n"
            f"Type /done or tap below when complete."
        ),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

def schedule_quests(app):
    """Schedule all quest notifications"""
    now = datetime.now(TIMEZONE)
    today = now.weekday()

    for quest in QUESTS:
        qid, name, t, dur, xp, stat, days = quest

        # Parse time
        hour, minute = map(int, t.split(":"))
        quest_time = TIMEZONE.localize(datetime.combine(now.date(), time(hour, minute)))

        if days == "daily":
            # Schedule daily
            app.job_queue.run_daily(
                send_quest_notification,
                time=time(hour, minute, tzinfo=TIMEZONE),
                data=quest,
                name=f"quest_{qid}"
            )
        else:
            # Schedule for specific days
            for day in days:
                app.job_queue.run_daily(
                    send_quest_notification,
                    time=time(hour, minute, tzinfo=TIMEZONE),
                    days=(day,),
                    data=quest,
                    name=f"quest_{qid}_{day}"
                )

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("status",  cmd_status))
    app.add_handler(CommandHandler("quests",  cmd_quests))
    app.add_handler(CommandHandler("done",    cmd_done))
    app.add_handler(CommandHandler("penalty", cmd_penalty))
    app.add_handler(CommandHandler("help",    cmd_help))
    app.add_handler(CallbackQueryHandler(button_callback))

    schedule_quests(app)

    logger.info("⚡ THE SYSTEM IS ONLINE")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
