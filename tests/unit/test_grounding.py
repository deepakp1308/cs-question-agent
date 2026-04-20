from app.answer.grounding import grounding_ratio, semantic_agreement, split_claims


def test_split_claims_filters_tiny_fragments():
    claims = split_claims("Star is good. Yes. A star topology helps isolate failures.")
    # "Yes." is under the 3-word floor.
    assert claims
    assert all(len(c.split()) >= 3 for c in claims)


def test_grounding_ratio_full():
    evidence = [
        "A star topology makes fault isolation easy and a cable failure affects only one computer.",
    ]
    ans = (
        "A star topology makes fault isolation easy. "
        "A cable failure affects only one computer."
    )
    ratio = grounding_ratio(answer_text=ans, evidence_texts=evidence, threshold=55.0)
    assert ratio == 1.0


def test_grounding_ratio_zero_for_unrelated_claim():
    evidence = ["SQL SELECT retrieves rows from a table."]
    ans = "The capital of France is Paris and it has a famous tower."
    assert grounding_ratio(answer_text=ans, evidence_texts=evidence) == 0.0


def test_semantic_agreement_high_for_paraphrase():
    a = "Star topology isolates faults to one cable."
    b = "In a star topology a single cable failure does not bring down the network."
    assert semantic_agreement(a, b) >= 0.35
