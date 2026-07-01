"""
Tests for entity extraction and the report number.

Plain text, no OCR dependencies:  python -m pytest tests/
"""

from entities import extract_entities, extract_report_id


def test_minerals_found_by_stem_across_cases():
    # Russian inflects minerals by grammatical case — we search by word stem
    text = "В пробах установлено золота и серебром, а также медный колчедан."
    minerals = extract_entities(text)["minerals"]
    assert "золото" in minerals
    assert "серебро" in minerals
    assert "медь" in minerals


def test_grades_extracted_but_year_filtered():
    text = "Содержание золота 13,2 г/т. Отчёт составлен в 1973 г-т назад."
    grades = extract_entities(text)["grades_g_per_t"]
    assert "13,2" in grades
    # "1973" looks like a year -> must not end up in the grades
    assert "1973" not in grades


def test_prose_coordinates_validated():
    text = "Участок расположен на 48°03' с.ш. и 71°16' в.д."
    coords = extract_entities(text)["coordinates_in_text"]
    assert len(coords) == 2
    assert all(c["valid"] for c in coords)
    lat = next(c for c in coords if "с" in c["type"])
    assert lat["decimal"] == round(48 + 3 / 60.0, 6)


def test_prose_coordinate_out_of_range_marked_invalid():
    # 99° of latitude is impossible -> valid=false, the coordinate is not lost
    text = "Ошибочно указано 99°03' с.ш."
    coords = extract_entities(text)["coordinates_in_text"]
    assert len(coords) == 1
    assert coords[0]["valid"] is False
    assert "decimal" not in coords[0]


def test_report_id_prefers_number_over_year_in_filename():
    # a file name with a year in front must not return the year instead of the report number
    assert extract_report_id("2024_otchet_25834.pdf", "") == "25834"


def test_report_id_from_context_in_text():
    assert extract_report_id("scan.pdf", "Геологический отчёт № 25834 за 1973 г.") == "25834"


def test_report_id_fallback_when_no_context():
    # no context word and no number in the name -> fallback to any 4-6-digit number
    assert extract_report_id("scan.pdf", "на листах описи 480015 приведены данные") == "480015"
