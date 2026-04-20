import json

from app.adapters.mock_adapter import MockAdapter, MockEmbeddingAdapter


def test_mock_answers_return_structured_json():
    a = MockAdapter()
    resp = a.complete(
        system="You are an expert 10th-grade computer science teacher.",
        user="QUESTION: State two advantages of star topology.\n\n[chunk:x1] it is easy to isolate faults",
    )
    data = json.loads(resp.text)
    assert "direct_answer" in data
    assert "evidence_chunk_ids" in data
    assert data["evidence_chunk_ids"] == ["x1"]


def test_mock_classifier_returns_primary():
    a = MockAdapter()
    resp = a.complete(
        system="Chapter classifier.",
        user="QUESTION: What is a star topology?",
    )
    data = json.loads(resp.text)
    assert "primary_chapter" in data
    assert data["primary_chapter"] == "ch_networks"


def test_mock_judges_pass():
    a = MockAdapter()
    r = json.loads(a.complete(system="Answer judge.", user="ignored").text)
    assert r["pass"] is True


def test_mock_embeddings_cosine_shape():
    e = MockEmbeddingAdapter()
    r = e.embed(["alpha beta", "alpha beta"])
    assert len(r.vectors) == 2
    assert r.vectors[0] == r.vectors[1]
