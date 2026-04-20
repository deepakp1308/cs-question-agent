from pathlib import Path

from app.chapters import parse_selector_dir


def test_parse_selectors_from_headings(tmp_path: Path):
    (tmp_path / "selectors.md").write_text("# Computer Networks\n# Databases\n")
    specs = parse_selector_dir(tmp_path)
    ids = [s.chapter_id for s in specs]
    assert "ch_computer_networks" in ids
    assert "ch_databases" in ids


def test_parse_id_lines(tmp_path: Path):
    (tmp_path / "selectors.md").write_text("ch_networks: Computer Networks\nch_db: Databases\n")
    specs = parse_selector_dir(tmp_path)
    ids = [s.chapter_id for s in specs]
    assert "ch_networks" in ids and "ch_db" in ids
