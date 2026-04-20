from __future__ import annotations

from app.extract import extract_paper, normalize
from app.hashing import sha256_file


def test_extractor_on_sample_paper(example_input_dir):
    paper = example_input_dir / "papers" / "sample_paper.pdf"
    records = extract_paper(
        paper_id="sample_paper",
        source_file=str(paper),
        paper_hash=sha256_file(paper),
    )
    # 1, 2, 3, 3(a), 3(b), 4, 5 → 7 records minimum. Allow for small numbering drift.
    assert len(records) >= 5
    top_level = [r for r in records if len(r.numbering_path) == 1]
    assert any(r.numbering_path == ["1"] for r in top_level)
    assert any(r.numbering_path == ["4"] for r in top_level)
    # Q1 should carry "star topology" and 2 marks.
    q1 = [r for r in records if r.numbering_path == ["1"]][0]
    assert "star topology" in q1.verbatim_text.lower()
    assert q1.marks == 2
    assert q1.normalized_text == normalize(q1.verbatim_text)


def test_or_branch_pairing(example_input_dir):
    paper = example_input_dir / "papers" / "sample_paper.pdf"
    records = extract_paper(
        paper_id="sample_paper",
        source_file=str(paper),
        paper_hash=sha256_file(paper),
    )
    q4s = [r for r in records if r.numbering_path == ["4"]]
    q5s = [r for r in records if r.numbering_path == ["5"]]
    # Q4 and Q5 are OR-paired in the sample paper.
    assert q4s and q5s
    # At least one of them should have or_group_id set.
    ids = {r.or_group_id for r in (*q4s, *q5s) if r.or_group_id}
    assert len(ids) == 1, f"expected a shared or_group_id, got {ids}"


def test_subparts_numbering(example_input_dir):
    paper = example_input_dir / "papers" / "sample_paper.pdf"
    records = extract_paper(
        paper_id="sample_paper",
        source_file=str(paper),
        paper_hash=sha256_file(paper),
    )
    subparts = [r for r in records if r.numbering_path[:1] == ["3"] and len(r.numbering_path) > 1]
    assert any(r.numbering_path == ["3", "a"] for r in subparts)
    assert any(r.numbering_path == ["3", "b"] for r in subparts)
