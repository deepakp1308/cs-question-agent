from app.hashing import question_id, sha256_text, stable_json_hash


def test_sha256_text_stable():
    assert sha256_text("abc") == sha256_text("abc")
    assert sha256_text("abc") != sha256_text("abd")


def test_stable_json_hash_is_order_independent():
    a = stable_json_hash({"b": 2, "a": 1})
    b = stable_json_hash({"a": 1, "b": 2})
    assert a == b


def test_question_id_is_stable_and_short():
    qid = question_id("deadbeef", ["3", "a", "ii"])
    assert len(qid) == 24
    assert question_id("deadbeef", ["3", "a", "ii"]) == qid
    assert question_id("deadbeef", ["3", "a", "iii"]) != qid
