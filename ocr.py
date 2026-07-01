"""
ocr.py — turns PDF pages into text via Tesseract.

Why this way: the scans are old and faded, so before OCR we preprocess:
  1) auto-rotate the page (some appendices are scanned rotated by 90°);
  2) grayscale conversion + contrast equalization (autocontrast) — this fixes
     uneven fading.

Important: we do NOT binarize the image ourselves (to black and white). On the
real scans of this report, Tesseract's own binarization of the grayscale image
yields noticeably more recognized lines than our manual threshold (verified:
~28 vs ~7 catalog rows). So we hand the engine grayscale and trust it to
binarize.

Memory: a large PDF (hundreds of pages) is not loaded into RAM in full — we
render it in batches of a few pages and free them after recognition.

Reliability: each page is in its own try/except — one broken page does not
bring down the whole document; it is flagged in the text and the rest are read.
"""

import os
import re

from pdf2image import convert_from_path, pdfinfo_from_path
import pytesseract
from PIL import ImageOps

# On Windows, tesseract.exe is often not visible on PATH. If the TESSERACT_CMD
# environment variable is set, use the path from it. Otherwise take it from PATH.
_TESSERACT_CMD = os.environ.get("TESSERACT_CMD")
if _TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = _TESSERACT_CMD


def preprocess(image):
    """
    Preprocess a scan for OCR of 1970s typescript:
    grayscale -> contrast equalization. Binarization is left to Tesseract.
    """
    gray = image.convert("L")                     # grayscale
    gray = ImageOps.autocontrast(gray, cutoff=2)  # stretch the faded contrast
    return gray


def _auto_rotate(image):
    """
    Detects the page orientation via Tesseract OSD and rotates it upright.
    Needed for appendices scanned rotated by 90°.
    If OSD is unavailable or wrong, return the page as is.
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


def _ocr_page(image, lang):
    """
    OCR of a single page in ONE image_to_data call: from it we collect both the
    text (preserving lines — needed for table parsing) and the engine confidence.
    Returns (text, list_of_word_confidences).
    """
    data = pytesseract.image_to_data(
        image, lang=lang, config="--psm 6",
        output_type=pytesseract.Output.DICT,
    )
    lines = {}
    confs = []
    for i, word in enumerate(data["text"]):
        if not word.strip():
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        lines.setdefault(key, []).append((data["word_num"][i], word))
        try:
            c = float(data["conf"][i])
            if c >= 0:                 # -1 = service elements, not text
                confs.append(c)
        except (ValueError, TypeError):
            pass
    text = "\n".join(
        " ".join(w for _, w in sorted(words)) for _, words in sorted(lines.items())
    )
    return text, confs


def _ocr_pages(pages, lang, collected, confs, errors):
    """OCR a list of pages with error isolation; accumulates text, confidences, failures."""
    for page in pages:
        try:
            text, page_confs = _ocr_page(preprocess(_auto_rotate(page)), lang)
            collected.append(text)
            confs.extend(page_confs)
        except Exception as e:
            errors[0] += 1
            collected.append(f"[OCR PAGE ERROR: {e}]")


def pdf_to_text(pdf_path, lang="rus", dpi=300, batch_size=5):
    """
    Recognizes the whole PDF. Returns a tuple (text, meta), where meta contains
    the mean OCR confidence, the page count, and the number of failed pages.

    lang="rus"      — Tesseract Russian language pack (required for Cyrillic).
    dpi=300         — render resolution: higher = more accurate but slower.
    batch_size=5    — how many pages to hold in memory at once.
    """
    all_text = []
    confs = []
    errors = [0]  # failed-page counter (a list so it can be mutated inside the helper)

    # Find out the page count so we can render in batches and not hold it all in RAM.
    try:
        n_pages = pdfinfo_from_path(pdf_path)["Pages"]
    except Exception:
        n_pages = None

    if n_pages is None:
        # could not determine the page count — render it whole (fallback path)
        pages = convert_from_path(pdf_path, dpi=dpi)
        _ocr_pages(pages, lang, all_text, confs, errors)
    else:
        for start in range(1, n_pages + 1, batch_size):
            end = min(start + batch_size - 1, n_pages)
            pages = convert_from_path(
                pdf_path, dpi=dpi, first_page=start, last_page=end
            )
            _ocr_pages(pages, lang, all_text, confs, errors)
            del pages  # free memory before the next batch

    meta = {
        "pages": n_pages if n_pages is not None else len(all_text),
        "failed_pages": errors[0],
        "mean_confidence": round(sum(confs) / len(confs), 1) if confs else 0.0,
    }
    return "\n".join(all_text), meta
