"""
Real astrological birth-chart (kundli) calculations using the Swiss Ephemeris
(pyswisseph) — the same astronomical calculation engine used by most
professional astrology software. Runs entirely locally, no API key needed,
no ongoing cost.

Uses the Moshier semi-analytical ephemeris (built into pyswisseph, no data
files to download) — accurate to a few arcseconds, more than enough for
astrology purposes.
"""

import datetime

import swisseph as swe
from timezonefinder import TimezoneFinder

try:
    from zoneinfo import ZoneInfo
except ImportError:  # Python <3.9 fallback
    from backports.zoneinfo import ZoneInfo

RASHIS = [
    "Mesh (Aries)", "Vrishabh (Taurus)", "Mithun (Gemini)", "Kark (Cancer)",
    "Simha (Leo)", "Kanya (Virgo)", "Tula (Libra)", "Vrishchik (Scorpio)",
    "Dhanu (Sagittarius)", "Makar (Capricorn)", "Kumbh (Aquarius)", "Meen (Pisces)",
]

NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni",
    "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha",
    "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha",
    "Purva Bhadrapada", "Uttara Bhadrapada", "Revati",
]

PLANETS = {
    "Sun": swe.SUN,
    "Moon": swe.MOON,
    "Mercury": swe.MERCURY,
    "Venus": swe.VENUS,
    "Mars": swe.MARS,
    "Jupiter": swe.JUPITER,
    "Saturn": swe.SATURN,
    "Rahu": swe.MEAN_NODE,  # Mean lunar node
}

_tf = TimezoneFinder()


def _rashi_for_longitude(longitude):
    return RASHIS[int(longitude // 30) % 12]


def _nakshatra_for_longitude(longitude):
    # Each nakshatra spans 13°20' (360/27 degrees)
    idx = int(longitude // (360 / 27)) % 27
    return NAKSHATRAS[idx]


def _geocode_place(place_name):
    """Free, keyless geocoding via OpenStreetMap Nominatim."""
    import requests

    resp = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": place_name, "format": "json", "limit": 1},
        headers={"User-Agent": "MyAgentKundliTool/1.0"},
        timeout=10,
    )
    resp.raise_for_status()
    results = resp.json()
    if not results:
        raise ValueError(f"Could not find location: {place_name}")
    return float(results[0]["lat"]), float(results[0]["lon"])


def calculate_kundli(birth_date: str, birth_time: str, birth_place: str) -> str:
    """
    birth_date: "YYYY-MM-DD"
    birth_time: "HH:MM" (24-hour, local time at birth_place)
    birth_place: free-text place name, e.g. "Mumbai, India"

    Returns a human-readable summary of real planetary positions at birth.
    """
    try:
        lat, lon = _geocode_place(birth_place)
    except Exception as exc:
        return f"Could not determine coordinates for '{birth_place}': {exc}"

    tz_name = _tf.timezone_at(lat=lat, lng=lon)
    if not tz_name:
        return f"Could not determine timezone for '{birth_place}'."

    try:
        y, m, d = (int(x) for x in birth_date.split("-"))
        hh, mm = (int(x) for x in birth_time.split(":"))
    except Exception:
        return "birth_date must be YYYY-MM-DD and birth_time must be HH:MM (24-hour)."

    local_dt = datetime.datetime(y, m, d, hh, mm, tzinfo=ZoneInfo(tz_name))
    utc_dt = local_dt.astimezone(datetime.timezone.utc)

    jd = swe.julday(
        utc_dt.year, utc_dt.month, utc_dt.day,
        utc_dt.hour + utc_dt.minute / 60.0,
    )

    # Use sidereal (Vedic/Lahiri) zodiac, standard for Indian astrology
    swe.set_sid_mode(swe.SIDM_LAHIRI)

    lines = [
        f"Birth details: {birth_date} {birth_time} ({tz_name}) at {birth_place} "
        f"(lat {lat:.2f}, lon {lon:.2f})",
        "",
        "Planetary positions (sidereal / Vedic):",
    ]

    for name, code in PLANETS.items():
        pos, _ = swe.calc_ut(jd, code, swe.FLG_SIDEREAL)
        longitude = pos[0]
        rashi = _rashi_for_longitude(longitude)
        nak = _nakshatra_for_longitude(longitude)
        lines.append(f"  - {name}: {rashi}, {nak} nakshatra ({longitude:.2f}°)")
        if name == "Rahu":
            ketu_long = (longitude + 180) % 360
            lines.append(
                f"  - Ketu: {_rashi_for_longitude(ketu_long)}, "
                f"{_nakshatra_for_longitude(ketu_long)} nakshatra ({ketu_long:.2f}°)"
            )

    # Ascendant (Lagna)
    cusps, ascmc = swe.houses_ex(jd, lat, lon, b"P", swe.FLG_SIDEREAL)
    asc_longitude = ascmc[0]
    lines.append("")
    lines.append(f"Ascendant (Lagna): {_rashi_for_longitude(asc_longitude)} ({asc_longitude:.2f}°)")
    lines.append(f"Moon sign (Rashi): {_rashi_for_longitude(swe.calc_ut(jd, swe.MOON, swe.FLG_SIDEREAL)[0][0])}")

    return "\n".join(lines)
