"""
Reliability test for the whole pipeline: a broken and an empty PDF must NOT crash
the run — they must end up in _errors.json, while the other artifacts (geojson,
summary) are still created.

This proves the scale robustness claimed in the README: one bad scan out of a
thousand does not bring down processing of the whole batch. The test does not
depend on OCR quality — all that matters is that the failure is isolated and
logged (it works both with poppler installed and absent — in both cases an
exception arises that the pipeline catches).
"""

import json
import sys

import main as main_mod


def test_corrupt_and_empty_pdf_are_logged_not_crashing(tmp_path):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    # deliberately unreadable "PDFs"
    (in_dir / "broken.pdf").write_bytes(b"%PDF-1.4 not actually a valid pdf body")
    (in_dir / "empty.pdf").write_bytes(b"")

    argv_backup = sys.argv
    sys.argv = ["main.py", "--input", str(in_dir), "--output", str(out_dir)]
    try:
        # the key point: the call must NOT raise an exception outward
        main_mod.main()
    finally:
        sys.argv = argv_backup

    # both failed files are logged, nothing is lost silently
    errlog = out_dir / "_errors.json"
    assert errlog.exists()
    logged = {e["file"] for e in json.loads(errlog.read_text(encoding="utf-8"))}
    assert "broken.pdf" in logged
    assert "empty.pdf" in logged

    # aggregate artifacts are still created (the run reached the end)
    assert (out_dir / "all_coordinates.geojson").exists()
    summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["documents"] == 0  # no valid documents, but the run completed
