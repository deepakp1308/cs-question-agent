from pathlib import Path

from app.adapters.mock_adapter import MockEmbeddingAdapter
from app.retrieval import chunk_text_file
from app.retrieval.store import RetrievalStore


def test_chunker_produces_chunks(tmp_path: Path):
    src = tmp_path / "networks.md"
    src.write_text(
        "# Networks\n\n## Star topology\n\n"
        + ("Words " * 600)
        + "\n\n## LANs\n\nA LAN covers a small area."
    )
    chunks = chunk_text_file(path=src, chapter_id="ch_networks")
    assert len(chunks) >= 2
    assert all(c.chapter_id == "ch_networks" for c in chunks)
    assert all("Networks" in c.heading_path for c in chunks)


def test_store_retrieves_by_keyword_and_semantics(tmp_path: Path):
    src = tmp_path / "networks.md"
    src.write_text(
        "# Networks\n\n## Topology\n\nA star topology connects each computer separately to a central switch.\n"
        "## LAN\n\nLAN covers a small area such as a classroom."
    )
    chunks = chunk_text_file(path=src, chapter_id="ch_networks")
    store = RetrievalStore(chunks, MockEmbeddingAdapter())
    hits = store.search("star topology", k=2)
    assert hits
    top_text = hits[0][0].text.lower()
    assert "star" in top_text or "topology" in top_text
