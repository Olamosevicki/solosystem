import os
import json
import logging
from datetime import datetime, time
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
USER_ID    = int(os.environ.get("USER_ID", "0"))
TIMEZONE   = pytz.timezone("Africa/Lagos")
DATA_FILE  = "player_data.json"

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
    ("morning_prayer",   "Morning Prayer",           "05:10", 20,  40, "Spirit",        "daily"),
    ("bible_study",      "Bible Study",              "05:30", 40,  40, "Spirit",        "daily"),
    ("workout",          "Workout",                  "06:10", 45,  35, "Body",          "daily"),
    ("night_prayer",     "Night Prayer",             "21:00", 15,  30, "Spirit",        "daily"),
    ("mon_ghl",          "GHL Business",             "13:30", 120, 50, "Wealth",        [0]),
    ("mon_study",        "Study Session",            "17:45", 75,  45, "Mind",          [0]),
    ("mon_uzaire",       "Uzaire",                   "18:30", 30,  25, "Wealth",        [0]),
    ("mon_laundry",      "Laundry",                  "19:00", 45,  15, "Body",          [0]),
    ("mon_family",       "Family Check-in",          "21:00", 15,  20, "Relationships", [0]),
    ("tue_one_thing",    "That One Thing",           "07:30", 90,  40, "Creativity",    [1]),
    ("tue_ghl1",         "GHL Business pt.1",        "12:30", 30,  25, "Wealth",        [1]),
    ("tue_ghl2",         "GHL Business pt.2",        "16:00", 90,  35, "Wealth",        [1]),
    ("tue_cooking",      "Cooking",                  "19:00", 60,  15, "Body",          [1]),
    ("tue_study",        "Study Session",            "20:00", 60,  45, "Mind",          [1]),
    ("tue_uzaire",       "Uzaire",                   "21:00", 30,  25, "Wealth",        [1]),
    ("wed_study_am",     "Morning Study",            "07:30", 60,  40, "Mind",          [2]),
    ("wed_ghl",          "GHL Business",             "14:00", 60,  35, "Wealth",        [2]),
    ("wed_uzaire",       "Uzaire",                   "18:30", 30,  25, "Wealth",        [2]),
    ("wed_laundry",      "Laundry",                  "19:00", 45,  15, "Body",          [2]),
    ("wed_study_pm",     "Evening Study",            "19:45", 75,  40, "Mind",          [2]),
    ("thu_ghl1",         "GHL Business pt.1",        "12:30", 30,  25, "Wealth",        [3]),
    ("thu_ghl2",         "GHL Business pt.2",        "16:00", 90,  35, "Wealth",        [3]),
    ("thu_siblings",     "Siblings Check-in",        "17:30", 20,  20, "Relationships", [3]),
    ("thu_discipleship", "Discipleship Meeting",     "18:00", 90,  35, "Spirit",        [3]),
    ("thu_study",        "Study Session",            "20:00", 30,  25, "Mind",          [3]),
    ("fri_study",        "Study Session [SACRED]",   "07:30", 180, 60, "Mind",          [4]),
    ("fri_one_thing",    "That One Thing",           "10:30", 90,  40, "Creativity",    [4]),
    ("fri_ghl",          "GHL Business [POWER]",     "12:30", 120, 60, "Wealth",        [4]),
    ("fri_uzaire",       "Uzaire",                   "14:30", 30,  25, "Wealth",        [4]),
    ("fri_siblings",     "Siblings Check-in",        "16:00", 30,  20, "Relationships", [4]),
    ("fri_church",       "Church",                   "18:00", 120, 30, "Spirit",        [4]),
    ("sat_study",        "Study Session",            "07:30", 180, 60, "Mind",          [5]),
    ("sat_one_thing",    "That One Thing",           "10:30", 90,  40, "Creativity",    [5]),
    ("sat_ghl",          "GHL Business",             "12:00", 60,  40, "Wealth",        [5]),
    ("sat_choir",        "Choir Rehearsal",          "14:00", 240, 35, "Spirit",        [5]),
    ("sat_family",       "Family Rotation Call",     "19:00", 30,  25, "Relationships", [5]),
    ("sat_uzaire",       "Uzaire",                   "19:30", 30,  25, "Wealth",        [5]),
    ("sun_one_thing",    "That One Thing",           "07:10", 90,  40, "Creativity",    [6]),
    ("sun_church",       "Church",                   "09:00", 180, 35, "Spirit",        [6]),
    ("sun_study",        "Study Session",            "16:00", 120, 50, "Mind",          [6]),
    ("sun_cooking",      "Cooking",                  "18:00", 60,  15, "Body",          [6]),
    ("sun_parents",      "Parents Call",             "19:00", 30,  25, "Relationships", [6]),
    ("sun_ghl",          "GHL Light Prep",           "20:00", 60,  30, "Wealth",        [6]),
]

# ── DATA ──────────────────────────────────────────────────────────────────────
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
    level_start = total_xp_for_level(data["level"])
    level_xp = data["total_xp"] - level_start
    needed = xp_for_level(data["level"])
    return level_xp, needed

def get_todays_quests():
    today = datetime.now(TIMEZONE).weekday()
    todays = []
    for q in QUESTS:
        qid, name, t, dur, xp, stat, days = q
        if days == "daily" or today in days:
            todays.append(q)
    return todays

def apply_decay(data):
    today = datetime.now(TIMEZONE).date()
    last = datetime.strptime(data["last_reset"], "%Y-%m-%d").date()
    if today > last:
        todays_quests = get_todays_quests()
        missed = [q for q in todays_quests if q[0] not in data["completed_today"]]
        for q in missed:
            stat = q[5]
            data["stats"][stat] = max(0, data["stats"][stat] - 2)
            if q[0] not in data["pending_penalties"]:
                data["pending_penalties"].append(q[0])
        data["completed_today"] = []
        data["last_reset"] = str(today)
        if len(missed) == 0:
            data["streak"] += 1
        else:
            data["streak"] = 0
    return data

def build_bar(value, max_val, length=10, filled="█", empty="░"):
    filled_count = int((value / max_val) * length)
    return filled * filled_count + empty * (length - filled_count)

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
        bar = build_bar(val, 100, length=8)
        emoji = STAT_EMOJI[stat]
        lines.append(f"{emoji} {stat:<14} {bar} {val}")
    if data["pending_penalties"]:
        lines.append("")
        lines.append(f"⚠️ PENALTY QUESTS: {len(data['pending_penalties'])} pending")
    return "\n".join(lines)

# ── EXPORT / IMPORT ───────────────────────────────────────────────────────────
def build_export_code(data):
    """Build a compact sync code for the artifact"""
    stats_str = ",".join(str(data["stats"][s]) for s in STATS)
    return (
        f"LVL:{data['level']}|"
        f"XP:{data['total_xp']}|"
        f"STATS:{stats_str}|"
        f"STREAK:{data['streak']}|"
        f"PENALTIES:{len(data['pending_penalties'])}"
    )

def parse_import_code(code):
    """Parse sync code back into data fields"""
    try:
        parts = {}
        for segment in code.strip().split("|"):
            key, val = segment.split(":", 1)
            parts[key] = val
        level = int(parts["LVL"])
        total_xp = int(parts["XP"])
        streak = int(parts["STREAK"])
        stat_vals = list(map(int, parts["STATS"].split(",")))
        stats = {s: stat_vals[i] for i, s in enumerate(STATS)}
        return level, total_xp, stats, streak
    except Exception:
        return None

# ── HANDLERS ──────────────────────────────────────────────────────────────────
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
        "/export — Sync code for status screen\n"
        "/import [code] — Import from status screen\n"
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
    lines = ["⚡ *TODAY'S QUEST LOG*\n"]
    for q in todays:
        qid, name, t, dur, xp, stat, days = q
        done = qid in data["completed_today"]
        status = "✅" if done else "🔲"
        emoji = STAT_EMOJI[stat]
        lines.append(f"{status} {emoji} *{name}*")
        lines.append(f"   🕐 {t} | ⏱ {dur}m | +{xp}XP")
    if data["pending_penalties"]:
        lines.append(f"\n⚠️ *PENALTIES: {len(data['pending_penalties'])} pending*")
    keyboard = []
    incomplete = [q for q in todays if q[0] not in data["completed_today"]]
    for q in incomplete[:8]:
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
    args = " ".join(ctx.args).lower() if ctx.args else ""
    todays = get_todays_quests()
    matched = None
    for q in todays:
        if args in q[1].lower() or args in q[0].lower():
            matched = q
            break
    if not matched:
        await update.message.reply_text("Quest not found. Use /quests to see today's quests.")
        return
    qid, name, t, dur, xp, stat, days = matched
    if qid in data["completed_today"]:
        await update.message.reply_text(f"✅ *{name}* already completed!", parse_mode="Markdown")
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

async def cmd_export(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != USER_ID:
        return
    data = load_data()
    code = build_export_code(data)
    await update.message.reply_text(
        f"⚡ *SYNC CODE — Copy this into your Status Screen*\n\n"
        f"`{code}`\n\n"
        f"Paste it into the artifact to sync your progress.",
        parse_mode="Markdown"
    )

async def cmd_import(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != USER_ID:
        return
    if not ctx.args:
        await update.message.reply_text("Usage: /import [sync code]")
        return
    code = " ".join(ctx.args)
    result = parse_import_code(code)
    if not result:
        await update.message.reply_text("❌ Invalid sync code. Please copy it exactly from the artifact.")
        return
    level, total_xp, stats, streak = result
    data = load_data()
    data["level"] = level
    data["total_xp"] = total_xp
    data["stats"] = stats
    data["streak"] = streak
    save_data(data)
    await update.message.reply_text(
        f"✅ *Sync complete!*\n\n"
        f"Level {level} | Streak {streak} days\n"
        f"All stats updated.",
        parse_mode="Markdown"
    )

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != USER_ID:
        return
    await update.message.reply_text(
        "⚡ *THE SYSTEM — COMMANDS*\n\n"
        "/start — Boot up the System\n"
        "/status — Full stats dashboard\n"
        "/quests — Today's quest log\n"
        "/done [name] — Complete a quest\n"
        "/penalty — View & complete penalty quests\n"
        "/export — Get sync code for status screen\n"
        "/import [code] — Import sync code\n"
        "/help — This message\n\n"
        "💡 Tap buttons in /quests to complete with one tap.",
        parse_mode="Markdown"
    )

# ── SCHEDULED NOTIFICATIONS ───────────────────────────────────────────────────
async def send_quest_notification(context: ContextTypes.DEFAULT_TYPE):
    quest = context.job.data
    qid, name, t, dur, xp, stat, days = quest
    data = load_data()
    if qid in data["completed_today"]:
        return
    keyboard = [[InlineKeyboardButton("✅ Mark Complete", callback_data=f"done_{qid}")]]
    await context.bot.send_message(
        chat_id=USER_ID,
        text=(
            f"⚡ *QUEST AVAILABLE*\n\n"
            f"{STAT_EMOJI[stat]} *{name}*\n"
            f"⏱ {dur} mins | 💎 +{xp} XP | +3 {stat}\n\n"
            f"Tap below when complete."
        ),
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
                data=quest,
                name=f"quest_{qid}"
            )
        else:
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
    app.add_handler(CommandHandler("export",  cmd_export))
    app.add_handler(CommandHandler("import",  cmd_import))
    app.add_handler(CommandHandler("help",    cmd_help))
    app.add_handler(CallbackQueryHandler(button_callback))
    schedule_quests(app)
    logger.info("⚡ THE SYSTEM IS ONLINE")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

