from pathlib import Path

from app.adapters.mock_adapter import MockAdapter, MockEmbeddingAdapter
from app.chapters import match_question
from app.hashing import question_id
from app.models import BBox, ChapterSpec, QuestionRecord
from app.retrieval import chunk_text_file
from app.retrieval.store import RetrievalStore


def _q(text: str) -> QuestionRecord:
    return QuestionRecord(
        question_id=question_id("h", ["1"]),
        paper_id="p",
        source_file="",
        page_range=(1, 1),
        numbering_path=["1"],
        verbatim_text=text,
        normalized_text=text.lower(),
        bbox_refs=[BBox(page=1, x0=0, y0=0, x1=10, y1=10)],
    )


def test_match_routes_to_networks(tmp_path: Path):
    p = tmp_path / "networks.md"
    p.write_text("# Networks\n\n## Topology\n\nA star topology connects each computer to a central switch.")
    p2 = tmp_path / "databases.md"
    p2.write_text("# Databases\n\n## Keys\n\nA primary key uniquely identifies a row.")
    chunks = chunk_text_file(path=p, chapter_id="ch_networks") + chunk_text_file(
        path=p2, chapter_id="ch_databases"
    )
    store = RetrievalStore(chunks, MockEmbeddingAdapter())
    chapters = [
        ChapterSpec(chapter_id="ch_networks", title="Networks"),
        ChapterSpec(chapter_id="ch_databases", title="Databases"),
    ]
    q = _q("State two advantages of a star topology.")
    match = match_question(
        question=q, chapters=chapters, store=store, classifier=MockAdapter()
    )
    assert match.primary_chapter == "ch_networks"
    assert match.retrieval_strength > 0


def test_match_routes_to_databases(tmp_path: Path):
    p2 = tmp_path / "databases.md"
    p2.write_text("# Databases\n\n## Keys\n\nA primary key uniquely identifies a row.")
    p = tmp_path / "networks.md"
    p.write_text("# Networks\n\n## Topology\n\nA star topology connects each computer.")
    chunks = chunk_text_file(path=p, chapter_id="ch_networks") + chunk_text_file(
        path=p2, chapter_id="ch_databases"
    )
    store = RetrievalStore(chunks, MockEmbeddingAdapter())
    chapters = [
        ChapterSpec(chapter_id="ch_networks", title="Networks"),
        ChapterSpec(chapter_id="ch_databases", title="Databases"),
    ]
    q = _q("Define a primary key and give one example.")
    match = match_question(
        question=q, chapters=chapters, store=store, classifier=MockAdapter()
    )
    assert match.primary_chapter == "ch_databases"
