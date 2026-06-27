"""
Тесты парсера каталога координат.

Не требуют Tesseract/Poppler — работают на синтетическом «OCR-тексте»,
поэтому судьи могут запустить их без OCR-окружения:  python -m pytest tests/
"""

from parse_catalog import parse_catalog, dms_to_decimal, _clean_name, MIN_CATALOG_ROWS


# Чистый каталог: 5 строк, формат [номер] [название] [широта гр мин] [долгота гр мин]
CLEAN = """\
1. Ю.Жуманай      48 03      71 16
2  Жабай          48 07      71 20
3  Актобе         48 11      71 24
4  Карасу         48 15      71 28
5  Тасты          48 19      71 32
"""

# Тот же каталог с типичными OCR-подменами цифр на похожие буквы:
# O→0, l→1, З→3, В→8, S→5, и мусор в начале строки.
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
    # все 5 строк должны распознаться несмотря на буквы вместо цифр
    assert len(rows) == 5
    assert all(r["valid"] for r in rows)
    # '4O O3' -> 48? нет: 4O=40, O3=03 -> 40.05
    assert rows[0]["lat_decimal"] == dms_to_decimal(40, 3)


def test_out_of_range_marked_invalid_not_dropped():
    # широта 99° вне диапазона: строка должна остаться, но valid=false,
    # а сырые координаты сохранены для ручной проверки.
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
    # меньше MIN_CATALOG_ROWS валидных строк -> это не каталог, а шум прозы.
    few = "\n".join(CLEAN.splitlines()[: MIN_CATALOG_ROWS - 1]) + "\n"
    assert parse_catalog(few) == []


def test_noise_without_real_names_is_filtered():
    # строки без осмысленного кириллического названия не должны проходить
    junk = """\
1. xx 12 34 56 78
2. yy 12 34 56 78
3. zz 12 34 56 78
4. qq 12 34 56 78
"""
    assert parse_catalog(junk) == []


def test_clean_name_keeps_digit_inside_but_trims_tail():
    # цифра ВНУТРИ названия не должна обрезать имя (weakness #3),
    # но хвостовой мусор от соседней колонки срезается.
    assert _clean_name("Жум4най   48 03") == "Жум4най"
    assert _clean_name("Ю.Жуманай") == "Ю.Жуманай"
