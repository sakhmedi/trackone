"""
entities.py — извлекает геологические сущности из текста отчёта.

Track 1 требует находить: минералы, местонахождения, химические составы.
Для хакатона используем словарный подход (списки ключевых слов) + regex
для содержаний металлов. Это просто, быстро и объяснимо судьям.

Можно потом улучшить через spaCy NER, но для рабочего прототипа
словарь покрывает большинство случаев в этих отчётах.
"""

import re

# минералы и металлы, встречающиеся в советских отчётах по золоту
MINERALS = [
    "золото", "серебро", "висмут", "медь", "цинк", "свинец",
    "молибден", "вольфрам", "кобальт", "ртуть", "мышьяк",
    "уран", "кварц", "пирит",
]

# содержание металла вида "13,2 г-т", "23,9 г/т", "10 г-т"
GRADE = re.compile(r"(\d+[,.]?\d*)\s*г[-/]?т")

# координаты в тексте: "48°03' с.ш.", "71°16' в.д."
COORD_IN_TEXT = re.compile(
    r"(\d{1,2})\s*[°o]\s*(\d{2})['′]?\s*(с\.?ш\.?|в\.?д\.?)",
    re.IGNORECASE
)


def extract_entities(text):
    """Возвращает словарь найденных сущностей."""
    low = text.lower()

    found_minerals = sorted({m for m in MINERALS if m in low})

    grades = GRADE.findall(text)

    coords = []
    for d, mins, kind in COORD_IN_TEXT.findall(text):
        coords.append({"value": f"{d}°{mins}'", "type": kind})

    return {
        "minerals": found_minerals,
        "grades_g_per_t": grades,        # содержания металлов
        "coordinates_in_text": coords,   # координаты, упомянутые в прозе
    }


def extract_report_id(filename, text):
    """
    Пытается найти номер отчёта (например 25834).
    Сначала в имени файла, потом в тексте.
    """
    m = re.search(r"(\d{5})", filename)
    if m:
        return m.group(1)
    m = re.search(r"\b(\d{5})\b", text)
    return m.group(1) if m else None
