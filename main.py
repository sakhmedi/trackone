"""
main.py — точка входа пайплайна Track 1.

Обходит ВСЕ pdf в папке input/, обрабатывает каждый, пишет JSON в output/.
Без хардкода имён файлов — масштабируется на любое число документов.
Каждый файл в try/except — один сбой не роняет весь прогон.

Запуск:
    python src/main.py
    python src/main.py --input my_scans --output my_results
"""

import argparse
import json
import os
import sys
import traceback
from datetime import datetime

# импорт наших модулей
from ocr import pdf_to_text
from parse_catalog import parse_catalog
from entities import extract_entities, extract_report_id


def process_one(pdf_path):
    """Обрабатывает один PDF, возвращает словарь с результатами."""
    filename = os.path.basename(pdf_path)
    text = pdf_to_text(pdf_path)

    return {
        "source_file": filename,
        "report_id": extract_report_id(filename, text),
        "processed_at": datetime.now().isoformat(timespec="seconds"),
        "coordinates": parse_catalog(text),
        "entities": extract_entities(text),
        "raw_text": text,
    }


def main():
    # пути задаются аргументами, по умолчанию — относительные папки.
    # это и есть "без хардкода": судьи укажут свои папки и всё заработает.
    parser = argparse.ArgumentParser(description="Track 1: OCR геологических отчётов")
    parser.add_argument("--input", default="input", help="папка с PDF")
    parser.add_argument("--output", default="output", help="папка для результатов")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    # находим все PDF в папке (рекурсивно)
    pdfs = []
    for root, _, files in os.walk(args.input):
        for f in files:
            if f.lower().endswith(".pdf"):
                pdfs.append(os.path.join(root, f))

    if not pdfs:
        print(f"В папке '{args.input}' не найдено PDF-файлов.")
        sys.exit(1)

    print(f"Найдено файлов: {len(pdfs)}")

    error_log = []
    ok = 0

    for i, pdf_path in enumerate(pdfs, 1):
        name = os.path.basename(pdf_path)
        print(f"[{i}/{len(pdfs)}] {name} ... ", end="", flush=True)
        try:
            result = process_one(pdf_path)
            out_name = os.path.splitext(name)[0] + ".json"
            out_path = os.path.join(args.output, out_name)
            with open(out_path, "w", encoding="utf-8") as fh:
                json.dump(result, fh, ensure_ascii=False, indent=2)
            n_coords = len(result["coordinates"])
            print(f"ок (координат: {n_coords})")
            ok += 1
        except Exception as e:
            # ничего не теряем молча: пишем в лог и идём дальше
            print("ОШИБКА")
            error_log.append({
                "file": name,
                "error": str(e),
                "trace": traceback.format_exc(),
            })

    # сохраняем лог ошибок — это требование критериев (надёжность)
    if error_log:
        log_path = os.path.join(args.output, "_errors.json")
        with open(log_path, "w", encoding="utf-8") as fh:
            json.dump(error_log, fh, ensure_ascii=False, indent=2)

    print("-" * 50)
    print(f"Готово. Успешно: {ok}/{len(pdfs)}. Ошибок: {len(error_log)}.")
    if error_log:
        print(f"Подробности ошибок: {os.path.join(args.output, '_errors.json')}")


if __name__ == "__main__":
    main()
