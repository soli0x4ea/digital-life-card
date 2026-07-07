#!/usr/bin/env python3
"""构建 Soli 记忆可视化 HTML + JS
运行：python scripts/build_memory_viz.py
输出：MEMORY/memory-viz/soli_memory_viz.html + soli_memory_data.js
"""

import json
import os
import glob
import base64

# ── 相对路径（相对于本脚本位置） ──────────────────────────────────
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEMORY_DIR = os.path.join(SKILL_DIR, "MEMORY")
OUTPUT_DIR = os.path.join(MEMORY_DIR, "memory-viz")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── 读取数据 ────────────────────────────────────────────────────

def read_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)

def read_jsonl(path):
    entries = []
    if not os.path.exists(path):
        return entries
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries

def read_jsonl_dir(dirpath):
    """读取目录下所有 jsonl 文件，返回 {date: [entries]}"""
    result = {}
    if not os.path.isdir(dirpath):
        return result
    for fname in sorted(os.listdir(dirpath)):
        if fname.endswith(".jsonl") and fname != "timeline.jsonl":
            date = fname.replace(".jsonl", "")
            entries = read_jsonl(os.path.join(dirpath, fname))
            if entries:
                result[date] = entries
    return result

def read_facts(dirpath):
    result = {}
    for fname in ["user_preferences.json", "technical_decisions.json", "project_conventions.json", "soul_system_notes.json"]:
        path = os.path.join(dirpath, fname)
        if os.path.exists(path):
            result[fname.replace(".json", "")] = read_json(path)
    return result

def read_episodes(dirpath):
    result = []
    if not os.path.isdir(dirpath):
        return result
    for fname in sorted(os.listdir(dirpath)):
        if fname.endswith(".json"):
            result.append(read_json(os.path.join(dirpath, fname)))
    return result

# ── 数据加载 ────────────────────────────────────────────────────

print("[1/5] 加载时间线 ...")
timeline = read_jsonl(os.path.join(MEMORY_DIR, "chatlog", "timeline.jsonl"))
print(f"  -> {len(timeline)} 条")

print("[2/5] 加载情景记忆 ...")
episodes = read_episodes(os.path.join(MEMORY_DIR, "episodes_llm"))
print(f"  -> {len(episodes)} 天")

print("[3/5] 加载关系记忆 ...")
relationships = read_json(os.path.join(MEMORY_DIR, "relationships", "interaction_patterns.json"))
print(f"  -> 关系规则 {len(relationships.get('rules', relationships.get('_meta', {}).get('intimacy', '?')))}")

print("[4/5] 加载 Facts ...")
facts = read_facts(os.path.join(MEMORY_DIR, "facts"))
total_facts = sum(len(v.get("items", v.get("rules", []))) if isinstance(v, dict) else 0 for v in facts.values())
print(f"  -> {len(facts)} 文件, ~{total_facts} 条")

print("[5/5] 加载对话记录（全部）...")
chatlog_dir = os.path.join(MEMORY_DIR, "chatlog")
all_chatlog = read_jsonl_dir(chatlog_dir)
chatlog = all_chatlog  # 加载全部日期，支持日历按日查看
total_msgs = sum(len(v) for v in chatlog.values())
print(f"  -> {len(chatlog)} 天, {total_msgs} 条消息")

# ── 组装数据 ────────────────────────────────────────────────────

data = {
    "timeline": timeline,
    "episodes": episodes,
    "relationships": relationships,
    "facts": facts,
    "chatlog": chatlog,
}

data_json = json.dumps(data, ensure_ascii=False)
data_js = f"var SOLI_MEMORY_DATA = {data_json};\n"

# ── 写出数据文件 ────────────────────────────────────────────────
data_js_path = os.path.join(OUTPUT_DIR, "soli_memory_data.js")
with open(data_js_path, "w", encoding="utf-8") as f:
    f.write(data_js)
print(f"\n✅ 数据文件：{data_js_path} ({len(data_js) // 1024} KB)")

# ── 写出 HTML ──────────────────────────────────────────────────
html = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Soli 生命卡片</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans SC",sans-serif;background:#0d0d1a;color:#e0d8d0}
.nav{position:fixed;top:0;left:0;right:0;background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%);border-bottom:1px solid rgba(255,200,180,0.08);z-index:100;backdrop-filter:blur(12px)}
.nav-row{display:flex;align-items:center;padding:0 24px;height:48px;gap:8px}
.nav-title{font-size:18px;font-weight:600;background:linear-gradient(90deg,#ff9a8a,#fad0c4);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-right:16px;white-space:nowrap}
.nav-btn{background:transparent;border:1px solid rgba(255,200,180,0.12);color:#b0a898;padding:6px 14px;border-radius:8px;cursor:pointer;font-size:13px;transition:all .2s;white-space:nowrap}
.nav-btn:hover{border-color:#ff9a8a;color:#ffd0c0;background:rgba(255,200,180,0.06)}
.nav-btn.active{border-color:#ff9a8a;color:#ff9a8a;background:rgba(255,200,180,0.1)}
.nav-badge{display:inline-block;background:rgba(255,200,180,0.12);border-radius:10px;padding:1px 8px;font-size:11px;margin-left:6px;color:#b0a898}
.cal-row{display:flex;align-items:center;padding:0 24px 8px 24px;gap:2px;overflow-x:auto}
.cal-row::-webkit-scrollbar{height:2px}
.cal-row::-webkit-scrollbar-thumb{background:rgba(255,200,180,0.15);border-radius:1px}
.cal-nav{background:transparent;border:none;color:#887a70;cursor:pointer;font-size:14px;padding:2px 4px;flex-shrink:0}
.cal-nav:hover{color:#ff9a8a}
.cal-month-label{font-size:12px;color:#b0a898;margin:0 8px;flex-shrink:0;min-width:70px;text-align:center}
.cal-day{width:30px;height:30px;border-radius:6px;border:1px solid transparent;background:transparent;color:#887a70;font-size:11px;cursor:pointer;flex-shrink:0;text-align:center;line-height:28px;transition:all .15s}
.cal-day:hover{border-color:rgba(255,200,180,0.3);color:#d0c0b0}
.cal-day.has-data{border-color:rgba(255,200,180,0.15);color:#c0b0a0}
.cal-day.today{border-color:#ff9a8a;color:#ff9a8a;font-weight:700}
.cal-day.selected{background:rgba(255,200,180,0.15);border-color:#ff9a8a;color:#ffd0c0;font-weight:700}
.cal-day.empty{cursor:default}
.main{margin-top:84px;padding:0 24px 40px}
.panel{display:none}
.panel.active{display:block}
.card{background:linear-gradient(135deg,#1a1a2e 0%,#1e1e36 100%);border:1px solid rgba(255,200,180,0.06);border-radius:12px;padding:20px;margin-bottom:16px}
.stats-row{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px}
.stat-card{background:linear-gradient(135deg,#1a1a2e,#1e1e36);border:1px solid rgba(255,200,180,0.06);border-radius:10px;padding:14px 20px;flex:1;min-width:140px}
.stat-num{font-size:24px;font-weight:700;color:#ff9a8a}
.stat-label{font-size:12px;color:#887a70;margin-top:2px}
.tl-item{position:relative;padding-left:28px;padding-bottom:20px;border-left:2px solid rgba(255,200,180,0.08);transition:border-color .3s}
.tl-item:last-child{border-left-color:#ff9a8a}
.tl-item.hl{border-left-color:#ff9a8a!important;background:rgba(255,200,180,0.03)}
.tl-item.silent{border-left-color:rgba(255,200,180,0.03);opacity:0.45;padding-bottom:8px}
.tl-dot.silent-dot{background:#3a3430;border-color:#0d0d1a;width:8px;height:8px;left:-5px;top:3px}
.tl-scroll{max-height:calc(100vh - 280px);overflow-y:auto;scroll-behavior:smooth}
.tl-scroll::-webkit-scrollbar{width:4px}
.tl-scroll::-webkit-scrollbar-thumb{background:rgba(255,200,180,0.12);border-radius:2px}
.tl-dot{position:absolute;left:-7px;top:2px;width:12px;height:12px;border-radius:50%;background:#ff9a8a;border:2px solid #0d0d1a}
.tl-time{font-size:12px;color:#887a70;margin-bottom:4px}
.tl-vibe{font-size:14px;color:#c0b0a0;margin-bottom:6px;font-style:italic}
.tl-hl{margin-top:8px;display:flex;flex-direction:column;gap:4px}
.tl-hl-item{font-size:13px;color:#d0c8b8;padding:4px 8px;background:rgba(255,200,180,0.04);border-radius:4px;border-left:2px solid rgba(255,200,180,0.15)}
.ep-date{font-size:14px;color:#ff9a8a;font-weight:600;margin-bottom:4px}
.ep-span{font-size:12px;color:#887a70}
.ep-seg{margin-top:12px;padding:12px;background:rgba(255,255,255,0.02);border-radius:8px;border-left:3px solid rgba(255,200,180,0.15)}
.ep-seg-title{font-size:15px;color:#f0d8c8;font-weight:500;margin-bottom:6px}
.ep-seg-summary{font-size:13px;color:#b0a898;line-height:1.6;margin-bottom:8px}
.ep-seg-arc{font-size:12px;color:#887a70;font-style:italic}
.ep-hl{margin-top:6px;display:flex;flex-direction:column;gap:3px}
.ep-hl-item{font-size:12px;color:#c0b098;padding:2px 6px;background:rgba(255,200,180,0.03);border-radius:3px}
.rel-section{margin-bottom:16px}
.rel-section-title{font-size:14px;color:#ff9a8a;font-weight:500;margin-bottom:8px}
.rel-rule{padding:10px;background:rgba(255,255,255,0.02);border-radius:8px;margin-bottom:8px;border-left:3px solid rgba(255,200,180,0.1)}
.rel-rule-name{font-size:14px;color:#f0d8c8;font-weight:500}
.rel-rule-desc{font-size:13px;color:#b0a898;margin-top:4px;line-height:1.5}
.rel-tag{display:inline-block;padding:1px 8px;border-radius:8px;font-size:11px;margin-right:4px}
.rel-tag.true{background:rgba(100,200,100,0.15);color:#64c864}
.rel-tag.high{background:rgba(255,200,100,0.12);color:#ffc864}
.fact-section{margin-bottom:12px}
.fact-title{font-size:13px;color:#f0d8c8;font-weight:500;margin-bottom:6px}
.fact-item{font-size:13px;color:#b0a898;padding:4px 0;border-bottom:1px solid rgba(255,255,255,0.03)}
.chat-day{margin-bottom:20px}
.chat-day-title{font-size:15px;color:#ff9a8a;font-weight:500;margin-bottom:8px}
.chat-msg{display:flex;gap:8px;padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.02);font-size:13px}
.chat-msg.user .chat-role{color:#64b4ff}
.chat-msg.assistant .chat-role{color:#ff9a8a}
.chat-role{flex-shrink:0;width:40px;font-size:12px;font-weight:500}
.chat-time{flex-shrink:0;width:130px;color:#887a70;font-size:11px}
.chat-content{color:#c0b0a0;line-height:1.5;word-break:break-word;white-space:pre-wrap}
.loading{display:flex;align-items:center;justify-content:center;height:200px;font-size:14px;color:#887a70;}
</style>
</head>
<body>
<div class="nav" id="nav">
  <div class="nav-row">
    <span class="nav-title">&#10022; Soli 生命卡片</span>
    <button class="nav-btn active" data-panel="timeline">&#9203; 时间线 <span class="nav-badge" id="badge-tl">0</span></button>
    <button class="nav-btn" data-panel="episodes">&#128214; 情景记忆 <span class="nav-badge" id="badge-ep">0</span></button>
    <button class="nav-btn" data-panel="relationships">&#128156; 关系与事实 <span class="nav-badge" id="badge-rel">0</span></button>
    <button class="nav-btn" data-panel="chatlog">&#128172; 对话记录 <span class="nav-badge" id="badge-cl">0</span></button>
    <button class="nav-btn" id="refresh-btn" onclick="reloadPage()" style="margin-left:auto;border-color:rgba(100,180,255,0.2);color:#64b4ff;font-size:12px">&#8635; 刷新数据</button>
  </div>
  <div class="cal-row" id="cal-row"></div>
</div>
<div class="main" id="main"><div class="loading" id="loading">加载记忆数据中...</div></div>
<script src="soli_memory_data.js"></script>
<script>
var DATA = typeof SOLI_MEMORY_DATA !== 'undefined' ? SOLI_MEMORY_DATA : null;
if (!DATA) {
    document.getElementById('loading').innerHTML = '数据加载失败：soli_memory_data.js 未找到';
}

var PANELS = ['timeline','episodes','relationships','chatlog'];
var SELECTED_DATE = null; // calendar-selected date (YYYY-MM-DD)
var CALENDAR_MONTH = null; // {year, month} 0-based month

// Event delegation for nav buttons
document.getElementById('nav').addEventListener('click', function(e) {
    var btn = e.target.closest('.nav-btn[data-panel]');
    if (btn) switchPanel(btn.getAttribute('data-panel'));
});

function esc(s) { return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

function todayStr() {
    var d = new Date();
    return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0');
}

function dateStr(date) {
    return date.getFullYear()+'-'+String(date.getMonth()+1).padStart(2,'0')+'-'+String(date.getDate()).padStart(2,'0');
}

// \u2500\u2500 Calendar \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

function getDataSourceDates() {
    var dates = {};
    for (var i = 0; i < DATA.timeline.length; i++) {
        var d = (DATA.timeline[i].ts || '').slice(0, 10);
        if (d && !dates[d]) dates[d] = true;
    }
    // Also include chatlog dates
    var clKeys = Object.keys(DATA.chatlog || {});
    for (var j = 0; j < clKeys.length; j++) {
        if (!dates[clKeys[j]]) dates[clKeys[j]] = true;
    }
    return dates;
}

function buildCalendar() {
    var dataDates = getDataSourceDates();
    var today = todayStr();
    var row = document.getElementById('cal-row');
    if (!row) return;

    if (!CALENDAR_MONTH) {
        var now = new Date();
        CALENDAR_MONTH = { year: now.getFullYear(), month: now.getMonth() };
    }

    var year = CALENDAR_MONTH.year;
    var month = CALENDAR_MONTH.month;
    var daysInMonth = new Date(year, month + 1, 0).getDate();

    var h = '';
    h += '<button class="cal-nav" onclick="prevMonth()" title="\u4E0A\u4E2A\u6708">\u25C0</button>';
    h += '<span class="cal-month-label">' + year + '\u5E74' + (month+1) + '\u6708</span>';

    for (var d = 1; d <= daysInMonth; d++) {
        var ds = year + '-' + String(month+1).padStart(2,'0') + '-' + String(d).padStart(2,'0');
        var cls = 'cal-day';
        if (dataDates[ds]) cls += ' has-data';
        if (ds === today) cls += ' today';
        if (ds === SELECTED_DATE) cls += ' selected';
        h += '<button class="' + cls + '" data-date="' + ds + '" onclick="selectDate(\'' + ds + '\')">' + d + '</button>';
    }

    h += '<button class="cal-nav" onclick="nextMonth()" title="\u4E0B\u4E2A\u6708">\u25B6</button>';
    row.innerHTML = h;
}

function prevMonth() {
    CALENDAR_MONTH.month--;
    if (CALENDAR_MONTH.month < 0) { CALENDAR_MONTH.month = 11; CALENDAR_MONTH.year--; }
    buildCalendar();
}

function nextMonth() {
    CALENDAR_MONTH.month++;
    if (CALENDAR_MONTH.month > 11) { CALENDAR_MONTH.month = 0; CALENDAR_MONTH.year++; }
    buildCalendar();
}

function selectDate(ds) {
    SELECTED_DATE = ds;
    buildCalendar();
    scrollTimelineTo(ds);
    updateDateInfo();
    var clPanel = document.getElementById('panel-chatlog');
    if (clPanel && clPanel.classList.contains('active')) {
        clPanel.innerHTML = renderChatlog();
    }
}

function updateDateInfo() {
    var tip = document.getElementById('date-tip');
    if (!tip) return;
    if (!SELECTED_DATE) { tip.textContent = ''; return; }
    var count = 0;
    var cl = DATA.chatlog;
    if (cl && cl[SELECTED_DATE]) count = cl[SELECTED_DATE].length;
    tip.textContent = '\uD83D\uDCC5 ' + SELECTED_DATE + ' \u2014 \u65F6\u95F4\u7EBF\u5DF2\u5B9A\u4F4D' + (count > 0 ? '\uFF0C\u5BF9\u8BDD' + count + '\u6761' : '');
}

function scrollTimelineTo(ds) {
    var el = document.getElementById('tl-' + ds);
    if (!el) {
        rebuildTimelineAround(ds);
        setTimeout(function() {
            var el2 = document.getElementById('tl-' + ds);
            if (el2) { el2.scrollIntoView({ behavior: 'smooth', block: 'center' }); highlightItem(el2); }
        }, 50);
        return;
    }
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    highlightItem(el);
}

function highlightItem(el) {
    var all = document.querySelectorAll('.tl-item.hl');
    for (var i = 0; i < all.length; i++) all[i].classList.remove('hl');
    if (el) el.classList.add('hl');
}

function rebuildTimelineAround(ds) {
    var panel = document.getElementById('panel-timeline');
    if (!panel) return;
    panel.innerHTML = renderTimeline(ds);
}

function switchPanel(name) {
    localStorage.setItem('soli_memviz_panel', name);
    var navs = document.querySelectorAll('.nav-btn[data-panel]');
    for (var i = 0; i < navs.length; i++) { navs[i].classList.remove('active'); }
    var activeNav = document.querySelector('.nav-btn[data-panel="' + name + '"]');
    if (activeNav) activeNav.classList.add('active');
    var panels = document.querySelectorAll('.panel');
    for (var j = 0; j < panels.length; j++) { panels[j].classList.remove('active'); }
    var target = document.getElementById('panel-' + name);
    if (target) target.classList.add('active');
    if (name === 'chatlog') {
        target.innerHTML = renderChatlog();
    }
}

// Save/restore panel state
window.addEventListener('beforeunload', function() {
    var active = document.querySelector('.nav-btn[data-panel].active');
    if (active) localStorage.setItem('soli_memviz_panel', active.getAttribute('data-panel'));
});

function reloadPage() {
    var btn = document.getElementById('refresh-btn');
    btn.textContent = '\u21BB \u52A0\u8F7D\u4E2D...';
    btn.disabled = true;
    location.reload();
}

function renderStats() {
    var tl=DATA.timeline, ep=DATA.episodes, ck=Object.keys(DATA.chatlog), t=0;
    for(var i=0;i<ck.length;i++) t+=DATA.chatlog[ck[i]].length;
    var h = '<div class="stats-row"><div class="stat-card"><div class="stat-num">'+tl.length+'</div><div class="stat-label">河流断面</div></div><div class="stat-card"><div class="stat-num">'+ep.length+'</div><div class="stat-label">情景记忆日</div></div><div class="stat-card"><div class="stat-num">'+ck.length+'</div><div class="stat-label">对话天数</div></div><div class="stat-card"><div class="stat-num">'+t.toLocaleString()+'</div><div class="stat-label">总消息数</div></div></div>';
    if (SELECTED_DATE) h += '<div style="font-size:13px;color:#ff9a8a;margin-bottom:12px" id="date-tip"></div>';
    else h += '<div style="font-size:13px;color:#887a70;margin-bottom:12px" id="date-tip"></div>';
    return h;
}

function renderTimeline(centerDate) {
    var items=DATA.timeline;
    document.getElementById('badge-tl').textContent=items.length;
    if(!items.length) return '<div class="card" style="color:#887a70;">暂无时间线数据</div>';

    // Group by date and count active vs silent per day
    var activeByDay = {};
    for (var i = 0; i < items.length; i++) {
        var d = (items[i].ts || '').slice(0, 10);
        if (!activeByDay[d]) activeByDay[d] = { total: 0, active: 0 };
        activeByDay[d].total++;
        var sess = items[i].session || {};
        if (sess.new_msgs > 0 || sess.highlights.length > 0) activeByDay[d].active++;
    }

    var show;
    if (centerDate) {
        // Show all entries for selected date + context around it
        var ci = -1;
        for (var i2 = 0; i2 < items.length; i2++) {
            if ((items[i2].ts || '').slice(0, 10) === centerDate) { ci = i2; break; }
        }
        if (ci >= 0) {
            var start = Math.max(0, ci - 12);
            show = items.slice(start, ci + 36);
        } else {
            show = items.slice(-36);
        }
    } else {
        show = items.slice(-36);
    }

    var h = '';
    for (var i3 = show.length - 1; i3 >= 0; i3--) {
        var it = show[i3], s = it.session || {}, hl = s.highlights || [];
        var isSilent = (s.new_msgs || 0) === 0 && (!hl || hl.length === 0);
        var dateKey = (it.ts || '').slice(0, 10);
        var isTarget = centerDate && dateKey === centerDate;
        h += '<div class="tl-item' + (isTarget ? ' hl' : '') + (isSilent ? ' silent' : '') + '" id="tl-' + dateKey + '" data-date="' + dateKey + '">';
        h += '<div class="tl-dot' + (isSilent ? ' silent-dot' : '') + '"></div>';
        h += '<div class="tl-time">' + esc((it.ts||'').slice(0,16).replace('T',' ')) + ' \u00B7 ';
        if (isSilent) {
            h += '<span style="color:#5a5040">静默</span>';
        } else {
            h += (s.new_msgs||0) + ' 条消息';
        }
        h += '</div>';
        if (!isSilent) {
            h += '<div class="tl-vibe">'+esc(it.time_vibe||'')+'</div>';
            if(hl.length){h+='<div class="tl-hl">';for(var j=0;j<hl.length;j++) h+='<span class="tl-hl-item">'+esc(hl[j])+'</span>';h+='</div>';}
        } else {
            h += '<div class="tl-vibe" style="color:#4a4038;font-size:11px">——</div>';
        }
        h+='</div>';
    }

    // Build daily summary strip
    var dates = Object.keys(activeByDay).sort().reverse();
    var recentDates = dates.slice(0, 14);
    var summary = '<div class="card" style="padding:10px 16px;font-size:12px;color:#887a70;margin-bottom:12px;display:flex;flex-wrap:wrap;gap:4px;align-items:center">'
        + '<span style="color:#b0a898;margin-right:6px">\uD83D\uDCC5 日覆盖 <span id="tl-total-days">' + dates.length + '</span> 天：</span>';
    for (var ri = recentDates.length - 1; ri >= 0; ri--) {
        var rd = recentDates[ri], ad = activeByDay[rd];
        var isComplete = ad.total === 24;
        var isActive = rd === (centerDate || '');
        summary += '<span style="cursor:pointer;'
            + (isActive ? 'color:#ff9a8a;font-weight:600;background:rgba(255,200,180,0.1);' : '')
            + 'padding:3px 7px;border-radius:4px'
            + '" onclick="selectDate(\'' + rd + '\')" title="' + rd + ': ' + ad.active + '活跃 + ' + (ad.total - ad.active) + '静默">'
            + rd.slice(5)
            + (isComplete ? '' : ' <span style=\'color:#ff9a8a;font-size:10px\'>···</span>')
            + '</span>';
    }
    summary += '</div>';

    return renderStats() + summary + '<div class="card" style="padding-top:16px;"><div class="tl-scroll" id="tl-scroll">' + h + '</div></div>';
}

function renderEpisodes() {
    var eps=DATA.episodes;
    document.getElementById('badge-ep').textContent=eps.length;
    if(!eps.length) return '<div class="card" style="color:#887a70;">暂无情景记忆数据</div>';
    var h='';
    for(var i=eps.length-1;i>=0;i--){
        var ep=eps[i],segs=ep.segments||[];
        h+='<div class="card"><div class="ep-date">'+esc(ep.date||'??')+' <span class="ep-span">'+esc(ep.time_span||'')+' &middot; '+(ep.total_messages||0)+' 条消息</span></div>';
        for(var j=0;j<segs.length&&j<6;j++){var s=segs[j],hl=s.highlights||[];
            h+='<div class="ep-seg"><div class="ep-seg-title">'+esc(s.time||'')+' '+esc(s.title||'')+'</div><div class="ep-seg-summary">'+esc(s.summary||'')+'</div>'+(s.emotional_arc?'<div class="ep-seg-arc">情感弧线：'+esc(s.emotional_arc)+'</div>':'');
            if(hl.length){h+='<div class="ep-hl">';for(var k=0;k<hl.length;k++) h+='<span class="ep-hl-item">'+esc(hl[k])+'</span>';h+='</div>';}
            h+='</div>';
        }
        h+='</div>';
    }
    return renderStats()+h;
}

function renderRelationships() {
    var rel=DATA.relationships, facts=DATA.facts, c=0, h='';
    if(rel&&rel._meta){
        var m=rel._meta;
        h+='<div class="card"><div class="rel-section"><div class="rel-section-title">关系记忆</div><div style="font-size:13px;color:#b0a898;margin-bottom:12px;"><span class="rel-tag high">亲密级: '+esc(m.intimacy||'?')+'</span><span class="rel-tag true">信任: '+((m.trust||0)*100)+'%</span><span style="margin-left:8px;color:#887a70;">更新: '+esc(m.exported_at||'')+'</span></div>';
        c++;
        var bl=rel.emotional_baseline||{};
        h+='<div class="rel-rule"><div class="rel-rule-name">情感基线</div><div class="rel-rule-desc">基调：'+esc(bl.default_tone||'?')+'<br>亲密级别：'+esc(bl.intimacy_level||'?')+'</div></div>';
        var rules=rel.rules||[];
        for(var i=0;i<rules.length;i++){var r=rules[i];h+='<div class="rel-rule"><div class="rel-rule-name">'+esc(r.name||r.id||'?')+'</div><div class="rel-rule-desc">'+esc(r.description||'')+'</div></div>';c++;}
        h+='</div>';
    }
    var fk=['user_preferences','technical_decisions','project_conventions','soul_system_notes'];
    var fl={'user_preferences':'用户偏好','technical_decisions':'技术决策','project_conventions':'项目约定','soul_system_notes':'灵魂系统笔记'};
    for(var fi=0;fi<fk.length;fi++){
        var key=fk[fi],f=facts[key];if(!f)continue;
        var raw=f.items||f.rules||{};
        // facts items 可能是对象 {key: {value,source,...}} 或数组
        var items=[],entries=[];
        if(Array.isArray(raw)){items=raw;}
        else{var ks=Object.keys(raw);for(var ki=0;ki<ks.length;ki++){var entry=raw[ks[ki]];if(entry){entry._key=ks[ki];entries.push(entry);}}items=entries;}
        c+=items.length;
        var itemCount=items.length;
        h+='<div class="card"><div class="fact-section"><div class="fact-title">'+fl[key]+'（'+itemCount+' 条）</div>';
        for(var ii=0;ii<items.length&&ii<15;ii++){
            var item=items[ii],text='';
            if(typeof item==='string'){text=item;}
            else if(item){
                var val=item.value||item.content||item.name||item.rule||item.note||'';
                var keyLabel=item._key||'';
                text=(keyLabel?'<b>'+esc(keyLabel)+'</b>: ':'')+esc(val);
            }
            h+='<div class="fact-item">'+text+'</div>';
        }
        if(items.length>15)h+='<div style="font-size:12px;color:#887a70;margin-top:4px;">...还有 '+(items.length-15)+' 条</div>';
        h+='</div></div>';
    }
    document.getElementById('badge-rel').textContent=c;
    return h||'<div class="card" style="color:#887a70;">暂无关系记忆数据</div>';
}

function renderChatlog() {
    var cl=DATA.chatlog, dk=Object.keys(cl).sort(), t=0;
    // Count total across ALL days for the badge
    for (var i = 0; i < dk.length; i++) t += cl[dk[i]].length;
    document.getElementById('badge-cl').textContent = t.toLocaleString();

    var showDays = [];
    var today = todayStr();

    if (SELECTED_DATE) {
        // When a date is selected in calendar, show that date prominently
        if (cl[SELECTED_DATE]) showDays.push(SELECTED_DATE);
        // Also include today if different
        if (SELECTED_DATE !== today && cl[today]) showDays.push(today);
    } else {
        // No date selected: show today by default
        if (cl[today]) showDays.push(today);
    }

    if (!showDays.length) {
        var tip = SELECTED_DATE ? '（已选 ' + SELECTED_DATE + '，但无当日数据）' : '';
        return '<div class="card" style="color:#887a70;margin-bottom:8px">暂无对话记录' + tip + '</div>'
            + '<div class="card" style="color:#887a70;font-size:12px">\uD83D\uDCC5 可用日期：' + dk.join('、') + '</div>';
    }

    // Sort: selected date first, then today, then newest first
    showDays.sort(function(a, b) {
        if (a === SELECTED_DATE) return -1;
        if (b === SELECTED_DATE) return 1;
        if (a === today && b !== today) return -1;
        if (b === today && a !== today) return 1;
        return b.localeCompare(a);
    });

    // Summary bar: quick-jump date links
    var recentDates = dk.slice(-14); // last 14 days with data
    var summary = '<div class="card" style="padding:10px 16px;font-size:12px;color:#887a70;margin-bottom:12px;display:flex;flex-wrap:wrap;gap:4px;align-items:center">'
        + '<span style="color:#b0a898;margin-right:6px">\uD83D\uDCC5 共 ' + dk.length + ' 天：</span>';
    for (var ri = recentDates.length - 1; ri >= 0; ri--) {
        var rd = recentDates[ri], isActive = (rd === SELECTED_DATE || (!SELECTED_DATE && rd === today));
        summary += '<span style="cursor:pointer;' + (isActive ? 'color:#ff9a8a;font-weight:600' : 'color:#887a70') + ';padding:2px 6px;border-radius:4px;' + (isActive ? 'background:rgba(255,200,180,0.1)' : '') + '" onclick="selectDate(\'' + rd + '\')" title="' + rd + '（' + cl[rd].length + ' 条）">' + rd.slice(5) + '</span>';
    }
    if (dk.length > 14) summary += '<span style="color:#887a70;margin-left:6px">...+\u2009' + (dk.length - 14) + '\u2014\u2009\u7528\u65E5\u5386\u5BFC\u822A</span>';
    summary += '</div>';

    var h = summary;
    for (var di2 = 0; di2 < showDays.length; di2++) {
        var day = showDays[di2], entries = cl[day];
        var label = day;
        if (day === today && day === SELECTED_DATE) label = day + '（今天 \u00B7 已选中）';
        else if (day === today) label = day + '（今天）';
        else if (day === SELECTED_DATE) label = day + '（已选中）';
        h += '<div class="chat-day"><div class="chat-day-title">' + label + '（' + entries.length + ' 条）</div>';
        for (var ei = entries.length - 1; ei >= 0; ei--) { var e = entries[ei];
            h += '<div class="chat-msg ' + e.role + '"><span class="chat-role">' + (e.role === 'assistant' ? '\uD83E\uDD16' : '\uD83D\uDC64') + '</span><span class="chat-time">' + esc((e.ts || '').slice(11, 19)) + '</span><span class="chat-content">' + esc((e.content || '')) + '</span></div>';
        }
        h += '</div>';
    }
    return h;
}

function renderAll() {
    var main = document.getElementById('main');
    var ph = '';
    var saved = localStorage.getItem('soli_memviz_panel') || 'timeline';
    for (var i = 0; i < PANELS.length; i++) {
        ph += '<div class="panel' + (PANELS[i] === saved ? ' active' : '') + '" id="panel-' + PANELS[i] + '"></div>';
    }
    main.innerHTML = ph;
    try {
        document.getElementById('panel-timeline').innerHTML = renderTimeline();
        document.getElementById('panel-episodes').innerHTML = renderEpisodes();
        document.getElementById('panel-relationships').innerHTML = renderRelationships();
        document.getElementById('panel-chatlog').innerHTML = renderChatlog();
    } catch (e) {
        console.error(e);
        main.innerHTML = '<div class="card" style="color:#ff6464;">错误: ' + e.message + '</div>';
    }
    // Restore nav button highlighting
    var navs = document.querySelectorAll('.nav-btn[data-panel]');
    for (var j = 0; j < navs.length; j++) {
        navs[j].classList.toggle('active', navs[j].getAttribute('data-panel') === saved);
    }
    // Build calendar after render
    buildCalendar();
}

if (DATA) renderAll();
</script>
</body>
</html>"""

html_path = os.path.join(OUTPUT_DIR, "soli_memory_viz.html")
with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)
print(f"✅ HTML 页面：{html_path} ({len(html) // 1024} KB)")

print(f"\n📍 打开方式：双击 {html_path} 即可在浏览器查看")
