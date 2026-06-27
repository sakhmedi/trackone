"""
Тесты сводки по корпусу (build_summary / to_summary_markdown).

Работают на готовых JSON-файлах, без OCR-окружения.
"""

import json

from main import build_summary, to_summary_markdown


def _write_doc(d, name, **kw):
    """Кладёт минимальный документ-JSON в каталог d."""
    doc = {
        "report_id": kw.get("report_id"),
        "ocr": {"needs_review": kw.get("needs_review", False)},
        "coordinates": kw.get("coordinates", []),
        "entities": {"minerals": kw.get("minerals", [])},
    }
    (d / name).write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")


def test_summary_aggregates_corpus(tmp_path):
    _write_doc(
        tmp_path, "a.json",
        report_id="25834", needs_review=True,
        minerals=["золото", "серебро"],
        coordinates=[{"valid": True}, {"valid": True}, {"valid": False}],
    )
    _write_doc(
        tmp_path, "b.json",
        report_id="25834", needs_review=False,
        minerals=["золото", "медь"],
        coordinates=[{"valid": True}],
    )

    s = build_summary(str(tmp_path))
    assert s["documents"] == 2
    assert s["needs_review"] == 1
    assert s["report_ids"] == ["25834"]          # дедуп номеров отчётов
    assert s["total_valid_coordinates"] == 3     # 2 + 1, невалидные не считаются
    # золото в обоих документах -> 2; serebro/med -> по 1; сортировка по частоте
    assert s["minerals"]["золото"] == 2
    assert s["minerals"]["серебро"] == 1
    assert list(s["minerals"])[0] == "золото"


def test_summary_ignores_aggregate_and_error_files(tmp_path):
    _write_doc(tmp_path, "doc.json", report_id="1", minerals=["золото"],
               coordinates=[{"valid": True}])
    # эти файлы не документы — их нельзя считать как документы корпуса
    (tmp_path / "_errors.json").write_text("[]", encoding="utf-8")
    (tmp_path / "summary.json").write_text("{}", encoding="utf-8")
    (tmp_path / "all_coordinates.geojson").write_text("{}", encoding="utf-8")

    s = build_summary(str(tmp_path))
    assert s["documents"] == 1


def test_summary_markdown_renders(tmp_path):
    _write_doc(tmp_path, "a.json", report_id="25834", minerals=["золото"],
               coordinates=[{"valid": True}])
    md = to_summary_markdown(build_summary(str(tmp_path)))
    assert "# Сводка по корпусу" in md
    assert "золото" in md
    assert "25834" in md
