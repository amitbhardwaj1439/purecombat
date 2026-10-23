"""Daily Combat Hub publisher for www.purecombat.in.

Free part (always runs):
  Collects the newest combat sports headlines from Google News (MMA, boxing, Muay Thai, kickboxing,
  Indian combat sports) and publishes them on the News page and the home page.

Optional AI part (only when ANTHROPIC_API_KEY is set, paid):
  Claude verifies the top stories with web search and writes an original Daily Combat Report
  (blog/<date>.html), and adds confirmed fight results to results.html.

Pages are regenerated from state.json, only between <!-- HUB:...:START/END --> markers.

Usage:
  python .github/combat_hub/combat_hub.py            daily run
  python .github/combat_hub/combat_hub.py --render   rebuild pages from state.json, no network
  python .github/combat_hub/combat_hub.py --force    regenerate today's AI report even if it exists
"""

import argparse
import email.utils
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATE_FILE = Path(__file__).with_name("state.json")
SITE = "https://www.purecombat.in"
IST = timezone(timedelta(hours=5, minutes=30))
MODEL = os.environ.get("COMBAT_HUB_MODEL") or "claude-opus-5-5"
MAX_SEARCHES = int(os.environ.get("COMBAT_HUB_MAX_SEARCHES") or "10")
SPORTS = ["MMA", "Boxing", "Muay Thai", "Kickboxing", "India"]

# (sport, Google News query). Indian queries look back further because there is less coverage.
FEEDS = [
    ("MMA", "UFC when:1d"),
    ("MMA", "MMA fight OR PFL OR \"ONE Championship\" when:1d"),
    ("Boxing", "boxing fight OR bout OR title when:1d"),
    ("Boxing", "boxing champion OR knockout when:1d"),
    ("Muay Thai", "\"Muay Thai\" when:2d"),
    ("Kickboxing", "kickboxing OR \"GLORY kickboxing\" when:2d"),
    ("India", "\"Matrix Fight Night\" OR \"MFN\" MMA when:7d"),
    ("India", "Indian boxer OR \"Boxing Federation of India\" when:3d"),
    ("India", "Indian MMA fighter OR India UFC when:3d"),
    ("India", "India kickboxing OR India \"Muay Thai\" when:7d"),
]
PER_FEED = 15
MIN_HEADLINES = 8
# A headline must mention at least one of these to count as combat sports news.
COMBAT_WORDS = re.compile(
    r"\b(ufc|mma|box(er|ers|ing)?|fight(s|er|ers|ing)?|bout|ko|tko|muay|kickbox\w*|(?-i:GLORY)|"
    r"one (championship|fc|friday|samurai)|mfn|matrix|pfl|bellator|octagon|title|belt|champion\w*|"
    r"undercard|weigh-?ins?|submission|sparring|grappl\w*|jiu-?jitsu|bjj|wrestl\w*|punch\w*|bantam\w*|"
    r"featherweight|lightweight|welterweight|middleweight|heavyweight|cruiserweight|flyweight|strawweight)\b",
    re.I)
OFF_TOPIC = re.compile(r"\b(net worth|arrest\w*|police|gangster|murder\w*|killed|steal\w*|thief|theft|"
                       r"detained|jailed|betting|horoscope)\b", re.I)
INDIA_WORDS = re.compile(
    r"\b(india|indian|indians|mfn|matrix fight night|boxing federation of india|bfi|delhi|mumbai|noida|"
    r"bengaluru|hyderabad|kolkata|chennai|punjab|haryana|manipur|khelo india)\b", re.I)
INDIAN_SOURCES = re.compile(
    r"times of india|hindustan|indian express|ndtv|ians|\bani\b|\bpti\b|sportstar|the hindu|rediff|lokmat|"
    r"dainik|dd news|telangana today|khel now|news18|india today|firstpost|tribune|deccan|mid-day|zee|"
    r"republic|outlook|economic times|sportskeeda|olympics\.com|the bridge", re.I)
INTERNATIONAL_MMA = re.compile(r"\b(ufc|pfl|bellator|one championship|dana white)\b", re.I)
SPORT_WORDS = [
    ("Muay Thai", re.compile(r"\bmuay\b", re.I)),
    ("Kickboxing", re.compile(r"\b(kickbox\w*|(?-i:GLORY))\b", re.I)),
    ("MMA", re.compile(r"\b(ufc|mma|pfl|bellator|octagon|one championship)\b", re.I)),
    ("Boxing", re.compile(r"\bbox(er|ers|ing)?\b", re.I)),
]
HEADLINES_PER_SPORT = 6
SOCIAL_SOURCES = {"facebook", "instagram", "youtube", "x", "twitter", "tiktok", "reddit"}

ARROW = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
         'stroke-linejoin="round" aria-hidden="true"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>')
ARROW_BACK = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
              'stroke-linejoin="round" aria-hidden="true"><path d="M19 12H5"/><path d="m12 19-7-7 7-7"/></svg>')


def log(msg):
    print(msg, flush=True)


def esc(text):
    return html.escape(str(text), quote=True)


def long_date(iso):
    d = datetime.strptime(iso, "%Y-%m-%d")
    return f"{d:%B} {d.day}, {d.year}"


def load_state():
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- headlines

def fetch_feed(query):
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": query, "hl": "en-IN", "gl": "IN", "ceid": "IN:en"})
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (PureCombat Combat Hub)"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        root = ET.fromstring(resp.read())
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        source = (item.findtext("source") or "").strip()
        if source and title.endswith(" - " + source):
            title = title[: -len(source) - 3].strip()
        try:
            published = email.utils.parsedate_to_datetime(item.findtext("pubDate"))
        except (TypeError, ValueError):
            continue
        yield {"title": title, "source": source, "url": (item.findtext("link") or "").strip(),
               "published": published}


def classify(title, source, feed_sport):
    """Pick the sport from the headline itself; the feed it came from is only a hint."""
    if INDIA_WORDS.search(title):
        return "India"
    if feed_sport == "India" and INDIAN_SOURCES.search(source) and not INTERNATIONAL_MMA.search(title):
        return "India"
    for sport, pattern in SPORT_WORDS:
        if pattern.search(title):
            return sport
    return feed_sport if feed_sport != "India" else "Boxing"


def collect_headlines():
    seen, headlines = set(), []
    for feed_sport, query in FEEDS:
        try:
            items = list(fetch_feed(query))
        except Exception as e:  # one broken feed should not stop the run
            log(f"  feed failed ({query}): {e}")
            continue
        items.sort(key=lambda h: h["published"], reverse=True)
        added = 0
        for h in items:
            key = re.sub(r"[^a-z0-9]", "", h["title"].lower())[:80]
            if (not h["title"] or key in seen or not COMBAT_WORDS.search(h["title"])
                    or OFF_TOPIC.search(h["title"]) or h["source"].lower() in SOCIAL_SOURCES):
                continue
            seen.add(key)
            headlines.append({**h, "sport": classify(h["title"], h["source"], feed_sport)})
            added += 1
            if added >= PER_FEED:
                break
        log(f"  {feed_sport:<10} {added:>2} new  <- {query}")
    for i, h in enumerate(headlines):
        h["id"] = i
    return headlines


def similar(a, b):
    """True when two headlines are mostly the same story (e.g. five outlets on one weigh-in)."""
    wa, wb = (set(re.findall(r"[a-z0-9]{4,}", t.lower())) for t in (a, b))
    return bool(wa and wb) and len(wa & wb) / min(len(wa), len(wb)) >= 0.5


def refresh_headlines(state, now):
    """Free daily update: the newest headlines per sport, no AI involved."""
    log("Collecting headlines...")
    headlines = collect_headlines()
    log(f"  {len(headlines)} unique headlines")
    if len(headlines) < MIN_HEADLINES:
        log("Too few headlines found; keeping the previous list.")
        return False
    picked = []
    for sport in SPORTS:
        newest = sorted((h for h in headlines if h["sport"] == sport), key=lambda h: h["published"], reverse=True)
        chosen = []
        for h in newest:
            if not any(similar(h["title"], c["title"]) for c in chosen):
                chosen.append(h)
            if len(chosen) == HEADLINES_PER_SPORT:
                break
        picked += chosen
    state["headlines"] = [
        {"title": h["title"], "source": h["source"], "url": h["url"], "sport": h["sport"],
         "date": h["published"].astimezone(IST).strftime("%Y-%m-%d")} for h in picked]
    state["headlines_updated"] = now.strftime("%Y-%m-%d %H:%M")
    log("  kept " + ", ".join(f"{s}: {sum(h['sport'] == s for h in picked)}" for s in SPORTS))
    return True


# ---------------------------------------------------------------- Claude

RESEARCH_SYSTEM = """You are the research editor for PURECOMBAT, an MMA and boxing academy in Noida, India, \
that publishes a daily combat sports report. Your job is to establish facts, not to write the article.

Rules:
- Only state facts you have confirmed in the headlines provided or with web search. Never guess results, \
records, dates, quotes or numbers. If something cannot be confirmed, leave it out.
- A fight result counts as confirmed only if a source reports that the fight has already happened, with the winner \
and the method.
- Prefer reputable outlets (official promotion sites, ESPN, major newspapers, established MMA/boxing media).
- Ignore stories that are not about combat sports, and ignore betting tips and listicles."""

RESEARCH_TASK = """Today is {today} (India time). Below are combat sports headlines from the last day or so.

1. Choose the 5-8 most important stories, covering as many of these as have real news: MMA, boxing, Muay Thai, \
kickboxing, and Indian combat sports (Matrix Fight Night / MFN, Indian boxers, Indian MMA, kickboxing and Muay Thai). \
Always include Indian stories when there are any.
2. Avoid repeating stories already covered in recent reports unless there is a genuinely new development:
{recent}
3. Use web search to confirm the key facts of each chosen story.
4. Reply with plain-text research notes. For each story: a heading, the sport, the confirmed facts as bullet points, \
and the URLs of the sources you used. Then a section "CONFIRMED RESULTS" listing fights from the last 7 days that \
have already taken place, one per line: event | date (YYYY-MM-DD) | sport | winner | loser | method | division. \
Write "none" if there are none. Then a line "HEADLINE IDS:" with the ids of the 8-12 most relevant headlines below.

Headlines:
{headlines}"""

WRITE_SYSTEM = """You write the PURECOMBAT Daily Combat Report for www.purecombat.in. PURECOMBAT is an MMA, \
boxing and fitness academy in Sector 122, Noida. Readers are Indian fight fans and people who train.

Voice: energetic, knowledgeable and respectful; plain English; short paragraphs. Write original prose. Never copy \
sentences from sources.

Accuracy rules (the report publishes automatically, with no human review):
- Use only facts that appear in the research notes. Do not add results, records, dates, quotes, ages or statistics \
from memory.
- Put a result in `results` only if it is listed under CONFIRMED RESULTS in the notes, using exactly those details.
- Give each section the URLs from the notes that support it.
- Use only headline ids that appear in the notes."""

WRITE_TASK = """Today is {today}. Write today's Daily Combat Report from these research notes.

- title: a punchy headline for the whole report, at most 70 characters.
- dek: a one-sentence summary for cards and search results, at most 160 characters.
- tags: the sports covered.
- intro: 2-3 sentences that set up the day.
- sections: one per story, 2-3 paragraphs each, in order of importance. sport must be one of the allowed values \
(use "India" for Indian combat sports).
- results: the confirmed results (may be empty).
- headline_ids: ids for the "latest headlines" list.
- takeaway: one short paragraph linking a lesson from today's news to training at PURECOMBAT. Do not invent \
promotions or prices.

Research notes:
{notes}"""

REPORT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "dek": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string", "enum": SPORTS}},
        "intro": {"type": "string"},
        "sections": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "heading": {"type": "string"},
                "sport": {"type": "string", "enum": SPORTS},
                "paragraphs": {"type": "array", "items": {"type": "string"}},
                "source_urls": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["heading", "sport", "paragraphs", "source_urls"],
            "additionalProperties": False,
        }},
        "results": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "event": {"type": "string"},
                "date": {"type": "string"},
                "sport": {"type": "string", "enum": SPORTS},
                "winner": {"type": "string"},
                "loser": {"type": "string"},
                "method": {"type": "string"},
                "division": {"type": "string"},
            },
            "required": ["event", "date", "sport", "winner", "loser", "method", "division"],
            "additionalProperties": False,
        }},
        "headline_ids": {"type": "array", "items": {"type": "integer"}},
        "takeaway": {"type": "string"},
    },
    "required": ["title", "dek", "tags", "intro", "sections", "results", "headline_ids", "takeaway"],
    "additionalProperties": False,
}

# Server-side fallback: if the model declines (safety classifier), the API retries on a recommended model.
FALLBACK = {"betas": ["server-side-fallback-2026-07-01"], "extra_body": {"fallbacks": "default"}}


def check_stop(message, step):
    if message.stop_reason == "refusal":
        raise SystemExit(f"{step}: the model declined the request ({getattr(message, 'stop_details', None)}); nothing published.")
    if message.stop_reason == "max_tokens":
        raise SystemExit(f"{step}: output hit max_tokens; nothing published.")


def research(client, today, headlines, recent):
    listing = "\n".join(
        f"[{h['id']}] ({h['sport']}) {h['title']} - {h['source']}, {h['published'].astimezone(IST):%Y-%m-%d}"
        for h in headlines)
    prompt = RESEARCH_TASK.format(today=today, recent=recent or "(none)", headlines=listing)
    messages = [{"role": "user", "content": prompt}]
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": MAX_SEARCHES}]
    usage = []
    for _ in range(5):  # resume pause_turn a bounded number of times
        with client.beta.messages.stream(
            model=MODEL, max_tokens=32000, system=RESEARCH_SYSTEM, messages=messages, tools=tools,
            output_config={"effort": "medium"}, **FALLBACK,
        ) as stream:
            message = stream.get_final_message()
        usage.append(message.usage)
        if message.stop_reason != "pause_turn":
            break
        messages = [messages[0], {"role": "assistant", "content": message.content}]
    check_stop(message, "research")

    content = message.to_dict()["content"]
    notes = "\n".join(b["text"] for b in content if b.get("type") == "text").strip()
    urls = set()
    for b in content:
        if b.get("type") == "web_search_tool_result" and isinstance(b.get("content"), list):
            urls.update(r.get("url") for r in b["content"] if r.get("url"))
    if len(notes) < 200:
        raise SystemExit("research: notes came back empty; nothing published.")
    return notes, urls, usage


def write_report(client, today, notes):
    message = client.beta.messages.create(
        model=MODEL, max_tokens=16000, system=WRITE_SYSTEM,
        messages=[{"role": "user", "content": WRITE_TASK.format(today=today, notes=notes)}],
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": REPORT_SCHEMA}},
        **FALLBACK,
    )
    check_stop(message, "writing")
    text = "".join(b.text for b in message.content if b.type == "text")
    return json.loads(text), message.usage


def tidy_report(report, notes, known_urls, headlines):
    """Drop anything that cannot be traced back to the research step."""
    for s in report["sections"]:
        s["paragraphs"] = [p.strip() for p in s["paragraphs"] if p.strip()]
        s["source_urls"] = [u for u in dict.fromkeys(s["source_urls"]) if u in known_urls or u in notes]
    report["sections"] = [s for s in report["sections"] if s["heading"].strip() and s["paragraphs"]]
    if len(report["sections"]) < 2:
        raise SystemExit("writing: fewer than two usable sections; nothing published.")

    notes_lower = notes.lower()
    kept = []
    for r in report["results"]:
        names_confirmed = r["winner"].lower() in notes_lower and r["loser"].lower() in notes_lower
        if names_confirmed and re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["date"]):
            kept.append(r)
        else:
            log(f"  dropped unverified result: {r['winner']} vs {r['loser']}")
    report["results"] = kept

    by_id = {h["id"]: h for h in headlines}
    report["headlines"] = [
        {"title": by_id[i]["title"], "source": by_id[i]["source"], "url": by_id[i]["url"],
         "sport": by_id[i]["sport"], "date": by_id[i]["published"].astimezone(IST).strftime("%Y-%m-%d")}
        for i in dict.fromkeys(report.pop("headline_ids")) if i in by_id][:12]
    report["tags"] = [t for t in SPORTS if t in report["tags"] or any(s["sport"] == t for s in report["sections"])]
    return report


def generate(state, today, force):
    if any(r["date"] == today and r["kind"] == "daily" for r in state["reports"]) and not force:
        log(f"Report for {today} already exists; rendering only.")
        return False
    if not os.environ.get("ANTHROPIC_API_KEY"):
        log("ANTHROPIC_API_KEY is not set; skipping report generation.")
        return False

    import anthropic
    client = anthropic.Anthropic()

    log("Collecting headlines...")
    headlines = collect_headlines()
    log(f"  {len(headlines)} unique headlines")
    if len(headlines) < MIN_HEADLINES:
        raise SystemExit("Too few headlines found; nothing published.")

    recent = "\n".join(f"- {r['date']}: " + "; ".join(r.get("headings", [r["title"]]))
                       for r in state["reports"][:3])
    log(f"Researching with {MODEL}...")
    notes, urls, usage = research(client, today, headlines, recent)
    log(f"  notes: {len(notes)} chars, {len(urls)} source URLs from web search")
    log("Writing report...")
    report, write_usage = write_report(client, today, notes)
    report = tidy_report(report, notes, urls | {h["url"] for h in headlines}, headlines)

    words = sum(len(p.split()) for s in report["sections"] for p in s["paragraphs"])
    words += len(report["intro"].split()) + len(report["takeaway"].split())
    entry = {
        "kind": "daily", "date": today, "slug": f"blog/{today}.html",
        "title": report["title"].strip(), "dek": report["dek"].strip(), "tags": report["tags"],
        "headings": [s["heading"] for s in report["sections"]],
        "read_min": max(2, round(words / 200)),
    }
    state["reports"] = [entry] + [r for r in state["reports"] if r["slug"] != entry["slug"]]
    (ROOT / "blog").mkdir(exist_ok=True)
    (ROOT / entry["slug"]).write_text(render_report_page(entry, report), encoding="utf-8")

    existing = {(r["event"].lower(), r["winner"].lower(), r["loser"].lower()) for r in state["results"]}
    new_results = [r for r in report["results"]
                   if (r["event"].lower(), r["winner"].lower(), r["loser"].lower()) not in existing]
    state["results"] = sorted(new_results + state["results"], key=lambda r: r["date"], reverse=True)[:60]

    for u in usage + [write_usage]:
        log(f"  usage: in={u.input_tokens} out={u.output_tokens} "
            f"searches={getattr(getattr(u, 'server_tool_use', None), 'web_search_requests', 0)}")
    log(f"Published {entry['slug']}: {entry['title']} ({len(report['sections'])} sections, "
        f"{len(new_results)} new results)")
    return True


# ---------------------------------------------------------------- rendering

def page_chrome():
    """Header and footer markup, taken from the hand-made week-1 article so the design stays in sync."""
    source = (ROOT / "blog" / "week-1.html").read_text(encoding="utf-8")
    header = source[source.index("<body"):source.index('<main id="main">')]
    footer = source[source.index("</main>") + len("</main>"):]
    return header, footer


def render_report_page(entry, report):
    header, footer = page_chrome()
    url = f"{SITE}/{entry['slug']}"
    full_title = f"{entry['title']} | PURECOMBAT Daily Combat Report"
    ld = json.dumps({
        "@context": "https://schema.org", "@type": "NewsArticle", "headline": entry["title"],
        "description": entry["dek"], "datePublished": entry["date"],
        "author": {"@type": "Organization", "name": "Team PURECOMBAT"},
        "publisher": {"@type": "Organization", "name": "PURECOMBAT",
                      "logo": {"@type": "ImageObject", "url": f"{SITE}/images/logo.png"}},
    })
    head = f"""<!DOCTYPE html>
<html lang="en" class="no-js">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(full_title)}</title>
<meta name="description" content="{esc(entry['dek'])}">
<link rel="canonical" href="{url}">
<meta name="theme-color" content="#0b0b0c">

<meta property="og:type" content="article">
<meta property="og:site_name" content="PURECOMBAT">
<meta property="og:title" content="{esc(full_title)}">
<meta property="og:description" content="{esc(entry['dek'])}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{SITE}/images/logo.png">
<meta name="twitter:card" content="summary">

<link rel="icon" type="image/png" href="../images/favicon.png">
<link rel="apple-touch-icon" href="../images/apple-touch-icon.png">

<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Oswald:wght@500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="../css/style.css">
<script type="application/ld+json">{ld}</script>
</head>
"""
    tags = "".join(f'<span class="pill pill-muted">{esc(t)}</span>' for t in entry["tags"])
    body = [f'<p class="intro">{esc(report["intro"])}</p>']
    for s in report["sections"]:
        body.append(f'<h2>{esc(s["heading"])}</h2>')
        body.extend(f"<p>{esc(p)}</p>" for p in s["paragraphs"])
        if s["source_urls"]:
            links = ", ".join(
                f'<a href="{esc(u)}" target="_blank" rel="noopener nofollow">{esc(domain(u))}</a>'
                for u in s["source_urls"][:4])
            body.append(f'<p class="sources">Sources: {links}</p>')
    if report["results"]:
        body.append("<h2>Results roundup</h2>")
        body.append('<div class="result-list">' + "".join(result_card(r) for r in report["results"]) + "</div>")
    body.append("<h2>The PureCombat takeaway</h2>")
    body.append(f"<p>{esc(report['takeaway'])}</p>")
    body.append("<p><strong>— Team PURECOMBAT</strong></p>")
    body.append('<p class="ai-note">This report is compiled automatically from public news sources and written '
                'with AI assistance. Spotted an error? <a href="mailto:purecombatprivatelimited@gmail.com">'
                'Let us know</a>.</p>')

    main = f"""<main id="main">
  <article>
    <div class="article-hero">
      <div class="article-wrap">
        <nav class="breadcrumb" aria-label="Breadcrumb"><a href="../index.html">Home</a><span>/</span><a href="../blogs.html">News</a><span>/</span><span>{esc(long_date(entry['date']))}</span></nav>
        <header class="article-header">
          <span class="eyebrow">Daily Combat Report · {esc(long_date(entry['date']))}</span>
          <h1>{esc(entry['title'])}</h1>
          <div class="article-byline">
            <img src="../images/logo-mark.png" alt="">
            <span>Team PURECOMBAT</span><span class="dot"></span>
            <time datetime="{entry['date']}">{esc(long_date(entry['date']))}</time><span class="dot"></span>
            <span>{entry['read_min']} min read</span>
          </div>
        </header>
        <div class="article-tags">{tags}</div>
      </div>
    </div>

    <div class="article-wrap prose">
      {(chr(10) + '      ').join(body)}

      <div class="article-footer">
        <a href="../blogs.html" class="link-arrow">{ARROW_BACK} All reports</a>
        <a href="../index.html#contact" class="btn btn-primary">Train with PureCombat {ARROW}</a>
      </div>
    </div>
  </article>
</main>"""
    return head + header + main + footer


def domain(url):
    host = urllib.parse.urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def result_card(r):
    month = datetime.strptime(r["date"], "%Y-%m-%d").strftime("%B %Y")
    division = f'\n            <div class="result-division">{esc(r["division"])}</div>' if r["division"] else ""
    return f"""
        <article class="result reveal">
          <div class="result-event"><small>{esc(r['sport'])} · {month}</small><strong>{esc(r['event'])}</strong></div>
          <div>
            <div class="result-fight"><span class="winner">{esc(r['winner'])}</span><span class="vs">def.</span><span class="loser">{esc(r['loser'])}</span></div>{division}
          </div>
          <span class="pill">{esc(r['method'])}</span>
        </article>"""


def report_card(r, prefix=""):
    href = prefix + r["slug"]
    if r.get("image"):
        cover = (f'<a href="{href}" class="post-img"><img src="{prefix}{r["image"]}" '
                 f'alt="{esc(r.get("image_alt", ""))}" loading="lazy"></a>')
    else:
        d = datetime.strptime(r["date"], "%Y-%m-%d")
        cover = (f'<a href="{href}" class="post-img post-cover" aria-hidden="true" tabindex="-1">'
                 f'<small>Daily Combat Report</small><strong>{d:%b} {d.day}</strong>'
                 f'<span>{esc(" · ".join(r["tags"]))}</span></a>')
    label = r.get("label") or "Daily Report"
    return f"""
        <article class="card post-card reveal">
          {cover}
          <div class="post-body">
            <div class="post-meta"><span class="tag">{esc(label)}</span><span>{esc(long_date(r['date']))}</span></div>
            <h3><a href="{href}">{esc(r['title'])}</a></h3>
            <p>{esc(r['dek'])}</p>
            <a href="{href}" class="link-arrow">Read article {ARROW}</a>
          </div>
        </article>"""


def headline_item(h, indent):
    d = datetime.strptime(h["date"], "%Y-%m-%d")
    return (f'\n{indent}<li><a href="{esc(h["url"])}" target="_blank" rel="noopener nofollow">'
            f'<small><b>{esc(h["sport"])}</b> · {esc(h["source"])} · {d:%b} {d.day}</small>'
            f'<span>{esc(h["title"])}</span></a></li>')


def updated_label(state, short=False):
    stamp = datetime.strptime(state["headlines_updated"], "%Y-%m-%d %H:%M")
    return f"Updated {stamp.day} {stamp:%b}" if short else f"Updated {stamp.day} {stamp:%b %Y, %H:%M} IST"


def headlines_block(state):
    items = state.get("headlines", [])
    if not items:
        return ""
    groups = []
    for sport in SPORTS:
        lis = "".join(headline_item(h, "          ") for h in items if h["sport"] == sport)
        if lis:
            title = "Indian combat sports" if sport == "India" else sport
            groups.append(f'\n        <h3>{esc(title)}</h3>\n        <ul class="headline-list">{lis}\n        </ul>')
    return f"""
      <div class="headlines reveal">
        <span class="eyebrow">Around the fight world · {esc(updated_label(state))}</span>
        <h2>Latest headlines</h2>{"".join(groups)}
        <p class="headlines-note">Headlines link to the original publishers and refresh automatically every day.</p>
      </div>"""


def home_headlines_card(state):
    items = state["headlines"]
    top = [next(h for h in items if h["sport"] == s) for s in SPORTS if any(h["sport"] == s for h in items)]
    lis = "".join(headline_item(h, "            ") for h in top[:5])
    return f"""
        <article class="card feature-card reveal">
          <div>
            <span class="eyebrow">{esc(updated_label(state, short=True))}</span>
            <h3>Today&rsquo;s headlines</h3>
            <ul class="headline-list mini">{lis}
            </ul>
          </div>
          <a href="blogs.html" class="link-arrow">All headlines {ARROW}</a>
        </article>"""


def replace_block(path, name, content):
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(rf"(<!-- HUB:{name}:START -->).*?(\n[ \t]*<!-- HUB:{name}:END -->)", re.S)
    if not pattern.search(text):
        raise SystemExit(f"Marker HUB:{name} not found in {path.name}")
    text = pattern.sub(lambda m: m.group(1) + content + m.group(2), text, count=1)
    path.write_text(text, encoding="utf-8")


def render_site(state):
    reports = state["reports"]
    replace_block(ROOT / "blogs.html", "REPORTS", "".join(report_card(r) for r in reports[:60]))
    replace_block(ROOT / "blogs.html", "HEADLINES", headlines_block(state))
    # Home page: a fresh AI report if one exists, otherwise today's headlines, otherwise the latest report.
    today = datetime.now(IST).strftime("%Y-%m-%d")
    if state.get("headlines") and not (reports[0]["kind"] == "daily" and reports[0]["date"] == today):
        latest = home_headlines_card(state)
    else:
        latest = report_card(reports[0])
    replace_block(ROOT / "index.html", "LATEST", latest)
    replace_block(ROOT / "results.html", "RESULTS", "".join(result_card(r) for r in state["results"]))
    replace_block(ROOT / "sitemap.xml", "SITEMAP", "".join(
        f"\n  <url><loc>{SITE}/{r['slug']}</loc><lastmod>{r['date']}</lastmod></url>" for r in reports))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--render", action="store_true", help="only rebuild pages from state.json")
    parser.add_argument("--force", action="store_true", help="regenerate today's report")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    state = load_state()
    if not args.render:
        now = datetime.now(IST)
        changed = refresh_headlines(state, now)
        changed = generate(state, now.strftime("%Y-%m-%d"), args.force) or changed
        if changed:
            save_state(state)
    render_site(state)
    log("Pages rendered.")


if __name__ == "__main__":
    sys.exit(main())
