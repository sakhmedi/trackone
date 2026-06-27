"""
Тесты извлечения сущностей и номера отчёта.

Чистый текст, без OCR-зависимостей:  python -m pytest tests/
"""

from entities import extract_entities, extract_report_id


def test_minerals_found_by_stem_across_cases():
    # русский склоняет минералы по падежам — ищем по основе слова
    text = "В пробах установлено золота и серебром, а также медный колчедан."
    minerals = extract_entities(text)["minerals"]
    assert "золото" in minerals
    assert "серебро" in minerals
    assert "медь" in minerals


def test_grades_extracted_but_year_filtered():
    text = "Содержание золота 13,2 г/т. Отчёт составлен в 1973 г-т назад."
    grades = extract_entities(text)["grades_g_per_t"]
    assert "13,2" in grades
    # "1973" выглядит как год -> не должно попасть в содержания
    assert "1973" not in grades


def test_prose_coordinates_validated():
    text = "Участок расположен на 48°03' с.ш. и 71°16' в.д."
    coords = extract_entities(text)["coordinates_in_text"]
    assert len(coords) == 2
    assert all(c["valid"] for c in coords)
    lat = next(c for c in coords if "с" in c["type"])
    assert lat["decimal"] == round(48 + 3 / 60.0, 6)


def test_prose_coordinate_out_of_range_marked_invalid():
    # 99° широты невозможны -> valid=false, координата не теряется
    text = "Ошибочно указано 99°03' с.ш."
    coords = extract_entities(text)["coordinates_in_text"]
    assert len(coords) == 1
    assert coords[0]["valid"] is False
    assert "decimal" not in coords[0]


def test_report_id_prefers_number_over_year_in_filename():
    # имя с годом впереди не должно отдавать год вместо номера отчёта
    assert extract_report_id("2024_otchet_25834.pdf", "") == "25834"


def test_report_id_from_context_in_text():
    assert extract_report_id("scan.pdf", "Геологический отчёт № 25834 за 1973 г.") == "25834"


def test_report_id_fallback_when_no_context():
    # нет контекста-слова и номера в имени -> фоллбэк на любое 4-6-значное число
    assert extract_report_id("scan.pdf", "на листах описи 480015 приведены данные") == "480015"
