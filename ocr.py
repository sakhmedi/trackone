"""
ocr.py — превращает страницы PDF в текст через Tesseract.

Почему так: сканы старые и выцветшие, поэтому перед OCR делаем предобработку:
  1) авто-поворот страницы (часть приложений отсканирована повёрнутой на 90°);
  2) перевод в оттенки серого + выравнивание контраста (autocontrast) — лечит
     неравномерное выцветание.

Важно: мы НЕ бинаризуем картинку сами (в чёрно-белое). На реальных сканах
этого отчёта собственная бинаризация Tesseract по серому изображению даёт
заметно больше распознанных строк, чем наш ручной порог (проверено: ~28 против
~7 строк каталога). Поэтому отдаём движку градации серого и доверяем бинаризацию ему.

Память: большой PDF (сотни страниц) не грузим в RAM целиком — рендерим
батчами по несколько страниц и освобождаем их после распознавания.

Надёжность: каждая страница в своём try/except — одна битая страница не
роняет весь документ, она помечается в тексте, остальные читаются.
"""

import os
import re

from pdf2image import convert_from_path, pdfinfo_from_path
import pytesseract
from PIL import ImageOps

# На Windows tesseract.exe часто не виден в PATH. Если задана переменная
# окружения TESSERACT_CMD — используем путь из неё. Иначе берём из PATH.
_TESSERACT_CMD = os.environ.get("TESSERACT_CMD")
if _TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = _TESSERACT_CMD


def preprocess(image):
    """
    Предобработка скана под OCR машинописи 1970-х:
    оттенки серого -> выравнивание контраста. Бинаризацию оставляем Tesseract.
    """
    gray = image.convert("L")                     # оттенки серого
    gray = ImageOps.autocontrast(gray, cutoff=2)  # растягиваем выцветший контраст
    return gray


def _auto_rotate(image):
    """
    Определяет ориентацию страницы через Tesseract OSD и доворачивает её.
    Нужно для приложений, отсканированных повёрнутыми на 90°.
    Если OSD недоступен или ошибся — возвращаем страницу как есть.
    """
    try:
        osd = pytesseract.image_to_osd(image)
        m = re.search(r"Rotate:\s*(\d+)", osd)
        angle = int(m.group(1)) if m else 0
        if angle:
            return image.rotate(-angle, expand=True)
    except Exception:
        pass
    return image


def _ocr_pages(pages, lang, collected, errors):
    """OCR списка страниц с изоляцией ошибок; дописывает в collected/errors."""
    for page in pages:
        try:
            prepared = preprocess(_auto_rotate(page))
            # --psm 6 = страница как единый блок текста, хорошо для таблиц
            text = pytesseract.image_to_string(prepared, lang=lang, config="--psm 6")
            collected.append(text)
        except Exception as e:
            errors[0] += 1
            collected.append(f"[OCR-ОШИБКА СТРАНИЦЫ: {e}]")


def pdf_to_text(pdf_path, lang="rus", dpi=300, batch_size=5):
    """
    Распознаёт весь PDF и возвращает текст всех страниц.

    lang="rus"      — русский языковой пакет Tesseract (обязателен для кириллицы).
    dpi=300         — разрешение рендера: выше = точнее, но медленнее.
    batch_size=5    — сколько страниц держать в памяти одновременно.
    """
    all_text = []
    errors = [0]  # счётчик сбойных страниц (список — чтобы менять внутри хелпера)

    # Узнаём число страниц, чтобы рендерить батчами и не держать всё в RAM.
    n_pages = None
    try:
        n_pages = pdfinfo_from_path(pdf_path)["Pages"]
    except Exception:
        n_pages = None

    if n_pages is None:
        # не смогли узнать число страниц — рендерим целиком (запасной путь)
        pages = convert_from_path(pdf_path, dpi=dpi)
        _ocr_pages(pages, lang, all_text, errors)
    else:
        for start in range(1, n_pages + 1, batch_size):
            end = min(start + batch_size - 1, n_pages)
            pages = convert_from_path(
                pdf_path, dpi=dpi, first_page=start, last_page=end
            )
            _ocr_pages(pages, lang, all_text, errors)
            del pages  # освобождаем память до следующего батча

    return "\n".join(all_text)
