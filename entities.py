"""
entities.py — extracts geological entities from the report text.

Track 1 requires finding: minerals, locations, chemical compositions.
For the hackathon we use a dictionary approach (keyword lists) + regex for metal
grades. This is simple, fast, and explainable to the judges.

It can later be improved with spaCy NER, but for a working prototype the
dictionary covers most cases in these reports.
"""

import re

from parse_catalog import dms_to_decimal

# Minerals/metals by word STEM: Russian text inflects them by grammatical case
# ("золота", "серебром", "медный"), so we search for the stem + any ending (\w*),
# not an exact match. The key is the canonical name for output, the value is the pattern.
MINERAL_PATTERNS = {
    "золото":   r"золот\w*",
    "серебро":  r"серебр\w*",
    "висмут":   r"висмут\w*",
    "медь":     r"\bмед(?:ь|и|н)\w*",
    "цинк":     r"цинк\w*",
    "свинец":   r"свин(?:ец|ц)\w*",
    "молибден": r"молибден\w*",
    "вольфрам": r"вольфрам\w*",
    "кобальт":  r"кобальт\w*",
    "ртуть":    r"ртут[ьи]\w*",
    "мышьяк":   r"мышья[кч]\w*",
    "уран":     r"\bуран\w*",
    "кварц":    r"кварц\w*",
    "пирит":    r"пирит\w*",
}
_MINERAL_COMPILED = {name: re.compile(p) for name, p in MINERAL_PATTERNS.items()}

# metal grade of the form "13,2 г/т", "23,9 г-т", "10 г/т".
# We require an actual slash (/ or -), not a dot: otherwise "1973 г. тонн"
# (where "г." = year) would falsely match as a grade. \b cuts off "г/тонну".
GRADE = re.compile(r"(\d+(?:[,.]\d+)?)\s*г\s*[/\-]\s*т\b")

# coordinates in text: "48°03' с.ш.", "71°16' в.д.", "105°20' в.д."
# Degrees 1–3 digits: latitude ≤90 (2 digits), but longitude can be 3-digit
# (>100° E) in eastern regions — an overly large value is cut off below by the
# range check (valid=false), not by silently skipping the row.
COORD_IN_TEXT = re.compile(
    r"(\d{1,3})\s*[°o]\s*(\d{2})['′]?\s*(с\.?ш\.?|в\.?д\.?)",
    re.IGNORECASE
)


def _looks_like_year(token):
    """True for a 4-digit number in the calendar-year range (1900–2099)."""
    return token.isdigit() and len(token) == 4 and 1900 <= int(token) <= 2099


def extract_entities(text):
    """Returns a dict of the entities found."""
    low = text.lower()

    found_minerals = sorted(
        name for name, rx in _MINERAL_COMPILED.items() if rx.search(low)
    )

    # Cut off values that look like a calendar year (an integer 1900–2099):
    # "1973 г-т" is a year, not a grade. Real grades usually have a comma
    # ("1,6") or are small, so the filter does not touch them.
    grades = [g for g in GRADE.findall(text) if not _looks_like_year(g)]

    # Coordinates mentioned in prose. As in the catalog, nothing is lost silently:
    # we check the range, compute decimal degrees, and mark implausible ones
    # "valid": false instead of quietly dropping them.
    coords = []
    for d, mins, kind in COORD_IN_TEXT.findall(text):
        deg, minute = int(d), int(mins)
        # latitude (с.ш.) <= 90°, longitude (в.д.) <= 180° — as in the catalog
        max_deg = 90 if kind.lower().startswith("с") else 180
        valid = 0 <= deg <= max_deg and 0 <= minute < 60
        entry = {
            "value": f"{deg}°{minute:02d}'",
            "type": kind,
            "valid": valid,
        }
        if valid:
            entry["decimal"] = dms_to_decimal(deg, minute)
        coords.append(entry)

    return {
        "minerals": found_minerals,
        "grades_g_per_t": grades,        # metal grades
        "coordinates_in_text": coords,   # coordinates mentioned in prose
    }


# a number next to a context word: "отчёт № 25834", "инв. 25834", "N 25834"
_REPORT_CONTEXT = re.compile(
    r"(?:отч[её]т|инв(?:\.|ентарн\w*)?|№|\bN\b)\D{0,6}(\d{4,6})",
    re.IGNORECASE,
)


def _pick_report_number(candidates):
    """
    From a list of 4–6-digit numbers, picks the most plausible report number:
    prefers non-years, and among them the longest (numbers are usually 5–6 digits).
    Returns a string or None.
    """
    if not candidates:
        return None
    non_years = [c for c in candidates if not _looks_like_year(c)]
    pool = non_years or candidates  # if only "years" remain, pick from them
    return max(pool, key=len)


def extract_report_id(filename, text):
    """
    Tries to find the report number (e.g. 25834). A length of 4–6 digits means we
    do not tie ourselves to one dataset's format and do not confuse the number
    with a year.

    Order: (1) a number next to a context word in the text ("отчёт № …");
    (2) the most plausible 4–6-digit number in the file name (not a year);
    (3) fallback — any 4–6-digit number in the text, so nothing is lost.
    """
    m = _REPORT_CONTEXT.search(text)
    if m:
        return m.group(1)

    picked = _pick_report_number(re.findall(r"\d{4,6}", filename))
    if picked:
        return picked

    m = re.search(r"\b(\d{4,6})\b", text)
    return m.group(1) if m else None
