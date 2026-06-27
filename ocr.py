"""
ocr.py — превращает страницы PDF в текст через Tesseract.

Почему так: сканы старые и выцветшие, поэтому перед OCR делаем
предобработку (серый цвет + увеличение контраста). Это заметно
повышает точность на машинописи 1970-х.
"""

from pdf2image import convert_from_path
import pytesseract
from PIL import Image


def preprocess(image):
    """
    Лёгкая предобработка скана для лучшего OCR.
    Серый цвет + бинаризация по простому порогу.
    Для большинства машинописных сканов этого достаточно.
    """
    gray = image.convert("L")  # в оттенки серого
    # порог: всё темнее 140 -> чёрное, светлее -> белое
    bw = gray.point(lambda x: 0 if x < 140 else 255, "1")
    return bw


def pdf_to_text(pdf_path, lang="rus", dpi=300):
    """
    Распознаёт весь PDF и возвращает текст всех страниц.

    lang="rus" — русский языковой пакет Tesseract (обязателен для кириллицы).
    dpi=300 — разрешение рендера; выше = точнее, но медленнее.
    """
    pages = convert_from_path(pdf_path, dpi=dpi)
    all_text = []
    for i, page in enumerate(pages):
        processed = preprocess(page)
        # --psm 6 = считать страницу единым блоком текста, хорошо для таблиц
        text = pytesseract.image_to_string(processed, lang=lang, config="--psm 6")
        all_text.append(text)
    return "\n".join(all_text)
