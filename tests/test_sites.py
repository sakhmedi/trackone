"""
Tests for cross-document site deduplication (build_sites).

They run on ready-made JSON documents, without an OCR environment.
"""

import json

from main import build_sites, to_sites_markdown, _norm_site_name


def _coord(cid, name, lat_dms, lon_dms, valid=True, lat=48.05, lon=71.33):
    return {
        "id": cid, "name": name,
        "lat_dms": lat_dms, "lon_dms": lon_dms,
        "lat_decimal": lat, "lon_decimal": lon, "valid": valid,
    }


def _write(d, fn, report_id, source_file, coords):
    doc = {"report_id": report_id, "source_file": source_file, "coordinates": coords}
    (d / fn).write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")


def test_same_site_in_two_documents_is_deduped(tmp_path):
    жабай = _coord("2", "Жабай", "48°07'", "71°20'")
    _write(tmp_path, "a.json", "25834", "a.pdf",
           [жабай, _coord("1", "Актобе", "48°11'", "71°24'")])
    _write(tmp_path, "b.json", "30001", "b.pdf", [dict(жабай, id="5")])

    s = build_sites(str(tmp_path))
    # Жабай and Актобе -> 2 unique sites (Жабай was not duplicated)
    assert s["unique_sites"] == 2
    assert s["total_mentions"] == 3  # Актобе×1 + Жабай×2
    assert s["cross_document_sites"] == 1  # only Жабай is in 2 documents

    жабай_site = next(x for x in s["sites"] if x["name"] == "Жабай")
    assert жабай_site["in_documents"] == 2
    assert жабай_site["count"] == 2
    reports = {o["report_id"] for o in жабай_site["occurrences"]}
    assert reports == {"25834", "30001"}


def test_name_normalisation_merges_variants(tmp_path):
    # the same name in different spellings + the same coordinates -> one site
    _write(tmp_path, "a.json", "1", "a.pdf", [_coord("1", "Ю.Жуманай", "48°03'", "71°16'")])
    _write(tmp_path, "b.json", "2", "b.pdf", [_coord("1", "ю. жуманай", "48°03'", "71°16'")])

    s = build_sites(str(tmp_path))
    assert s["unique_sites"] == 1
    assert s["cross_document_sites"] == 1


def test_invalid_coordinates_are_ignored(tmp_path):
    _write(tmp_path, "a.json", "1", "a.pdf", [
        _coord("1", "Хорошая", "48°03'", "71°16'"),
        _coord("2", "Плохая", "99°99'", "00°00'", valid=False),
    ])
    s = build_sites(str(tmp_path))
    assert s["unique_sites"] == 1
    assert s["sites"][0]["name"] == "Хорошая"


def test_name_conflict_is_flagged_not_merged(tmp_path):
    # one name -> DIFFERENT coordinates in two documents: this is a conflict to review
    _write(tmp_path, "a.json", "1", "a.pdf", [_coord("1", "Тасты", "48°19'", "71°32'")])
    _write(tmp_path, "b.json", "2", "b.pdf", [_coord("1", "Тасты", "48°55'", "71°59'")])

    s = build_sites(str(tmp_path))
    assert s["unique_sites"] == 2            # different coordinates -> not collapsed
    assert len(s["name_conflicts"]) == 1
    conflict = s["name_conflicts"][0]
    assert conflict["name"] == "Тасты"
    assert len(conflict["variants"]) == 2


def test_norm_site_name():
    assert _norm_site_name("Ю.Жуманай") == _norm_site_name("ю. жуманай")
    assert _norm_site_name("  Тас-ты ") == "тасты"


def test_sites_markdown_renders(tmp_path):
    _write(tmp_path, "a.json", "25834", "a.pdf", [_coord("1", "Жабай", "48°07'", "71°20'")])
    md = to_sites_markdown(build_sites(str(tmp_path)))
    assert "# Участки" in md
    assert "Жабай" in md
