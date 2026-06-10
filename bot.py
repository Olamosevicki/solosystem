import os
import json
import logging
import threading
import requests as req
from datetime import datetime, time
import pytz
from flask import Flask, jsonify
from flask_cors import CORS
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN    = os.environ.get("BOT_TOKEN", "")
USER_ID      = int(os.environ.get("USER_ID", "0"))
MINI_APP_URL = os.environ.get("MINI_APP_URL", "")
TIMEZONE     = pytz.timezone("Africa/Lagos")
JSONBIN_ID   = os.environ.get("JSONBIN_ID", "")
JSONBIN_KEY  = os.environ.get("JSONBIN_KEY", "")
JSONBIN_URL  = f"https://api.jsonbin.io/v3/b/{JSONBIN_ID}"
PORT         = int(os.environ.get("PORT", 8080))

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

# ── PENALTY TASKS (fixed per quest) ───────────────────────────────────────────
PENALTY_TASKS = {
    "morning_prayer":   "45 min extended prayer session tonight before sleep",
    "bible_study":      "Read 3 chapters + write key verse reflection",
    "night_prayer":     "30 min prayer + full gratitude journal before sleep",
    "workout":          "100 pushups + 50 squats before midnight",
    "mon_ghl":          "Extra 1 hr GHL session on top of today's",
    "tue_ghl1":         "Extra 1 hr GHL session on top of today's",
    "tue_ghl2":         "Extra 1 hr GHL session on top of today's",
    "wed_ghl":          "Extra 1 hr GHL session on top of today's",
    "thu_ghl1":         "Extra 1 hr GHL session on top of today's",
    "thu_ghl2":         "Extra 1 hr GHL session on top of today's",
    "fri_ghl":          "Extra 1 hr GHL session on top of today's",
    "sat_ghl":          "Extra 1 hr GHL session on top of today's",
    "sun_ghl":          "Extra 1 hr GHL session on top of today's",
    "mon_study":        "Extra 2 hrs study on top of today's session",
    "tue_study":        "Extra 2 hrs study on top of today's session",
    "wed_study_am":     "Extra 2 hrs study on top of today's session",
    "wed_study_pm":     "Extra 2 hrs study on top of today's session",
    "thu_study":        "Extra 2 hrs study on top of today's session",
    "fri_study":        "Extra 2 hrs study on top of today's session",
    "sat_study":        "Extra 2 hrs study on top of today's session",
    "sun_study":        "Extra 2 hrs study on top of today's session",
    "mon_uzaire":       "Extra 45 min Uzaire session today",
    "tue_uzaire":       "Extra 45 min Uzaire session today",
    "wed_uzaire":       "Extra 45 min Uzaire session today",
    "sat_uzaire":       "Extra 45 min Uzaire session today",
    "mon_laundry":      "Complete laundry + iron clothes same day",
    "wed_laundry":      "Complete laundry + iron clothes same day",
    "tue_cooking":      "Cook + meal prep for next day",
    "sun_cooking":      "Cook + meal prep for next day",
    "mon_family":       "Call family immediately — minimum 20 mins",
    "thu_siblings":     "Call siblings immediately — minimum 20 mins",
    "fri_siblings":     "Call siblings immediately — minimum 20 mins",
    "sat_family":       "Call family rotation — minimum 20 mins",
    "sun_parents":      "Call parents immediately — minimum 30 mins",
    "thu_discipleship": "1 hr personal worship + reflection at home",
    "fri_church":       "1 hr personal worship + reflection at home",
    "sat_choir":        "1 hr personal vocal practice",
    "sun_church":       "1 hr personal worship + reflection at home",
    "tue_one_thing":    "2 hrs dedicated creative session today",
    "fri_one_thing":    "2 hrs dedicated creative session today",
    "sat_one_thing":    "2 hrs dedicated creative session today",
    "sun_one_thing":    "2 hrs dedicated creative session today",
}

# ── QUESTS ────────────────────────────────────────────────────────────────────
QUESTS = [
    # Daily
    ("morning_prayer",   "Morning Prayer",            "05:10", 20,  40, "Spirit",        "daily"),
    ("bible_study",      "Bible Study",               "05:30", 40,  40, "Spirit",        "daily"),
    ("workout",          "Workout",                   "06:10", 45,  35, "Body",          "daily"),
    ("night_prayer",     "Night Prayer",              "21:00", 15,  30, "Spirit",        "daily"),
    # Monday
    ("mon_ghl",          "GHL Business",              "13:30", 120, 50, "Wealth",        [0]),
    ("mon_study",        "Study Session",             "17:45", 75,  45, "Mind",          [0]),
    ("mon_uzaire",       "Uzaire",                    "18:30", 30,  25, "Wealth",        [0]),
    ("mon_laundry",      "Laundry",                   "19:00", 45,  15, "Body",          [0]),
    ("mon_family",       "Family Check-in",           "21:00", 15,  20, "Relationships", [0]),
    # Tuesday
    ("tue_one_thing",    "That One Thing",            "07:30", 90,  40, "Creativity",    [1]),
    ("tue_ghl1",         "GHL Business pt.1",         "12:30", 30,  25, "Wealth",        [1]),
    ("tue_ghl2",         "GHL Business pt.2",         "16:00", 90,  35, "Wealth",        [1]),
    ("tue_cooking",      "Cooking",                   "19:00", 60,  15, "Body",          [1]),
    ("tue_study",        "Study Session",             "20:00", 60,  45, "Mind",          [1]),
    ("tue_uzaire",       "Uzaire",                    "21:00", 30,  25, "Wealth",        [1]),
    # Wednesday
    ("wed_study_am",     "Morning Study",             "07:30", 60,  40, "Mind",          [2]),
    ("wed_ghl",          "GHL Business",              "14:00", 60,  35, "Wealth",        [2]),
    ("wed_uzaire",       "Uzaire",                    "18:30", 30,  25, "Wealth",        [2]),
    ("wed_laundry",      "Laundry",                   "19:00", 45,  15, "Body",          [2]),
    ("wed_study_pm",     "Evening Study",             "19:45", 75,  40, "Mind",          [2]),
    # Thursday
    ("thu_ghl1",         "GHL Business pt.1",         "12:30", 30,  25, "Wealth",        [3]),
    ("thu_ghl2",         "GHL Business pt.2",         "16:00", 90,  35, "Wealth",        [3]),
    ("thu_siblings",     "Siblings Check-in",         "17:30", 20,  20, "Relationships", [3]),
    ("thu_discipleship", "Discipleship Meeting",      "18:00", 90,  35, "Spirit",        [3]),
    ("thu_study",        "Study Session",             "20:00", 30,  25, "Mind",          [3]),
    # Friday
    ("fri_study",        "Study Session [SACRED]",    "07:30", 180, 60, "Mind",          [4]),
    ("fri_one_thing",    "That One Thing",            "10:30", 90,  40, "Creativity",    [4]),
    ("fri_ghl",          "GHL Business [POWER]",      "12:30", 120, 60, "Wealth",        [4]),
    ("fri_uzaire",       "Uzaire",                    "14:30", 30,  25, "Wealth",        [4]),
    ("fri_siblings",     "Siblings Check-in",         "16:00", 30,  20, "Relationships", [4]),
    ("fri_church",       "Church",                    "18:00", 120, 30, "Spirit",        [4]),
    # Saturday
    ("sat_study",        "Study Session",             "07:30", 180, 60, "Mind",          [5]),
    ("sat_one_thing",    "That One Thing",            "10:30", 90,  40, "Creativity",    [5]),
    ("sat_ghl",          "GHL Business",              "12:00", 60,  40, "Wealth",        [5]),
    ("sat_choir",        "Choir Rehearsal",           "14:00", 240, 35, "Spirit",        [5]),
    ("sat_family",       "Family Rotation Call",      "19:00", 30,  25, "Relationships", [5]),
    ("sat_uzaire",       "Uzaire",                    "19:30", 30,  25, "Wealth",        [5]),
    # Sunday
    ("sun_one_thing",    "That One Thing",            "07:10", 90,  40, "Creativity",    [6]),
    ("sun_church",       "Church",                    "09:00", 180, 35, "Spirit",        [6]),
    ("sun_study",        "Study Session",             "16:00", 120, 50, "Mind",          [6]),
    ("sun_cooking",      "Cooking",                   "18:00", 60,  15, "Body",          [6]),
    ("sun_parents",      "Parents Call",              "19:00", 30,  25, "Relationships", [6]),
    ("sun_ghl",          "GHL Light Prep",            "20:00", 60,  30, "Wealth",        [6]),
]

# ── FRESH START DATA ──────────────────────────────────────────────────────────
FRESH_DATA = {
    "level": 2,
    "total_xp": total_xp_for_level(2),
    "stats": {s: 10 for s in STATS},
    "completed_today": [],
    "pending_penalties": [],  # list of {id, quest_id, stat, task, assigned_date}
    "locked": False,
    "streak": 0,
    "last_reset": str(datetime.now(pytz.timezone("Africa/Lagos")).date()),
    "history": []
}

# ── JSONBIN DATA ──────────────────────────────────────────────────────────────
def load_data():
    try:
        res = req.get(JSONBIN_URL + "/latest",
            headers={"X-Master-Key": JSONBIN_KEY, "X-Bin-Meta": "false"},
            timeout=10)
        if res.ok:
            return res.json()
    except Exception as e:
        logger.error(f"JSONBin load failed: {e}")
    return dict(FRESH_DATA)

def save_data(data):
    try:
        req.put(JSONBIN_URL, json=data,
            headers={"X-Master-Key": JSONBIN_KEY, "Content-Type": "application/json"},
            timeout=10)
    except Exception as e:
        logger.error(f"JSONBin save failed: {e}")

# ── HELPERS ───────────────────────────────────────────────────────────────────
def xp_for_level(level):
    return int(100 * (1.4 ** (level - 1)))

def total_xp_for_level(level):
    return sum(int(100 * (1.4 ** (l-1))) for l in range(1, level))

def check_level_up(data):
    leveled_up = False
    while True:
        needed = xp_for_level(data["level"])
        current_xp = data["total_xp"] - total_xp_for_level(data["level"])
        if current_xp >= needed:
            data["level"] += 1
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

def get_quest_by_id(qid):
    return next((q for q in QUESTS if q[0] == qid), None)

def is_locked(data):
    """Check if system is locked due to uncleared penalties past midnight"""
    return data.get("locked", False)

def apply_daily_reset(data):
    """Run at midnight — check missed quests, assign penalties, reset day"""
    today = datetime.now(TIMEZONE).date()
    last = datetime.strptime(data["last_reset"], "%Y-%m-%d").date()
    if today <= last:
        return data, False

    yesterday_weekday = last.weekday()
    yesterday_quests = [q for q in QUESTS if q[6] == "daily" or yesterday_weekday in q[6]]
    missed = [q for q in yesterday_quests if q[0] not in data["completed_today"]]

    newly_assigned = []
    for q in missed:
        qid, name, t, dur, xp, stat, days = q
        # Apply -2 decay
        data["stats"][stat] = max(0, data["stats"][stat] - 2)
        # Check if penalty already exists for this quest
        already = any(p["quest_id"] == qid for p in data.get("pending_penalties", []))
        if not already:
            penalty = {
                "id": f"pen_{qid}_{str(today)}",
                "quest_id": qid,
                "quest_name": name,
                "stat": stat,
                "task": PENALTY_TASKS.get(qid, f"Complete missed {name} task"),
                "assigned_date": str(today),
            }
            data.setdefault("pending_penalties", []).append(penalty)
            newly_assigned.append(penalty)

    # Reset daily
    data["completed_today"] = []
    data["last_reset"] = str(today)
    data["streak"] = data["streak"] + 1 if not missed else 0

    # If there are pending penalties — lock the system
    if data.get("pending_penalties"):
        data["locked"] = True

    return data, newly_assigned

def build_bar(value, max_val=100, length=10):
    filled = int((value / max_val) * length)
    return "█" * filled + "░" * (length - filled)

def build_status(data):
    level_xp, needed = get_xp_progress(data)
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
        f"{build_bar(level_xp, needed)} {pct}%",
        f"{level_xp} / {needed} XP → Level {data['level']+1}",
        "",
        "━━━ STATS ━━━",
    ]
    for stat in STATS:
        val = data["stats"][stat]
        lines.append(f"{STAT_EMOJI[stat]} {stat:<14} {build_bar(val)} {val}")
    if data.get("pending_penalties"):
        lines.append(f"\n⚠️ PENALTIES: {len(data['pending_penalties'])} pending")
    if data.get("locked"):
        lines.append("🔒 SYSTEM LOCKED — Clear penalties first")
    return "\n".join(lines)

# ── FLASK API ─────────────────────────────────────────────────────────────────
flask_app = Flask(__name__)
CORS(flask_app)

@flask_app.route("/stats")
def get_stats():
    data = load_data()
    level_xp, needed = get_xp_progress(data)
    pct = int((level_xp / needed) * 100)
    todays = get_todays_quests()
    quests_out = [{
        "id": q[0], "name": q[1], "time": q[2],
        "dur": q[3], "xp": q[4], "stat": q[5],
        "done": q[0] in data["completed_today"]
    } for q in todays]
    return jsonify({
        "level": data["level"],
        "total_xp": data["total_xp"],
        "level_xp": level_xp,
        "needed": needed,
        "pct": pct,
        "stats": data["stats"],
        "streak": data["streak"],
        "penalties": len(data.get("pending_penalties", [])),
        "locked": data.get("locked", False),
        "quests": quests_out,
    })

@flask_app.route("/health")
def health():
    return jsonify({"status": "online"})

def run_flask():
    flask_app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)

# ── MINI APP BUTTON ───────────────────────────────────────────────────────────
def mini_btn(extra_buttons=None):
    keyboard = extra_buttons or []
    if MINI_APP_URL:
        keyboard.append([InlineKeyboardButton("⚡ Open The System", web_app=WebAppInfo(url=MINI_APP_URL))])
    return InlineKeyboardMarkup(keyboard) if keyboard else None

# ── HANDLERS ──────────────────────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != USER_ID: return
    data = load_data()
    data, newly_assigned = apply_daily_reset(data)
    save_data(data)
    msg = (
        "⚡ *THE SYSTEM — ONLINE*\n\n"
        "Welcome back, Victor.\n\n"
        "/status — Stats\n"
        "/quests — Today's quests\n"
        "/done [quest] — Complete quest\n"
        "/penalty — Penalty tasks\n"
        "/export — Sync code\n"
        "/reset — Fresh start\n"
        "/help — All commands"
    )
    if data.get("locked"):
        msg += "\n\n🔒 *SYSTEM LOCKED — Clear penalties first*"
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=mini_btn())

async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != USER_ID: return
    data = load_data()
    data, _ = apply_daily_reset(data)
    save_data(data)
    await update.message.reply_text(
        f"```\n{build_status(data)}\n```",
        parse_mode="Markdown", reply_markup=mini_btn()
    )

async def cmd_quests(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != USER_ID: return
    data = load_data()
    data, _ = apply_daily_reset(data)
    save_data(data)

    if is_locked(data):
        await update.message.reply_text(
            "🔒 *SYSTEM LOCKED*\n\n"
            "You have uncompleted penalty tasks.\n"
            "Clear them with /penalty before new quests can be logged.\n\n"
            f"⚠️ Stats are decaying -1/hr on affected stats.",
            parse_mode="Markdown",
            reply_markup=mini_btn([[InlineKeyboardButton("⚠️ View Penalties", callback_data="show_penalties")]])
        )
        return

    todays = get_todays_quests()
    lines = ["⚡ *TODAY'S QUEST LOG*\n"]
    for q in todays:
        done = q[0] in data["completed_today"]
        lines.append(f"{'✅' if done else '🔲'} {STAT_EMOJI[q[5]]} *{q[1]}*")
        lines.append(f"   🕐 {q[2]} | ⏱ {q[3]}m | +{q[4]}XP")

    keyboard = []
    for q in [q for q in todays if q[0] not in data["completed_today"]][:8]:
        keyboard.append([InlineKeyboardButton(f"✅ {q[1]}", callback_data=f"done_{q[0]}")])

    await update.message.reply_text(
        "\n".join(lines), parse_mode="Markdown",
        reply_markup=mini_btn(keyboard)
    )

async def cmd_done(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != USER_ID: return
    data = load_data()
    data, _ = apply_daily_reset(data)

    if is_locked(data):
        await update.message.reply_text(
            "🔒 *SYSTEM LOCKED*\n\nClear your penalty tasks first.\nUse /penalty to view them.",
            parse_mode="Markdown"
        )
        return

    args = " ".join(ctx.args).lower() if ctx.args else ""
    matched = next((q for q in get_todays_quests() if args in q[1].lower() or args in q[0].lower()), None)

    if not matched:
        await update.message.reply_text("Quest not found. Use /quests to see today's quests."); return
    if matched[0] in data["completed_today"]:
        await update.message.reply_text(f"✅ *{matched[1]}* already completed!", parse_mode="Markdown"); return

    qid, name, t, dur, xp, stat, days = matched
    data["completed_today"].append(qid)
    data["total_xp"] += xp
    data["stats"][stat] = min(100, data["stats"][stat] + 3)
    leveled_up = check_level_up(data)
    save_data(data)

    level_xp, needed = get_xp_progress(data)
    msg = (f"⚡ *QUEST COMPLETE*\n\n{STAT_EMOJI[stat]} *{name}*\n"
           f"+{xp} XP | +3 {stat}\n\n"
           f"LVL {data['level']} {build_bar(level_xp, needed)} {int((level_xp/needed)*100)}%")
    if leveled_up:
        msg += f"\n\n🎉 *LEVEL UP! You are now Level {data['level']}!*\nAll stats +1"
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=mini_btn())

async def button_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if update.effective_user.id != USER_ID: return
    await query.answer()
    data = load_data()
    data, _ = apply_daily_reset(data)

    if query.data == "show_penalties":
        await show_penalty_list(query, data)
        return

    if query.data.startswith("done_"):
        qid = query.data[5:]
        if is_locked(data):
            await query.edit_message_text(
                "🔒 *SYSTEM LOCKED*\n\nClear penalties first. Use /penalty",
                parse_mode="Markdown"
            )
            return

        matched = get_quest_by_id(qid)
        if not matched or qid in data["completed_today"]:
            await query.edit_message_text("✅ Already completed!", parse_mode="Markdown"); return

        qid_, name, t, dur, xp, stat, days = matched
        data["completed_today"].append(qid_)
        data["total_xp"] += xp
        data["stats"][stat] = min(100, data["stats"][stat] + 3)
        leveled_up = check_level_up(data)
        save_data(data)

        level_xp, needed = get_xp_progress(data)
        msg = (f"⚡ *QUEST COMPLETE*\n\n{STAT_EMOJI[stat]} *{name}*\n"
               f"+{xp} XP | +3 {stat}\n\n"
               f"LVL {data['level']} {build_bar(level_xp, needed)} {int((level_xp/needed)*100)}%")
        if leveled_up:
            msg += f"\n\n🎉 *LEVEL UP! Level {data['level']}!*"
        await query.edit_message_text(msg, parse_mode="Markdown",
            reply_markup=mini_btn())

    if query.data.startswith("pen_done_"):
        pen_id = query.data[9:]
        penalties = data.get("pending_penalties", [])
        pen = next((p for p in penalties if p["id"] == pen_id), None)
        if not pen:
            await query.edit_message_text("Penalty already cleared."); return

        # Complete penalty — partial recovery only (+1)
        stat = pen["stat"]
        data["stats"][stat] = min(100, data["stats"][stat] + 1)
        data["pending_penalties"] = [p for p in penalties if p["id"] != pen_id]

        # Unlock if no more penalties
        if not data["pending_penalties"]:
            data["locked"] = False

        save_data(data)
        remaining = len(data["pending_penalties"])
        msg = (f"⚠️ *PENALTY CLEARED*\n\n"
               f"{STAT_EMOJI[stat]} {stat} +1 (partial recovery)\n\n"
               f"{'✅ All penalties cleared. System unlocked.' if not remaining else f'⚠️ {remaining} penalties remaining.'}")
        await query.edit_message_text(msg, parse_mode="Markdown",
            reply_markup=mini_btn())

async def show_penalty_list(query_or_msg, data, edit=True):
    penalties = data.get("pending_penalties", [])
    if not penalties:
        msg = "✅ No penalty tasks. System is clean."
        if edit:
            await query_or_msg.edit_message_text(msg)
        else:
            await query_or_msg.reply_text(msg)
        return

    lines = [
        "⚠️ *PENALTY TASKS*\n",
        "Complete these to recover stats (+1 each):\n",
        f"{'🔒 SYSTEM LOCKED — Complete to unlock' if data.get('locked') else ''}\n"
    ]
    keyboard = []
    for p in penalties:
        lines.append(f"🔴 {STAT_EMOJI[p['stat']]} *{p['quest_name']}*")
        lines.append(f"   📋 {p['task']}")
        lines.append(f"   📅 Assigned: {p['assigned_date']}\n")
        keyboard.append([InlineKeyboardButton(f"✅ Done: {p['quest_name']}", callback_data=f"pen_done_{p['id']}")])

    rm = mini_btn(keyboard)
    if edit:
        await query_or_msg.edit_message_text("\n".join(lines), parse_mode="Markdown", reply_markup=rm)
    else:
        await query_or_msg.reply_text("\n".join(lines), parse_mode="Markdown", reply_markup=rm)

async def cmd_penalty(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != USER_ID: return
    data = load_data()
    await show_penalty_list(update.message, data, edit=False)


async def cmd_export(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != USER_ID: return
    data = load_data()
    stats_str = ",".join(str(data["stats"][s]) for s in STATS)
    code = f"LVL:{data['level']}|XP:{data['total_xp']}|STATS:{stats_str}|STREAK:{data['streak']}|PENALTIES:{len(data.get('pending_penalties',[]))}"
    await update.message.reply_text(
        f"⚡ *SYNC CODE*\n\n`{code}`",
        parse_mode="Markdown"
    )

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != USER_ID: return
    await update.message.reply_text(
        "⚡ *THE SYSTEM — COMMANDS*\n\n"
        "/start — Boot up\n"
        "/status — Stats dashboard\n"
        "/quests — Today's quests\n"
        "/done [name] — Complete a quest\n"
        "/penalty — View penalty tasks\n"
        "/export — Sync code for Mini App\n"
        "/reset — Fresh start (resets all stats)\n"
        "/help — This message",
        parse_mode="Markdown", reply_markup=mini_btn()
    )

# ── SCHEDULED NOTIFICATIONS ───────────────────────────────────────────────────
async def send_quest_notification(context: ContextTypes.DEFAULT_TYPE):
    quest = context.job.data
    qid, name, t, dur, xp, stat, days = quest
    data = load_data()
    if qid in data["completed_today"]: return
    if is_locked(data):
        await context.bot.send_message(
            chat_id=USER_ID,
            text=f"🔒 *SYSTEM LOCKED*\n\nQuest skipped: *{name}*\nClear your penalties first to unlock quests.",
            parse_mode="Markdown"
        )
        return
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

async def hourly_penalty_decay(context: ContextTypes.DEFAULT_TYPE):
    """Every hour — if locked, decay -1 on each pending penalty's stat"""
    data = load_data()
    if not data.get("locked"): return
    penalties = data.get("pending_penalties", [])
    if not penalties: return

    # Decay -1 on each unique stat that has a pending penalty
    affected_stats = list(set(p["stat"] for p in penalties))
    for stat in affected_stats:
        data["stats"][stat] = max(0, data["stats"][stat] - 1)

    save_data(data)

    stat_list = ", ".join(f"{STAT_EMOJI[s]} {s}" for s in affected_stats)
    await context.bot.send_message(
        chat_id=USER_ID,
        text=(f"⏰ *PENALTY DECAY*\n\n"
              f"Affected stats: {stat_list}\n"
              f"Each -1 this hour.\n\n"
              f"Clear penalties now: /penalty"),
        parse_mode="Markdown"
    )

def schedule_jobs(app):
    # Quest notifications
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
    # Hourly penalty decay
    app.job_queue.run_repeating(hourly_penalty_decay, interval=3600, first=60)

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info(f"⚡ Flask running on port {PORT}")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("status",  cmd_status))
    app.add_handler(CommandHandler("quests",  cmd_quests))
    app.add_handler(CommandHandler("done",    cmd_done))
    app.add_handler(CommandHandler("penalty", cmd_penalty))
    app.add_handler(CommandHandler("export",  cmd_export))
    app.add_handler(CommandHandler("help",    cmd_help))
    app.add_handler(CallbackQueryHandler(button_callback))
    schedule_jobs(app)
    logger.info("⚡ THE SYSTEM IS ONLINE")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
