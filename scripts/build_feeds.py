#!/usr/bin/env python3
"""Build one podcast RSS feed per show (news.xml, learning.xml, ...) from episodes.json.

Subscribe to https://podcast.lpworx.com/<show id>.xml in any podcast app.
Runs automatically after the Muse sync and whenever episodes.json changes.
Uses only the Python standard library.
"""
import json, os, re
from datetime import datetime
from email.utils import format_datetime
from urllib.parse import quote
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://podcast.lpworx.com/"
TZ = ZoneInfo("America/Denver")
TYPES = {".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".ogg": "audio/ogg", ".opus": "audio/ogg", ".wav": "audio/wav", ".aac": "audio/aac"}


def x(s):
    return escape(str(s or ""), {'"': "&quot;"})


def abs_url(path):
    return BASE + quote(path.lstrip("/"))


def main():
    with open(os.path.join(ROOT, "episodes.json"), encoding="utf-8") as f:
        data = json.load(f)
    shows = data.get("shows") or [{"id": "main", "name": "LP's Podcast"}]
    for sh in shows:
        sid = sh["id"]
        eps = [e for e in data["episodes"] if e.get("show", shows[0]["id"]) == sid]
        cover = abs_url(f"cover-{sid}.png") if os.path.exists(os.path.join(ROOT, f"cover-{sid}.png")) else abs_url("icon-512.png")
        desc = sh.get("description") or f"{sh['name']}, from LPworx."
        items = []
        for i, e in enumerate(eps):
            path = os.path.join(ROOT, e["url"])
            size = os.path.getsize(path) if os.path.exists(path) else 0
            ext = os.path.splitext(e["url"])[1].lower()
            # noon local time; earlier items in the list sort as newer on the same day
            y, m, d = (int(p) for p in e["date"].split("-"))
            when = datetime(y, m, d, 12, 0, tzinfo=TZ).timestamp() - i * 60
            items.append(f"""    <item>
      <title>{x(e['title'])}</title>
      <description>{x(e.get('description') or e['title'])}</description>
      <enclosure url="{x(abs_url(e['url']))}" length="{size}" type="{TYPES.get(ext, 'audio/mpeg')}"/>
      <guid isPermaLink="false">{x(e.get('guid') or e['url'])}</guid>
      <pubDate>{format_datetime(datetime.fromtimestamp(when, TZ))}</pubDate>
      <itunes:duration>{int(e.get('secs') or 0)}</itunes:duration>
    </item>""")
        feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{x(sh['name'])}</title>
    <link>{BASE}#{sid}</link>
    <description>{x(desc)}</description>
    <language>en</language>
    <atom:link href="{BASE}{sid}.xml" rel="self" type="application/rss+xml"/>
    <itunes:author>LPworx</itunes:author>
    <itunes:image href="{cover}"/>
    <image><url>{cover}</url><title>{x(sh['name'])}</title><link>{BASE}</link></image>
    <itunes:category text="Technology"/>
    <itunes:explicit>false</itunes:explicit>
    <itunes:block>Yes</itunes:block>
{chr(10).join(items)}
  </channel>
</rss>
"""
        out = os.path.join(ROOT, f"{sid}.xml")
        old = open(out, encoding="utf-8").read() if os.path.exists(out) else None
        if old != feed:
            with open(out, "w", encoding="utf-8") as f:
                f.write(feed)
            print(f"Wrote {sid}.xml ({len(eps)} episodes)")


if __name__ == "__main__":
    main()
