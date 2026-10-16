#!/usr/bin/env python3
"""Copy new episodes from the Muse RSS feed into this repo.

Reads the feed URL from the MUSE_FEED_URL environment variable (a GitHub secret).
For local testing, MUSE_FEED_FILE can point at a saved copy of the feed instead.

For each feed item not already in episodes.json (matched by guid or title):
  - downloads the MP3 into audio/
  - picks a show: a "News:" or "Learning:" title prefix wins; otherwise
    "briefing" or "news" in the title or description means LP News,
    and everything else goes to LP Learning
  - adds it to the top of episodes.json
Existing episodes get Muse's description and guid filled in if missing.
Uses only the Python standard library.
"""
import json, os, re, sys, unicodedata, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EPISODES = os.path.join(ROOT, "episodes.json")
AUDIO_DIR = os.path.join(ROOT, "audio")
LOCAL_TZ = ZoneInfo("America/Denver")
ITUNES = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"
NEWS_WORDS = re.compile(r"\b(briefing|news)\b", re.I)
PREFIX = re.compile(r"^\s*(news|learning)\s*[:\-–—]\s*", re.I)
UA = {"User-Agent": "LPs-Podcast-sync/1.0 (+https://podcast.lpworx.com)"}


def norm(t):
    t = unicodedata.normalize("NFKC", t or "").replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", t).strip().lower()


def slug(t):
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:90] or "episode"


def clean_desc(d):
    d = (d or "").strip()
    d = re.sub(r"\s*AI Generated\s*$", "", d).strip()
    return re.sub(r"\s*\n\s*", " ", d)


def duration(text):
    if not text:
        return 0
    parts = [int(float(p)) for p in text.strip().split(":") if p.strip()]
    secs = 0
    for p in parts:
        secs = secs * 60 + p
    return secs


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def load_feed():
    path = os.environ.get("MUSE_FEED_FILE")
    if path:
        with open(path, "rb") as f:
            return f.read()
    url = os.environ.get("MUSE_FEED_URL", "").strip()
    if not url:
        print("MUSE_FEED_URL is not set; nothing to do.")
        sys.exit(0)
    return fetch(url)


def write_episodes(data):
    txt = json.dumps(data, indent=2, ensure_ascii=False)
    # keep one show / one episode per line so the file stays easy to edit by hand
    txt = re.sub(r'\{\n\s+("(?:id|title)"[^{}]*?)\n\s+\}',
                 lambda m: "{ " + re.sub(r",\n\s+", ", ", m.group(1)) + " }", txt)
    with open(EPISODES, "w", encoding="utf-8") as f:
        f.write(txt + "\n")


def main():
    with open(EPISODES, encoding="utf-8") as f:
        data = json.load(f)
    eps = data["episodes"]
    show_ids = {s["id"] for s in data.get("shows", [])}
    by_guid = {e["guid"]: e for e in eps if e.get("guid")}
    by_title = {norm(e["title"]): e for e in eps}

    channel = ET.fromstring(load_feed()).find("channel")
    added, filled = [], 0
    for item in channel.findall("item"):
        raw_title = (item.findtext("title") or "").strip()
        guid = (item.findtext("guid") or "").strip()
        desc = clean_desc(item.findtext("description"))
        enc = item.find("enclosure")
        if not raw_title or enc is None or not enc.get("url"):
            continue

        m = PREFIX.match(raw_title)
        title = PREFIX.sub("", raw_title).strip() if m else raw_title
        existing = by_guid.get(guid) or by_title.get(norm(title)) or by_title.get(norm(raw_title))
        if existing:
            changed = False
            if desc and not existing.get("description"):
                existing["description"] = desc; changed = True
            if guid and not existing.get("guid"):
                existing["guid"] = guid; changed = True
            filled += changed
            continue

        if m:
            show = m.group(1).lower()
        else:
            show = "news" if NEWS_WORDS.search(title + " " + desc) else "learning"
        if show_ids and show not in show_ids:
            show = sorted(show_ids)[0]

        try:
            when = parsedate_to_datetime(item.findtext("pubDate")).astimezone(LOCAL_TZ)
        except Exception:
            when = datetime.now(LOCAL_TZ)
        date = when.strftime("%Y-%m-%d")

        ext = os.path.splitext(enc.get("url").split("?")[0])[1].lower() or ".mp3"
        name = f"{slug(title)}-{date}{ext}"
        dest = os.path.join(AUDIO_DIR, name)
        if not os.path.exists(dest):
            print(f"Downloading {title} ...")
            body = fetch(enc.get("url"))
            if len(body) < 1000:
                print(f"  skipped: download looked empty ({len(body)} bytes)")
                continue
            os.makedirs(AUDIO_DIR, exist_ok=True)
            with open(dest, "wb") as f:
                f.write(body)

        ep = {"title": title, "show": show, "date": date,
              "secs": duration(item.findtext(ITUNES + "duration")),
              "url": "audio/" + name, "description": desc, "guid": guid}
        added.append((when, ep))
        by_title[norm(title)] = ep
        if guid:
            by_guid[guid] = ep

    for _, ep in sorted(added, key=lambda x: x[0]):  # oldest first, so the newest ends on top
        eps.insert(0, ep)
    if added or filled:
        write_episodes(data)
    for _, ep in added:
        print(f"Added to {ep['show']}: {ep['title']}")
    print(f"{len(added)} new episode(s), {filled} existing episode(s) updated.")


if __name__ == "__main__":
    main()
