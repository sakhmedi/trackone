"""
Тест надёжности всего пайплайна: битый и пустой PDF НЕ должны ронять прогон —
они обязаны попасть в _errors.json, а остальные артефакты (geojson, summary)
всё равно создаться.

Это доказывает заявленную в README устойчивость на масштабе: один плохой скан из
тысячи не обрушивает обработку всей пачки. Тест не зависит от качества OCR —
важно лишь, что сбой изолирован и залогирован (он отработает и при установленном,
и при отсутствующем poppler — в обоих случаях возникает исключение, которое
пайплайн ловит).
"""

import json
import sys

import main as main_mod


def test_corrupt_and_empty_pdf_are_logged_not_crashing(tmp_path):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    # заведомо нечитаемые «PDF»
    (in_dir / "broken.pdf").write_bytes(b"%PDF-1.4 not actually a valid pdf body")
    (in_dir / "empty.pdf").write_bytes(b"")

    argv_backup = sys.argv
    sys.argv = ["main.py", "--input", str(in_dir), "--output", str(out_dir)]
    try:
        # ключевое: вызов НЕ должен бросить исключение наружу
        main_mod.main()
    finally:
        sys.argv = argv_backup

    # оба сбойных файла залогированы, ничего не потеряно молча
    errlog = out_dir / "_errors.json"
    assert errlog.exists()
    logged = {e["file"] for e in json.loads(errlog.read_text(encoding="utf-8"))}
    assert "broken.pdf" in logged
    assert "empty.pdf" in logged

    # сводные артефакты всё равно создаются (прогон дошёл до конца)
    assert (out_dir / "all_coordinates.geojson").exists()
    summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["documents"] == 0  # валидных документов нет, но прогон завершён
