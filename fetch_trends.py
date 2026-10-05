"""Recoge tendencias de YouTube y Wikipedia (España) y las guarda en data.json."""
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

REGION = "ES"
HEADERS = {"User-Agent": "pulso-tendencias/1.0 (proyecto personal)"}


def get_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fmt(n):
    return f"{int(n):,}".replace(",", ".")


def youtube():
    key = os.environ.get("YOUTUBE_API_KEY")
    if not key:
        print("Falta YOUTUBE_API_KEY")
        return []
    params = urllib.parse.urlencode({
        "part": "snippet,statistics", "chart": "mostPopular",
        "regionCode": REGION, "maxResults": 15, "key": key,
    })
    data = get_json("https://www.googleapis.com/youtube/v3/videos?" + params)
    now = datetime.now(timezone.utc)
    out = []
    for v in data.get("items", []):
        published = datetime.fromisoformat(v["snippet"]["publishedAt"].replace("Z", "+00:00"))
        hours = max((now - published).total_seconds() / 3600, 1)
        views = int(v["statistics"].get("viewCount", 0))
        speed = views / hours
        out.append({
            "title": v["snippet"]["title"],
            "source": "yt",
            "meta": f'{v["snippet"]["channelTitle"]} - {fmt(views)} vistas',
            "label": f"{fmt(speed)} vistas/h",
            "metric": speed,
            "url": "https://www.youtube.com/watch?v=" + v["id"],
        })
    return out


def wiki_day(day):
    url = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/top/"
           f"es.wikipedia/all-access/{day:%Y/%m/%d}")
    articles = get_json(url)["items"][0]["articles"]
    return {a["article"]: a["views"] for a in articles}


def wikipedia():
    today = datetime.now(timezone.utc).date()
    new = wiki_day(today - timedelta(days=2))
    old = wiki_day(today - timedelta(days=3))
    floor = min(old.values())
    rows = []
    for name, views in new.items():
        if ":" in name or name == "Portada" or views < 5000:
            continue
        before = old.get(name, floor)
        growth = (views / before - 1) * 100
        if growth <= 0:
            continue
        rows.append({
            "title": name.replace("_", " "),
            "source": "wk",
            "meta": f"{fmt(views)} visitas en un día",
            "label": f"+{round(growth)} %",
            "metric": growth,
            "url": "https://es.wikipedia.org/wiki/" + urllib.parse.quote(name),
        })
    rows.sort(key=lambda r: r["metric"], reverse=True)
    return rows[:15]


def main():
    items = []
    for name, fn in (("YouTube", youtube), ("Wikipedia", wikipedia)):
        try:
            found = fn()
            print(f"{name}: {len(found)} tendencias")
            top = max((i["metric"] for i in found), default=0) or 1
            for i in found:
                i["heat"] = round(i.pop("metric") / top * 100)
            items += found
        except Exception as e:
            print(f"{name} ha fallado: {e}")
    if not items:
        raise SystemExit("No se ha conseguido ningún dato")
    items.sort(key=lambda i: i["heat"], reverse=True)
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump({"updated": datetime.now(timezone.utc).isoformat(), "items": items},
                  f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
