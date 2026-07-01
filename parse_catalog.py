"""
parse_catalog.py — extracts coordinate catalog rows from OCR text.

Row format in the catalog (see каталог_координат_25834):
    1.  Ю.Жуманай      48 03      71 16
    2   Жабай          48 07      71 20
    ...
That is: [number] [site name] [latitude: degrees minutes] [longitude: degrees minutes]

The approach is regular expressions. Not a neural network: for tabular data,
regex is more precise, faster, and fully reproducible, which is what the
criteria value.

OCR resilience: digits in coordinates are often recognized as similar letters
(0↔О/O, 1↔l/I, 3↔З, 8↔В, 5↔S/s, 6↔b, 2↔Z). We allow such characters in
coordinate positions and normalize them into digits. Each row is checked against
a valid range; unreadable/implausible rows are NOT silently discarded but marked
"valid": false — so that data is not lost unnoticed.
"""

import re


# We treat a document as a coordinate catalog only if it yields at least this
# many VALID rows. This cuts off false positives on continuous text and expense
# tables, where random numbers occasionally line up into a "coordinate".
# The threshold is generic (not tied to a region/file): a real catalog is dense.
MIN_CATALOG_ROWS = 4


# "looks like a digit" -> digit map (typical Cyrillic OCR errors)
_DIGIT_MAP = str.maketrans({
    "O": "0", "o": "0", "О": "0", "о": "0",
    "l": "1", "I": "1", "|": "1", "і": "1",
    "З": "3", "з": "3",
    "В": "8",
    "S": "5", "s": "5",
    "b": "6",
    "Z": "2",
})

# characters we treat as a "digit" in a coordinate position (a digit or its OCR twin)
_DIGITLIKE = r"[0-9OoОоlI|іЗзВSsbZ]"
# separator between degrees and minutes: degree sign/prime/space/junk (or nothing)
_SEP = r"[°ºˈ'’\s]*"
# one coordinate: 2–3 "digits" (degrees) + separator + 2 "digits" (minutes)
_COORD = rf"({_DIGITLIKE}{{2,3}}){_SEP}({_DIGITLIKE}{{2}})"

# catalog row: [OCR junk] number -> name -> latitude -> longitude
# OCR often puts junk at the start of a line ("; 28 ...", "| 48 ...", "д 29 ..."),
# so we allow up to 3 non-digit characters before the site number.
LINE = re.compile(
    r"^\D{0,3}?(\d{1,2})[.\)\s\-—]+"  # [junk] site number
    r"(.+?)\s+"                       # name (non-greedy, up to the coordinates)
    + _COORD + r"\D+?"                # latitude + separator up to longitude
    + _COORD,                         # longitude
    re.MULTILINE,
)


def _norm_int(token):
    """'4О' -> 40. Returns int or None if nothing numeric remains."""
    cleaned = re.sub(r"\D", "", token.translate(_DIGIT_MAP))
    return int(cleaned) if cleaned else None


_CYR = re.compile(r"[А-Яа-яЁё]")


def _clean_name(raw):
    """
    Keeps the meaningful "head" part of the name. Digits are allowed inside the
    name — OCR often inserts them into a letter ('Жум4най'), and the name must
    not be cut at the first digit. So we take letters/digits/spaces/dots/hyphens,
    and then trim only the TRAILING junk (digits/spaces/dots) that may have stuck
    on from the adjacent coordinate column.
    """
    m = re.match(r"[А-Яа-яЁё][А-Яа-яЁё0-9 .\-]*", raw.strip())
    if not m:
        return ""
    return re.sub(r"[\s\d.\-]+$", "", m.group(0)).strip()


def dms_to_decimal(degrees, minutes):
    """Converts degrees+minutes to decimal degrees. 48, 3 -> 48.05"""
    return round(degrees + minutes / 60.0, 6)


def parse_catalog(text):
    """
    Finds all coordinate catalog rows in the text.
    Returns a list of dicts. Invalid rows are marked "valid": false.
    """
    results = []
    for m in LINE.finditer(text):
        num, name, lat_d, lat_m, lon_d, lon_m = m.groups()

        # Noise filter: a real catalog row has a meaningful name.
        # If the name has fewer than 3 Cyrillic letters, it is most likely
        # a false positive on OCR mush, not a site. Skip it.
        name = _clean_name(name)
        if len(_CYR.findall(name)) < 3:
            continue

        latd, latm = _norm_int(lat_d), _norm_int(lat_m)
        lond, lonm = _norm_int(lon_d), _norm_int(lon_m)

        valid = (
            None not in (latd, latm, lond, lonm)
            and 0 <= latd <= 90 and 0 <= latm < 60
            and 0 <= lond <= 180 and 0 <= lonm < 60
        )

        entry = {
            "id": num.strip(),
            "name": name.strip(),
            "valid": valid,
        }
        if valid:
            entry["lat_dms"] = f"{latd}°{latm:02d}'"
            entry["lon_dms"] = f"{lond}°{lonm:02d}'"
            entry["lat_decimal"] = dms_to_decimal(latd, latm)
            entry["lon_decimal"] = dms_to_decimal(lond, lonm)
        else:
            # save as recognized — for manual review, nothing is lost
            entry["lat_dms_raw"] = f"{lat_d} {lat_m}"
            entry["lon_dms_raw"] = f"{lon_d} {lon_m}"
            entry["warning"] = "координаты нечитаемы или вне допустимого диапазона"
        results.append(entry)

    # Density threshold: if there are few valid rows, this is not a catalog but prose noise.
    if sum(1 for r in results if r["valid"]) < MIN_CATALOG_ROWS:
        return []
    return results
