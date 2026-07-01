"""
Tests for the coordinate catalog parser.

No Tesseract/Poppler required — they run on synthetic "OCR text", so the judges
can run them without an OCR environment:  python -m pytest tests/
"""

from parse_catalog import parse_catalog, dms_to_decimal, _clean_name, MIN_CATALOG_ROWS


# Clean catalog: 5 rows, format [number] [name] [lat deg min] [lon deg min]
CLEAN = """\
1. Ю.Жуманай      48 03      71 16
2  Жабай          48 07      71 20
3  Актобе         48 11      71 24
4  Карасу         48 15      71 28
5  Тасты          48 19      71 32
"""

# The same catalog with typical OCR substitutions of digits by similar letters:
# O→0, l→1, З→3, В→8, S→5, and junk at the start of the line.
NOISY = """\
; 1. Ю.Жуманай     4O O3      7l 16
| 2  Жабай         48 O7      71 2О
д 3  Актобе        4В 11      71 24
4  Карасу         48 1S      71 28
5  Тасты          48 19      7l 32
"""


def test_clean_catalog_parses_all_rows():
    rows = parse_catalog(CLEAN)
    assert len(rows) == 5
    assert all(r["valid"] for r in rows)


def test_decimal_conversion_is_correct():
    rows = parse_catalog(CLEAN)
    first = rows[0]
    # 48°03' -> 48 + 3/60 = 48.05 ; 71°16' -> 71 + 16/60 = 71.266667
    assert first["lat_decimal"] == 48.05
    assert first["lon_decimal"] == round(71 + 16 / 60.0, 6)


def test_ocr_letter_substitutions_are_normalised():
    rows = parse_catalog(NOISY)
    # all 5 rows should be recognized despite letters standing in for digits
    assert len(rows) == 5
    assert all(r["valid"] for r in rows)
    # '4O O3' -> 48? no: 4O=40, O3=03 -> 40.05
    assert rows[0]["lat_decimal"] == dms_to_decimal(40, 3)


def test_out_of_range_marked_invalid_not_dropped():
    # latitude 99° is out of range: the row must remain, but valid=false,
    # and the raw coordinates preserved for manual review.
    text = (
        CLEAN
        + "6  Бракованный   99 03      71 16\n"
    )
    rows = parse_catalog(text)
    bad = [r for r in rows if r["id"] == "6"]
    assert len(bad) == 1
    assert bad[0]["valid"] is False
    assert "lat_dms_raw" in bad[0]
    assert "warning" in bad[0]


def test_below_threshold_returns_empty():
    # fewer than MIN_CATALOG_ROWS valid rows -> this is not a catalog but prose noise.
    few = "\n".join(CLEAN.splitlines()[: MIN_CATALOG_ROWS - 1]) + "\n"
    assert parse_catalog(few) == []


def test_noise_without_real_names_is_filtered():
    # rows without a meaningful Cyrillic name must not pass
    junk = """\
1. xx 12 34 56 78
2. yy 12 34 56 78
3. zz 12 34 56 78
4. qq 12 34 56 78
"""
    assert parse_catalog(junk) == []


def test_clean_name_keeps_digit_inside_but_trims_tail():
    # a digit INSIDE the name must not truncate the name (weakness #3),
    # but trailing junk from the adjacent column is trimmed.
    assert _clean_name("Жум4най   48 03") == "Жум4най"
    assert _clean_name("Ю.Жуманай") == "Ю.Жуманай"
