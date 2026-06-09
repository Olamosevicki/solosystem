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

def xp_for_level(level):
    return int(100 * (1.4 ** (level - 1)))

def total_xp_for_level(level):
    return sum(int(100 * (1.4 ** (l-1))) for l in range(1, level))

STATS = ["Spirit", "Wealth", "Mind", "Body", "Relationships", "Creativity"]
STAT_EMOJI = {
    "Spirit":"⚔️","Wealth":"💰","Mind":"🧠",
    "Body":"💪","Relationships":"🤝","Creativity":"✨",
}

BONUS_QUESTS = {
    "Spirit":[
        ("bonus_spirit_1","Read Psalms 23 + write a reflection",30,"Spirit"),
        ("bonus_spirit_2","15 mins worship music + silent prayer",25,"Spirit"),
    ],
    "Wealth":[
        ("bonus_wealth_1","Watch 1 GHL tutorial + take notes",30,"Wealth"),
        ("bonus_wealth_2","Research 1 new potential client",25,"Wealth"),
    ],
    "Mind":[
        ("bonus_mind_1","Read 20 pages of any book",30,"Mind"),
        ("bonus_mind_2","Review + summarize one class topic",25,"Mind"),
    ],
    "Body":[
        ("bonus_body_1","20 mins brisk walk or light exercise",25,"Body"),
        ("bonus_body_2","Drink 2L water + stretch 10 mins",20,"Body"),
    ],
    "Relationships":[
        ("bonus_rel_1","Send encouraging message to 3 family members",25,"Relationships"),
        ("bonus_rel_2","Check in on a friend you haven't spoken to in a while",20,"Relationships"),
    ],
    "Creativity":[
        ("bonus_cre_1","Work on AMV for 30 mins",30,"Creativity"),
        ("bonus_cre_2","Write or sketch something just for fun",20,"Creativity"),
    ],
}

# days: "daily" or list of ints (0=Mon,1=Tue,2=Wed,3=Thu,4=Fri,5=Sat,6=Sun)
QUESTS = [
    # DAILY
    ("morning_prayer","Morning Prayer","07:00",20,40,"Spirit","daily"),
    ("bible_study","Bible Study","07:20",40,40,"Spirit","daily"),
    ("workout","Workout","08:00",45,35,"Body","daily"),
    ("night_prayer","Night Prayer","21:45",15,30,"Spirit","daily"),
    # MONDAY — CVE302 Practical 13:00-17:00
    ("mon_study","Study Session","08:50",60,45,"Mind",[0]),
    ("mon_ghl","GHL Business","09:50",120,50,"Wealth",[0]),
    ("mon_family","Family Check-in","12:00",15,20,"Relationships",[0]),
    ("mon_uzaire","Uzaire","17:30",30,25,"Wealth",[0]),
    ("mon_laundry","Laundry","18:00",45,15,"Body",[0]),
    ("mon_free","Free Time — Movie/Chill","19:00",60,0,"Creativity",[0]),
    # TUESDAY
    ("tue_one_thing","That One Thing","08:50",90,40,"Creativity",[1]),
    ("tue_ghl1","GHL Business pt.1","10:30",30,25,"Wealth",[1]),
    ("tue_ghl2","GHL Business pt.2","16:10",90,35,"Wealth",[1]),
    ("tue_study","Study Session","17:45",60,45,"Mind",[1]),
    ("tue_cooking","Cooking","19:00",60,15,"Body",[1]),
    ("tue_uzaire","Uzaire","20:00",30,25,"Wealth",[1]),
    ("tue_free","Free Time — Movie/Chill","20:30",60,0,"Creativity",[1]),
    # WEDNESDAY
    ("wed_study_am","Morning Study","08:50",60,40,"Mind",[2]),
    ("wed_ghl","GHL Business","14:10",60,35,"Wealth",[2]),
    ("wed_uzaire","Uzaire","18:30",30,25,"Wealth",[2]),
    ("wed_laundry","Laundry","19:00",45,15,"Body",[2]),
    ("wed_study_pm","Evening Study","19:45",75,40,"Mind",[2]),
    ("wed_free","Free Time — Movie/Chill","21:00",30,0,"Creativity",[2]),
    # THURSDAY
    ("thu_study","Morning Study","08:50",60,40,"Mind",[3]),
    ("thu_ghl1","GHL Business pt.1","12:10",30,25,"Wealth",[3]),
    ("thu_ghl2","GHL Business pt.2","16:10",60,35,"Wealth",[3]),
    ("thu_siblings","Siblings Check-in","17:30",20,20,"Relationships",[3]),
    ("thu_discipleship","Discipleship Meeting","18:00",90,35,"Spirit",[3]),
    ("thu_free","Free Time — Movie/Chill","19:30",60,0,"Creativity",[3]),
    # FRIDAY
    ("fri_study","Study Session [SACRED]","08:50",180,60,"Mind",[4]),
    ("fri_one_thing","That One Thing","11:50",90,40,"Creativity",[4]),
    ("fri_ghl","GHL Business [POWER]","13:30",120,60,"Wealth",[4]),
    ("fri_uzaire","Uzaire","15:30",30,25,"Wealth",[4]),
    ("fri_siblings","Siblings Check-in","16:10",30,20,"Relationships",[4]),
    ("fri_free","Free Time — Movie/Chill","17:00",60,0,"Creativity",[4]),
    ("fri_church","Church","18:00",120,30,"Spirit",[4]),
    # SATURDAY
    ("sat_study","Study Session","08:50",180,60,"Mind",[5]),
    ("sat_one_thing","That One Thing","11:50",90,40,"Creativity",[5]),
    ("sat_ghl","GHL Business","13:30",60,40,"Wealth",[5]),
    ("sat_choir","Choir Rehearsal","14:00",240,35,"Spirit",[5]),
    ("sat_family","Family Rotation Call","18:30",30,25,"Relationships",[5]),
    ("sat_uzaire","Uzaire","19:00",30,25,"Wealth",[5]),
    ("sat_free","Free Time — Movie/Chill","19:30",60,0,"Creativity",[5]),
    # SUNDAY
    ("sun_one_thing","That One Thing","08:50",90,40,"Creativity",[6]),
    ("sun_church","Church","09:00",180,35,"Spirit",[6]),
    ("sun_study","Study Session","14:00",120,50,"Mind",[6]),
    ("sun_free","Free Time — Movie/Chill","16:00",60,0,"Creativity",[6]),
    ("sun_cooking","Cooking","17:00",60,15,"Body",[6]),
    ("sun_parents","Parents Call","18:00",30,25,"Relationships",[6]),
    ("sun_ghl","GHL Light Prep","19:00",60,30,"Wealth",[6]),
]

def fresh_data():
    return {
        "level":2,"total_xp":total_xp_for_level(2),
        "stats":{s:10 for s in STATS},
        "completed_today":[],"skipped_today":[],
        "skips_this_week":0,"week_start":str(datetime.now(TIMEZONE).date()),
        "pending_penalties":[],"locked":False,
        "streak":0,"last_reset":str(datetime.now(TIMEZONE).date()),"history":[]
    }

def load_data():
    try:
        res = req.get(JSONBIN_URL+"/latest",
            headers={"X-Master-Key":JSONBIN_KEY,"X-Bin-Meta":"false"},timeout=10)
        if res.ok:
            d = res.json()
            d.setdefault("skipped_today",[])
            d.setdefault("skips_this_week",0)
            d.setdefault("week_start",str(datetime.now(TIMEZONE).date()))
            d.setdefault("locked",False)
            d.setdefault("pending_penalties",[])
            return d
    except Exception as e:
        logger.error(f"Load failed: {e}")
    return fresh_data()

def save_data(data):
    try:
        req.put(JSONBIN_URL,json=data,
            headers={"X-Master-Key":JSONBIN_KEY,"Content-Type":"application/json"},timeout=10)
    except Exception as e:
        logger.error(f"Save failed: {e}")

def check_level_up(data):
    leveled_up = False
    while True:
        needed = xp_for_level(data["level"])
        cur = data["total_xp"] - total_xp_for_level(data["level"])
        if cur >= needed:
            data["level"] += 1
            for s in STATS: data["stats"][s] = min(100,data["stats"][s]+1)
            leveled_up = True
        else: break
    return leveled_up

def get_xp_progress(data):
    ls = total_xp_for_level(data["level"])
    lxp = data["total_xp"] - ls
    needed = xp_for_level(data["level"])
    return lxp, needed

def get_todays_quests():
    now = datetime.now(TIMEZONE)
    today = now.weekday()
    logger.info(f"Today: {now.strftime('%A %Y-%m-%d')} (weekday {today})")
    return [q for q in QUESTS if q[6]=="daily" or (isinstance(q[6],list) and today in q[6])]

def get_quest_by_id(qid):
    return next((q for q in QUESTS if q[0]==qid),None)

def reset_weekly_skips(data):
    today = datetime.now(TIMEZONE).date()
    ws = datetime.strptime(data.get("week_start",str(today)),"%Y-%m-%d").date()
    if (today-ws).days >= 7:
        data["skips_this_week"] = 0
        data["week_start"] = str(today)
    return data

def apply_daily_reset(data):
    today = datetime.now(TIMEZONE).date()
    last = datetime.strptime(data["last_reset"],"%Y-%m-%d").date()
    if today <= last: return data,[]
    yw = last.weekday()
    yq = [q for q in QUESTS if q[6]=="daily" or (isinstance(q[6],list) and yw in q[6])]
    missed = [q for q in yq
              if q[0] not in data["completed_today"]
              and q[0] not in data.get("skipped_today",[])
              and q[4] > 0]
    new_penalties = []
    for q in missed:
        qid,name,t,dur,xp,stat,days = q
        data["stats"][stat] = max(0,data["stats"][stat]-2)
        if not any(p["quest_id"]==qid for p in data.get("pending_penalties",[])):
            p = {"id":f"pen_{qid}_{today}","quest_id":qid,"quest_name":name,
                 "stat":stat,"task":"30 press-ups + 30 squats","assigned_date":str(today)}
            data.setdefault("pending_penalties",[]).append(p)
            new_penalties.append(p)
    data["completed_today"] = []
    data["skipped_today"] = []
    data["last_reset"] = str(today)
    data["streak"] = data["streak"]+1 if not missed else 0
    if data.get("pending_penalties"): data["locked"] = True
    return data, new_penalties

def get_bonus_quests(data):
    active = []
    for stat,quests in BONUS_QUESTS.items():
        if data["stats"].get(stat,10) < 20:
            for q in quests:
                if q[0] not in data["completed_today"]:
                    active.append(q)
    return active

def build_bar(val,mx=100,n=10):
    f = int((min(val,mx)/mx)*n)
    return "█"*f + "░"*(n-f)

def build_status(data):
    lxp,needed = get_xp_progress(data)
    pct = int((lxp/needed)*100)
    skips_left = 3 - data.get("skips_this_week",0)
    lines = [
        "╔══════════════════════════╗",
        "║   ⚡ THE SYSTEM — STATUS  ║",
        "╚══════════════════════════╝","",
        f"🎮 LEVEL:   {data['level']}",
        f"🔥 STREAK:  {data['streak']} days",
        f"🎫 SKIPS:   {skips_left}/3 this week","",
        "━━━ XP PROGRESS ━━━",
        f"{build_bar(lxp,needed)} {pct}%",
        f"{lxp} / {needed} XP → Level {data['level']+1}","",
        "━━━ STATS ━━━",
    ]
    for s in STATS:
        v = data["stats"][s]
        warn = " ⚠️" if v < 20 else ""
        lines.append(f"{STAT_EMOJI[s]} {s:<14} {build_bar(v)} {v}{warn}")
    bonus = get_bonus_quests(data)
    if bonus: lines.append(f"\n💡 BONUS QUESTS: {len(bonus)} available — /bonus")
    if data.get("pending_penalties"): lines.append(f"⚠️  PENALTIES: {len(data['pending_penalties'])} pending")
    if data.get("locked"): lines.append("🔒 SYSTEM LOCKED")
    return "\n".join(lines)

flask_app = Flask(__name__)
CORS(flask_app)

@flask_app.route("/stats")
def api_stats():
    data = load_data()
    lxp,needed = get_xp_progress(data)
    todays = get_todays_quests()
    return jsonify({
        "level":data["level"],"total_xp":data["total_xp"],
        "level_xp":lxp,"needed":needed,"pct":int((lxp/needed)*100),
        "stats":data["stats"],"streak":data["streak"],
        "penalties":len(data.get("pending_penalties",[])),"locked":data.get("locked",False),
        "skips_left":3-data.get("skips_this_week",0),
        "bonus_available":len(get_bonus_quests(data)),
        "quests":[{"id":q[0],"name":q[1],"time":q[2],"dur":q[3],"xp":q[4],"stat":q[5],
                   "done":q[0] in data["completed_today"],
                   "skipped":q[0] in data.get("skipped_today",[]),
                   "is_free":q[4]==0} for q in todays],
    })

@flask_app.route("/health")
def health(): return jsonify({"status":"online"})

def run_flask():
    flask_app.run(host="0.0.0.0",port=PORT,debug=False,use_reloader=False)

def mini_btn(extra=None):
    kb = list(extra or [])
    if MINI_APP_URL: kb.append([InlineKeyboardButton("⚡ Open The System",web_app=WebAppInfo(url=MINI_APP_URL))])
    return InlineKeyboardMarkup(kb) if kb else None

async def cmd_start(update,ctx):
    if update.effective_user.id!=USER_ID: return
    data=load_data(); data=reset_weekly_skips(data); data,_=apply_daily_reset(data); save_data(data)
    msg=("⚡ *THE SYSTEM — ONLINE*\n\nWelcome back, Victor.\n\n"
         "/status — Stats\n/quests — Today's quests\n/done [quest] — Complete\n"
         "/skip [quest] — Excuse (3/week)\n/penalty — Penalty tasks\n"
         "/bonus — Optional boosts\n/export — Sync code\n/help — Commands")
    if data.get("locked"): msg+="\n\n🔒 *SYSTEM LOCKED — Clear penalties first*"
    await update.message.reply_text(msg,parse_mode="Markdown",reply_markup=mini_btn())

async def cmd_status(update,ctx):
    if update.effective_user.id!=USER_ID: return
    data=load_data(); data=reset_weekly_skips(data); data,_=apply_daily_reset(data); save_data(data)
    await update.message.reply_text(f"```\n{build_status(data)}\n```",parse_mode="Markdown",reply_markup=mini_btn())

async def cmd_quests(update,ctx):
    if update.effective_user.id!=USER_ID: return
    data=load_data(); data=reset_weekly_skips(data); data,_=apply_daily_reset(data); save_data(data)
    if data.get("locked"):
        await update.message.reply_text("🔒 *SYSTEM LOCKED*\nClear penalties first. /penalty",
            parse_mode="Markdown",reply_markup=mini_btn([[InlineKeyboardButton("⚠️ Penalties",callback_data="show_penalties")]])); return
    todays=get_todays_quests()
    skips_left=3-data.get("skips_this_week",0)
    lines=[f"⚡ *TODAY'S QUEST LOG* — 🎫 {skips_left} skips left\n"]
    for q in todays:
        qid,name,t,dur,xp,stat,days=q
        done=qid in data["completed_today"]; skipped=qid in data.get("skipped_today",[])
        if done: s="✅"
        elif skipped: s="⏭️"
        elif xp==0: s="🎬"
        else: s="🔲"
        lines.append(f"{s} {STAT_EMOJI[stat]} *{name}*")
        lines.append(f"   🕐 {t} | ⏱ {dur}m | {'FREE' if xp==0 else f'+{xp}XP'}")
    kb=[[InlineKeyboardButton(f"{'🎬' if q[4]==0 else '✅'} {q[1]}",callback_data=f"done_{q[0]}")]
        for q in todays if q[0] not in data["completed_today"] and q[0] not in data.get("skipped_today",[])][:6]
    bonus=get_bonus_quests(data)
    if bonus: lines.append(f"\n💡 *{len(bonus)} BONUS QUEST(S)* — /bonus")
    await update.message.reply_text("\n".join(lines),parse_mode="Markdown",reply_markup=mini_btn(kb))

async def cmd_done(update,ctx):
    if update.effective_user.id!=USER_ID: return
    data=load_data(); data,_=apply_daily_reset(data)
    if data.get("locked"):
        await update.message.reply_text("🔒 *SYSTEM LOCKED*\n/penalty",parse_mode="Markdown"); return
    args=" ".join(ctx.args).lower() if ctx.args else ""
    matched=next((q for q in get_todays_quests() if args in q[1].lower() or args in q[0].lower()),None)
    if not matched: await update.message.reply_text("Quest not found. Use /quests."); return
    if matched[0] in data["completed_today"]:
        await update.message.reply_text(f"✅ *{matched[1]}* already done!",parse_mode="Markdown"); return
    qid,name,t,dur,xp,stat,days=matched
    data["completed_today"].append(qid)
    if xp>0:
        data["total_xp"]+=xp; data["stats"][stat]=min(100,data["stats"][stat]+3)
    leveled_up=check_level_up(data) if xp>0 else False
    save_data(data)
    lxp,needed=get_xp_progress(data)
    if xp>0:
        msg=(f"⚡ *QUEST COMPLETE*\n\n{STAT_EMOJI[stat]} *{name}*\n+{xp} XP | +3 {stat}\n\n"
             f"LVL {data['level']} {build_bar(lxp,needed)} {int((lxp/needed)*100)}%")
        if leveled_up: msg+=f"\n\n🎉 *LEVEL UP! Level {data['level']}!*"
    else: msg=f"🎬 *{name}* logged. Enjoy — you earned it. ✅"
    await update.message.reply_text(msg,parse_mode="Markdown",reply_markup=mini_btn())

async def cmd_skip(update,ctx):
    if update.effective_user.id!=USER_ID: return
    data=load_data(); data=reset_weekly_skips(data)
    used=data.get("skips_this_week",0)
    if used>=3:
        await update.message.reply_text("❌ *No skips left this week.*\nResets next Monday.",parse_mode="Markdown"); return
    args=" ".join(ctx.args).lower() if ctx.args else ""
    if not args:
        await update.message.reply_text("Usage: /skip [quest name]\nExample: /skip workout"); return
    matched=next((q for q in get_todays_quests() if args in q[1].lower() or args in q[0].lower()),None)
    if not matched: await update.message.reply_text("Quest not found."); return
    if matched[0] in data["completed_today"] or matched[0] in data.get("skipped_today",[]):
        await update.message.reply_text("Already completed or skipped."); return
    data.setdefault("skipped_today",[]).append(matched[0])
    data["skips_this_week"]=used+1
    save_data(data)
    await update.message.reply_text(
        f"⏭️ *{matched[1]}* excused.\nNo penalty. 🎫 {3-data['skips_this_week']} skips left this week.",
        parse_mode="Markdown",reply_markup=mini_btn())

async def cmd_bonus(update,ctx):
    if update.effective_user.id!=USER_ID: return
    data=load_data(); bonus=get_bonus_quests(data)
    if not bonus:
        await update.message.reply_text("💡 No bonus quests right now.\nUnlocks when any stat drops below 20.",reply_markup=mini_btn()); return
    lines=["💡 *BONUS QUESTS*\n","Optional — no penalty for declining.\n"]
    kb=[]
    for qid,task,xp,stat in bonus:
        lines.append(f"⭐ {STAT_EMOJI[stat]} *{stat}* — {task}")
        lines.append(f"   💎 +{xp} XP | +5 {stat}\n")
        kb.append([InlineKeyboardButton(f"✅ {task[:35]}", callback_data=f"bonus_{qid}|{stat}|{xp}")])
    kb.append([InlineKeyboardButton("❌ Decline all",callback_data="bonus_decline")])
    await update.message.reply_text("\n".join(lines),parse_mode="Markdown",reply_markup=mini_btn(kb))

async def cmd_penalty(update,ctx):
    if update.effective_user.id!=USER_ID: return
    data=load_data(); penalties=data.get("pending_penalties",[])
    if not penalties:
        await update.message.reply_text("✅ No penalties. Clean.\n\nOnly the disciplined are free. — Victor",reply_markup=mini_btn()); return
    lines=["⚠️ *PENALTY TASKS*\n",
           f"{'🔒 System locked until cleared.' if data.get('locked') else ''}\n",
           "Penalty: *30 press-ups + 30 squats* per missed quest.\n",
           "Completing gives +1 stat (partial recovery).\n"]
    kb=[]
    for p in penalties:
        lines.append(f"🔴 {STAT_EMOJI[p['stat']]} *{p['quest_name']}*  📅 {p['assigned_date']}")
        kb.append([InlineKeyboardButton(f"✅ Done: {p['quest_name']}",callback_data=f"pen_done_{p['id']}")])
    await update.message.reply_text("\n".join(lines),parse_mode="Markdown",reply_markup=mini_btn(kb))

async def cmd_export(update,ctx):
    if update.effective_user.id!=USER_ID: return
    data=load_data()
    ss=",".join(str(data["stats"][s]) for s in STATS)
    code=f"LVL:{data['level']}|XP:{data['total_xp']}|STATS:{ss}|STREAK:{data['streak']}|PENALTIES:{len(data.get('pending_penalties',[]))}"
    await update.message.reply_text(f"⚡ *SYNC CODE*\n\n`{code}`",parse_mode="Markdown")

async def cmd_help(update,ctx):
    if update.effective_user.id!=USER_ID: return
    await update.message.reply_text(
        "⚡ *THE SYSTEM — COMMANDS*\n\n"
        "/start — Boot up\n/status — Stats + XP\n/quests — Today's quests\n"
        "/done [name] — Complete quest\n/skip [name] — Excuse quest (3/week)\n"
        "/penalty — View + clear penalties\n/bonus — Optional stat boosts\n"
        "/export — Sync code\n/help — This message",
        parse_mode="Markdown",reply_markup=mini_btn())

async def button_callback(update,ctx):
    query=update.callback_query
    if update.effective_user.id!=USER_ID: return
    await query.answer()
    data=load_data(); data,_=apply_daily_reset(data)

    if query.data=="show_penalties":
        penalties=data.get("pending_penalties",[])
        if not penalties: await query.edit_message_text("✅ No penalties!"); return
        lines=["⚠️ *PENALTIES*\nEach: 30 press-ups + 30 squats\n"]
        kb=[]
        for p in penalties:
            lines.append(f"🔴 {STAT_EMOJI[p['stat']]} *{p['quest_name']}*")
            kb.append([InlineKeyboardButton(f"✅ {p['quest_name']}",callback_data=f"pen_done_{p['id']}")])
        await query.edit_message_text("\n".join(lines),parse_mode="Markdown",reply_markup=mini_btn(kb)); return

    if query.data.startswith("done_"):
        qid=query.data[5:]
        if data.get("locked"):
            await query.edit_message_text("🔒 Clear penalties first. /penalty"); return
        matched=get_quest_by_id(qid)
        if not matched or qid in data["completed_today"]:
            await query.edit_message_text("✅ Already done!"); return
        qid_,name,t,dur,xp,stat,days=matched
        data["completed_today"].append(qid_)
        if xp>0:
            data["total_xp"]+=xp; data["stats"][stat]=min(100,data["stats"][stat]+3)
        leveled_up=check_level_up(data) if xp>0 else False
        save_data(data)
        lxp,needed=get_xp_progress(data)
        if xp>0:
            msg=(f"⚡ *QUEST COMPLETE*\n\n{STAT_EMOJI[stat]} *{name}*\n+{xp} XP | +3 {stat}\n\n"
                 f"LVL {data['level']} {build_bar(lxp,needed)} {int((lxp/needed)*100)}%")
            if leveled_up: msg+=f"\n\n🎉 *LEVEL UP! Level {data['level']}!*"
        else: msg=f"🎬 *{name}* logged. Enjoy! ✅"
        await query.edit_message_text(msg,parse_mode="Markdown",reply_markup=mini_btn()); return

    if query.data.startswith("pen_done_"):
        pen_id=query.data[9:]
        penalties=data.get("pending_penalties",[])
        pen=next((p for p in penalties if p["id"]==pen_id),None)
        if not pen: await query.edit_message_text("Already cleared."); return
        stat=pen["stat"]
        data["stats"][stat]=min(100,data["stats"][stat]+1)
        data["pending_penalties"]=[p for p in penalties if p["id"]!=pen_id]
        if not data["pending_penalties"]: data["locked"]=False
        save_data(data)
        rem=len(data["pending_penalties"])
        msg=(f"⚠️ *PENALTY CLEARED*\n\n30 press-ups + 30 squats done.\n"
             f"{STAT_EMOJI[stat]} {stat} +1\n\n"
             f"{'✅ All cleared. System unlocked!' if not rem else f'⚠️ {rem} remaining.'}")
        await query.edit_message_text(msg,parse_mode="Markdown",reply_markup=mini_btn()); return

    if query.data.startswith("bonus_") and "|" in query.data:
        parts=query.data.replace("bonus_","",1).split("|")
        qid,stat,xp=parts[0],parts[1],int(parts[2])
        data["completed_today"].append(qid)
        data["total_xp"]+=xp
        data["stats"][stat]=min(100,data["stats"][stat]+5)
        save_data(data)
        await query.edit_message_text(
            f"⭐ *BONUS COMPLETE!*\n\n{STAT_EMOJI[stat]} {stat} +5 | +{xp} XP\n\nExtra mile. Respect. 🔥",
            parse_mode="Markdown",reply_markup=mini_btn()); return

    if query.data=="bonus_decline":
        await query.edit_message_text("👍 Declined. No penalty.\nFocus on your main quests.",reply_markup=mini_btn()); return

async def send_quest_notification(context):
    quest=context.job.data
    qid,name,t,dur,xp,stat,days=quest
    data=load_data()
    if qid in data["completed_today"] or qid in data.get("skipped_today",[]): return
    if data.get("locked"):
        await context.bot.send_message(chat_id=USER_ID,
            text=f"🔒 *LOCKED*\n*{name}* skipped. Clear penalties: /penalty",parse_mode="Markdown"); return
    is_free=xp==0
    if is_free:
        kb=[[InlineKeyboardButton("🎬 Log Free Time",callback_data=f"done_{qid}")]]
        text=f"🎬 *FREE TIME*\n\n{name}\n⏱ {dur} mins — You earned this. Enjoy."
    else:
        kb=[[InlineKeyboardButton("✅ Mark Complete",callback_data=f"done_{qid}")]]
        text=f"⚡ *QUEST AVAILABLE*\n\n{STAT_EMOJI[stat]} *{name}*\n⏱ {dur} mins | 💎 +{xp} XP | +3 {stat}"
    if MINI_APP_URL: kb.append([InlineKeyboardButton("⚡ Open The System",web_app=WebAppInfo(url=MINI_APP_URL))])
    await context.bot.send_message(chat_id=USER_ID,text=text,parse_mode="Markdown",reply_markup=InlineKeyboardMarkup(kb))

async def hourly_decay(context):
    data=load_data()
    if not data.get("locked"): return
    penalties=data.get("pending_penalties",[])
    if not penalties: return
    affected=list(set(p["stat"] for p in penalties))
    for s in affected: data["stats"][s]=max(0,data["stats"][s]-1)
    save_data(data)
    sl=" | ".join(f"{STAT_EMOJI[s]} {s}" for s in affected)
    await context.bot.send_message(chat_id=USER_ID,
        text=f"⏰ *PENALTY DECAY*\n\n{sl}\nEach -1 this hour.\n\nClear now: /penalty",parse_mode="Markdown")

async def bonus_check(context):
    data=load_data(); bonus=get_bonus_quests(data)
    if not bonus: return
    low=[s for s in STATS if data["stats"].get(s,10)<20]
    if not low: return
    sl="\n".join(f"{STAT_EMOJI[s]} {s}: {data['stats'][s]}" for s in low)
    await context.bot.send_message(chat_id=USER_ID,
        text=f"💡 *BONUS QUESTS AVAILABLE*\n\nStats below 20:\n{sl}\n\n/bonus to view. No penalty for declining.",
        parse_mode="Markdown")

def schedule_jobs(app):
    for quest in QUESTS:
        qid,name,t,dur,xp,stat,days=quest
        h,m=map(int,t.split(":"))
        if days=="daily":
            app.job_queue.run_daily(send_quest_notification,
                time=time(h,m,tzinfo=TIMEZONE),data=quest,name=f"q_{qid}")
        else:
            for day in days:
                ptb_day=(day+1)%7
                app.job_queue.run_daily(send_quest_notification,
                    time=time(h,m,tzinfo=TIMEZONE),days=(ptb_day,),data=quest,name=f"q_{qid}_{day}")
    app.job_queue.run_repeating(hourly_decay,interval=3600,first=60)
    app.job_queue.run_daily(bonus_check,time=time(12,0,tzinfo=TIMEZONE),name="bonus_check")

def main():
    threading.Thread(target=run_flask,daemon=True).start()
    logger.info(f"⚡ Flask on port {PORT}")
    app=Application.builder().token(BOT_TOKEN).build()
    for cmd,fn in [("start",cmd_start),("status",cmd_status),("quests",cmd_quests),
                   ("done",cmd_done),("skip",cmd_skip),("bonus",cmd_bonus),
                   ("penalty",cmd_penalty),("export",cmd_export),("help",cmd_help)]:
        app.add_handler(CommandHandler(cmd,fn))
    app.add_handler(CallbackQueryHandler(button_callback))
    schedule_jobs(app)
    logger.info("⚡ THE SYSTEM IS ONLINE")
    app.run_polling(drop_pending_updates=True)

if __name__=="__main__":
    main()
