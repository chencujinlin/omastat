#!/usr/bin/env python3
"""Current weather using the same source as Omarchy's status-bar weather.

The bar stores its location in
~/.local/state/omarchy/settings/weather.json (name and optional coordinates)
and reads wttr.in. This helper reads that same location and the same wttr.in
j1 response, then emits one compact JSON object for the omastat weather strip.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import urllib.parse
import urllib.request

WTTR_URL = "https://wttr.in/"
CONDITION_ZH = {
    113: "晴", 116: "多云", 119: "阴", 122: "阴",
    143: "雾", 248: "雾", 260: "雾",
    176: "局部有雨", 263: "毛毛雨", 266: "小雨", 293: "小雨",
    296: "小雨", 299: "中雨", 302: "中雨", 305: "大雨", 308: "大雨",
    353: "小雨", 356: "中雨", 359: "大雨",
    200: "雷雨", 386: "雷雨", 389: "雷雨", 392: "雷雨", 395: "雷雨",
    179: "雪", 227: "雪", 230: "雪", 323: "小雪", 326: "小雪",
    329: "中雪", 332: "中雪", 335: "大雪", 338: "大雪", 368: "小雪", 371: "大雪",
    182: "雨夹雪", 185: "雨夹雪", 281: "冻雨", 284: "冻雨",
    311: "冻雨", 314: "冻雨", 317: "雨夹雪", 320: "雨夹雪",
    350: "冰雹", 362: "雨夹雪", 365: "雨夹雪", 374: "冰雹", 377: "冰雹",
}
WIND_ZH = {
    "N": "北风", "NNE": "东北风", "NE": "东北风", "ENE": "东北风",
    "E": "东风", "ESE": "东南风", "SE": "东南风", "SSE": "东南风",
    "S": "南风", "SSW": "西南风", "SW": "西南风", "WSW": "西南风",
    "W": "西风", "WNW": "西北风", "NW": "西北风", "NNW": "西北风",
}

# Nerd Font weather glyphs used by the Omarchy weather icon helper.
DAY_ICON = {
    113: 0xE30D, 116: 0xE302, 119: 0xE33D, 122: 0xE33D,
    143: 0xE313, 248: 0xE313, 260: 0xE313,
    176: 0xE308, 263: 0xE308, 353: 0xE308,
    179: 0xE30A, 227: 0xE30A, 230: 0xE30A, 323: 0xE30A, 326: 0xE30A, 368: 0xE30A,
    182: 0xE3AD, 185: 0xE3AD, 281: 0xE3AD, 284: 0xE3AD,
    311: 0xE3AD, 314: 0xE3AD, 317: 0xE3AD, 320: 0xE3AD,
    200: 0xE31D, 386: 0xE31D, 389: 0xE31D, 392: 0xE31D, 395: 0xE31D,
    266: 0xE318, 293: 0xE318, 296: 0xE318, 299: 0xE318, 302: 0xE318,
    305: 0xE318, 308: 0xE318, 356: 0xE318, 359: 0xE318,
    329: 0xE31A, 332: 0xE31A, 335: 0xE31A, 338: 0xE31A, 371: 0xE31A,
    350: 0xE3AD, 362: 0xE3AD, 365: 0xE3AD, 374: 0xE3AD, 377: 0xE3AD,
}
NIGHT_ICON = {
    113: 0xE32B, 116: 0xE32E, 176: 0xE333, 263: 0xE333, 353: 0xE333,
    179: 0xE327, 227: 0xE327, 230: 0xE327, 323: 0xE327, 326: 0xE327, 368: 0xE327,
}


def integer(value):
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def read_location(home):
    path = Path(home) / ".local/state/omarchy/settings/weather.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return {"name": "", "latitude": None, "longitude": None}
    if not isinstance(data, dict):
        return {"name": "", "latitude": None, "longitude": None}
    name = data.get("name") if isinstance(data.get("name"), str) else ""
    try:
        latitude = float(data.get("latitude"))
        longitude = float(data.get("longitude"))
    except (TypeError, ValueError):
        latitude = longitude = None
    if latitude is None or longitude is None:
        return {"name": name.strip(), "latitude": None, "longitude": None}
    return {"name": name.strip(), "latitude": latitude, "longitude": longitude}


def location_query(location):
    if location["latitude"] is not None and location["longitude"] is not None:
        return str(location["latitude"]) + "," + str(location["longitude"])
    if location["name"]:
        return urllib.parse.quote(location["name"], safe="")
    return ""


def is_night(astronomy):
    sunrise = str(astronomy.get("sunrise") or "")
    sunset = str(astronomy.get("sunset") or "")
    try:
        rise = dt.datetime.strptime(sunrise, "%I:%M %p").time()
        setting = dt.datetime.strptime(sunset, "%I:%M %p").time()
    except ValueError:
        return False
    now = dt.datetime.now().time()
    return now < rise or now >= setting


def weather_icon(code, night):
    if night and code in NIGHT_ICON:
        return chr(NIGHT_ICON[code])
    return chr(DAY_ICON.get(code, 0xE33D))


def parse_weather(payload, configured_name):
    if not isinstance(payload, dict):
        raise ValueError("invalid weather response")
    current = payload.get("current_condition")
    days = payload.get("weather")
    if not isinstance(current, list) or not current or not isinstance(days, list) or not days:
        raise ValueError("weather response incomplete")
    condition_data = current[0]
    today = days[0]
    area = (payload.get("nearest_area") or [{}])[0]
    area_name = ""
    region = ""
    country = ""
    if isinstance(area, dict):
        for key, target in (("areaName", "area_name"), ("region", "region"), ("country", "country")):
            values = area.get(key)
            if isinstance(values, list) and values and isinstance(values[0], dict):
                value = values[0].get("value")
                if isinstance(value, str):
                    if target == "area_name":
                        area_name = value.strip()
                    elif target == "region":
                        region = value.strip()
                    else:
                        country = value.strip()
    location = configured_name or region or area_name or "本地"
    if location.isascii():
        location = location.title()
    code = integer(condition_data.get("weatherCode")) or 0
    astronomy = (today.get("astronomy") or [{}])[0]
    night = is_night(astronomy if isinstance(astronomy, dict) else {})
    description = ""
    descs = condition_data.get("weatherDesc")
    if isinstance(descs, list) and descs and isinstance(descs[0], dict):
        description = str(descs[0].get("value") or "").strip()
    condition = CONDITION_ZH.get(code, description or "未知")
    wind_dir = str(condition_data.get("winddir16Point") or "")
    return {
        "state": "ok",
        "location": location,
        "area": area_name,
        "region": region,
        "country": country,
        "temperature": integer(condition_data.get("temp_C")),
        "feelsLike": integer(condition_data.get("FeelsLikeC")),
        "condition": condition,
        "description": description,
        "humidity": integer(condition_data.get("humidity")),
        "windKmph": integer(condition_data.get("windspeedKmph")),
        "windDir": wind_dir,
        "windDirZh": WIND_ZH.get(wind_dir, wind_dir),
        "high": integer(today.get("maxtempC")),
        "low": integer(today.get("mintempC")),
        "icon": weather_icon(code, night),
        "isDay": not night,
        "updated": str(condition_data.get("observation_time") or ""),
        "fetchedAtMs": int(dt.datetime.now().timestamp() * 1000),
    }


def fetch_weather(query, timeout):
    url = WTTR_URL + ("?" if not query else query + "?") + "format=j1"
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "omastat/1.0", "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError("weather HTTP " + str(response.status))
        return json.loads(response.read().decode("utf-8", "replace"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--timeout", type=float, default=10)
    args = parser.parse_args()
    if os.environ.get("OMASTAT_NO_COLLECT") == "1":
        print(json.dumps({"state": "disabled"}, ensure_ascii=False))
        return 0
    location = read_location(args.home)
    try:
        payload = fetch_weather(location_query(location), max(3.0, args.timeout))
        data = parse_weather(payload, location["name"])
    except Exception as error:
        print(json.dumps({"state": "error", "message": type(error).__name__}, ensure_ascii=False))
        return 1
    print(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
