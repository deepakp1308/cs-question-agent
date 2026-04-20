# Computer Science Question-Paper Extraction and Teaching Agent

## Goal
Build a Python-based batch agent that:
1. Reads a folder of computer-science question papers (PDFs/images).
2. Reads chapter selectors (screenshots or a text config describing the target chapters).
3. Optionally reads chapter source material (textbook chapter PDFs, notes, syllabus pages, mark schemes).
4. Extracts questions exactly as written, preserving paper structure.
5. Maps each question to the right chapter.
6. Produces a student-friendly answer and explanation for each question.
7. Runs a separate judge/verifier pipeline to detect bad extraction, bad chapter matching, lazy answers, and hallucinations.
8. Renders output PDFs and publishes them to GitHub Pages.

## Critical design decision
Do **not** build this as one free-form autonomous agent.
Build it as a deterministic orchestration pipeline with model-assisted steps.

Reason:
- Exact extraction needs layout-aware parsing.
- Good teaching answers need grounded retrieval.
- Quality assurance needs an independent verifier.
- Publishing should be gated by pass/fail rules.

## Inputs
Use this folder contract:

```text
/input
  /papers              # question papers in PDF/JPG/PNG
  /chapter_selectors   # screenshots/list of target chapters
  /chapter_sources     # textbook chapter PDFs / notes / syllabus extracts
  /markschemes         # optional but high-value
  project.yaml         # board, grade, subject, age target, output settings
```

### project.yaml
```yaml
subject: computer_science
grade_level: 10
student_age: 15
teaching_style: "clear, patient, first-time learner"
exam_board: "optional"
selection_mode: "all_questions"
dedupe_mode: "group_exact_duplicates"
publish:
  github_pages_repo: "<owner>/<repo>"
  custom_domain: "optional"
  visibility: "public"          # public | private
quality:
  min_extraction_score: 0.98
  min_answer_score: 0.90
  max_repair_loops: 2
  max_run_cost_usd: 25.00       # hard cost cap for a single run
  confidence_weights:
    ensemble_agreement: 0.40
    grounding_ratio: 0.35
    retrieval_strength: 0.25
  grounding_ratio_floor: 0.70   # hard quarantine below this, regardless of composite
models:
  classifier:
    provider: "google"          # cheap/fast: chapter matching, selector parsing, ambiguous-merge resolution
    model: "gemini-2.5-flash"
  generator:
    provider: "anthropic"       # strong frontier model for answer generation
    model: "claude-sonnet-4.6"
  judge:
    provider: "openai"          # MUST be a different provider family than `generator`
    model: "gpt-5.4"
  embeddings:
    provider: "openai"
    model: "text-embedding-3-large"
  reranker:
    provider: "cohere"
    model: "rerank-3.5"
```

## System architecture

```text
File discovery
  -> PDF/image preprocessing
  -> Chapter selector parsing
  -> Question extraction
  -> Question-to-chapter matching
  -> Retrieval-grounded answer generation
  -> Multi-stage judging / repair loop
  -> HTML/PDF rendering
  -> GitHub Pages publishing
```

## Components

### 1) Ingestion service
Responsibilities:
- Scan files and generate a manifest.
- Hash each file for caching.
- Detect PDF vs scanned image vs image-based PDF.
- Store page-level artifacts.

Outputs:
- `runs/<run_id>/manifest.json`
- `runs/<run_id>/pages/*.png`
- `runs/<run_id>/raw_text/*.json`

### 2) Layout-aware parser
Responsibilities:
- Extract page text, blocks, words, and positions.
- Preserve exam structure: section headers, instructions, question numbers, subparts, marks, OR branches, diagrams, tables, code blocks.
- Keep both:
  - `verbatim_text` (for output)
  - `normalized_text` (for matching/search)

Strategy:
- First use deterministic parsing with regex + layout positions.
- Then use a model only to resolve ambiguous merges/splits.
- Never let the model paraphrase the question text.
- Before escalating to the LLM extraction judge, run a **deterministic text-diff verifier** (see §7A).

### 3) Chapter selector parser
Responsibilities:
- Read screenshots of chapter lists or chapter headings.
- Produce structured `ChapterSpec` objects.
- Expand aliases and keyword vocabulary.

Example `ChapterSpec`:
```json
{
  "chapter_id": "ch_networks",
  "title": "Computer Networks",
  "aliases": ["Networks", "Data Communication and Networking"],
  "keywords": ["LAN", "WAN", "topology", "protocol", "packet"],
  "subtopics": ["network devices", "IP address", "switch vs router"],
  "source_docs": ["chapter_sources/networks.pdf"]
}
```

### 4) Question extractor
Responsibilities:
- Produce canonical question records.
- Preserve hierarchy and provenance.
- Support nested numbering like `1`, `1(a)`, `1(a)(i)`.

Example `QuestionRecord`:
```json
{
  "question_id": "paper_2024_p2_q3_a_ii",
  "paper_id": "paper_2024_p2",
  "source_file": "paper_2024_p2.pdf",
  "page_range": [5, 6],
  "section_heading": "Section B",
  "instruction_context": "Answer any three questions.",
  "numbering_path": ["3", "a", "ii"],
  "marks": 2,
  "verbatim_text": "State two advantages of using a star topology.",
  "normalized_text": "state two advantages of using a star topology",
  "bbox_refs": [{"page": 5, "x0": 72, "y0": 214, "x1": 489, "y1": 262}],
  "diagram_refs": [],
  "diagram_crops": [],
  "code_blocks": [],
  "or_group_id": null,
  "variant_role": "primary",
  "duplicate_group_id": null,
  "canonical_question_id": null,
  "continuation_of": null,
  "extraction_confidence": 0.99
}
```

### Structural fields

- `or_group_id` + `variant_role: "primary" | "alternative"`
  - Used when the paper says "Answer 3(a) OR 3(b)".
  - Both branches share an `or_group_id`; exactly one is rendered as `primary` in the student PDF; alternatives are kept for the audit artifact and mark-scheme comparison.
- `duplicate_group_id` + `canonical_question_id`
  - Populated when `project.yaml.dedupe_mode = "group_exact_duplicates"`.
  - All duplicates share a `duplicate_group_id`; one record is designated canonical (`canonical_question_id == question_id`); answers are generated only for the canonical record and reused across the group.
- `continuation_of`
  - Non-null when a subpart spans a page break and was stitched from multiple layout blocks.
  - Points to the `question_id` of the preceding block to preserve traceability without fragmenting the record.
- `diagram_crops: [path]`
  - Rasterized crops of each bounding box that contains a diagram or figure.
  - Fed to the multimodal extraction judge and embedded in both the student PDF and audit artifact.
- `code_blocks: [{text, indent, language?, bbox}]`
  - Detected from monospace font runs in PyMuPDF spans.
  - `indent` is preserved verbatim; renderer emits `<pre><code>` with a monospace stack.

### 5) Chapter matcher
Responsibilities:
- Match each question to one or more target chapters.
- Use both lexical and semantic signals.

Concrete pipeline:
1. **Hybrid candidate retrieval** over the retrieval store (see §6c):
   - BM25 lexical score (SQLite FTS5 or `rank_bm25`) on the question's `normalized_text` against chapter chunks.
   - Dense embedding cosine similarity using the embedding model from `models.embeddings`.
   - Reciprocal-rank fusion over the two lists to produce the top-20 candidates.
2. **Cross-encoder rerank** of the top-20 using `models.reranker` — dramatically improves chapter matching over embeddings-only.
3. **LLM classifier** (`models.classifier`) confirms the final assignment and returns `primary_chapter`, `secondary_chapters`, and per-chapter justification.
4. Return a `ChapterMatch` record:
   ```json
   {
     "primary_chapter": "ch_networks",
     "secondary_chapters": ["ch_security"],
     "retrieval_strength": 0.88,
     "classifier_confidence": 0.92
   }
   ```

Important rules:
- A question may be multi-chapter. Do not force a single chapter if the top-2 classifier scores are within 0.05.
- `retrieval_strength` feeds into the composite confidence (see §6).

### 6) Retrieval-grounded answer generator
Responsibilities:
- Answer each question using chapter source material.
- Write like an excellent 10th-grade computer science teacher.
- Use simple language for a first-time learner.

Answer schema:
```json
{
  "question_id": "paper_2024_p2_q3_a_ii",
  "direct_answer": "A star topology is easy to manage and faults are easier to isolate.",
  "exam_style_answer": "Two advantages are: (1) it is easy to identify a failed node, and (2) a failure in one cable usually does not affect the rest of the network.",
  "step_by_step_explanation": [
    "In a star topology, each computer connects separately to a central device.",
    "Because each device has its own connection, one cable failure usually affects only one computer.",
    "This makes troubleshooting easier compared with topologies where devices share a line."
  ],
  "simple_example": "If one classroom computer disconnects, the others can often continue working normally.",
  "common_mistake": "Do not say that star topology needs no central device. It depends on one.",
  "evidence_chunk_ids": ["src_networks_014", "src_networks_021"],
  "confidence": {
    "composite": 0.93,
    "ensemble_agreement": 0.94,
    "grounding_ratio": 0.96,
    "retrieval_strength": 0.88,
    "model_self_reported": 0.95
  }
}
```

### Composite confidence

Model-reported confidence is kept for audit but **never used as the gating signal** — LLMs are overconfident and poorly calibrated. The `composite` score is what drives publish / quarantine decisions.

Inputs:

- `ensemble_agreement` — two independent generations are produced (temperature jitter or provider jitter) and their semantic similarity is scored (embedding cosine or judge-scored). Disagreement signals uncertainty that the generator will not self-report.
- `grounding_ratio` — fraction of declarative claims in the answer that cite at least one `evidence_chunk_id`. Computed post-hoc by a deterministic claim splitter + chunk-overlap check, not by asking the model.
- `retrieval_strength` — the minimum top-k similarity across the retrieved evidence. Low values mean the retrieval store did not confidently cover the question.
- `model_self_reported` — recorded for drift analysis only.

Composite formula (starting point, tunable against the golden set):

```
composite = 0.40 * ensemble_agreement
          + 0.35 * grounding_ratio
          + 0.25 * retrieval_strength
```

The weights are pinned in `project.yaml -> quality.confidence_weights` so they can be retuned without code changes.

Generation rules:
- Scale depth by marks.
- Always include a short plain-English explanation.
- Never answer from memory when chapter source text is available.
- If evidence is weak, set low confidence and route to repair/review.

### 6b) Mark scheme integration

Mark schemes are high-value ground truth and must not be treated as optional scenery. When `/input/markschemes` is populated, the pipeline uses them in three places:

#### Retrieval
- Indexed into the same retrieval store as chapter sources (see §6c) with `source_type: markscheme` metadata on every chunk.
- At answer-generation time, mark-scheme chunks for the matched chapter(s) are included in the evidence set alongside textbook chunks.
- The generator is instructed to treat mark-scheme phrasing as authoritative when it contradicts a textbook extract.

#### Acceptable alternatives
- For open-ended questions, a pre-processing step extracts "acceptable alternative answers" from the mark scheme (e.g., "any two of: …"). These are attached to the `QuestionRecord` as:
  ```json
  "acceptable_alternatives": [
    {"text": "easy to isolate a failed node", "source": "ms_p2_q3_a_ii"},
    {"text": "one cable failure does not bring down the whole network", "source": "ms_p2_q3_a_ii"}
  ]
  ```
- The renderer shows these in the audit artifact. The student PDF does not expose them verbatim — it uses them to shape the answer explanation.

#### Judging
- When a mark scheme exists for a question's chapter, the answer judge's `correctness` and `completeness` scores MUST be computed against the mark scheme, not just against textbook chunks.
- The judge prompt receives the mark-scheme chunks explicitly labelled as "authoritative scoring rubric".
- If the answer misses more than `1 - quality.min_answer_score` of the acceptable alternatives (normalized by marks), the answer fails and is routed to repair with the missed alternatives attached as hints.

### 6c) Retrieval store

A single store backs both chapter matching (§5) and answer generation (§6). No external vector database is required — the corpus is small (textbook chapters + mark schemes) and fits comfortably in local SQLite.

#### Stack
- **Lexical index**: SQLite FTS5 (built-in, zero dependency) or `rank_bm25`.
- **Dense index**: `sqlite-vec` (SQLite extension) or `lancedb` (embedded, no server). Both keep the run reproducible and air-gap friendly.
- **Embedding model**: `models.embeddings` (see §"Model policy").
- **Reranker**: `models.reranker` cross-encoder, invoked on the top-20 candidates.
- **Fusion**: reciprocal-rank fusion of BM25 and dense results before rerank.

#### Chunking strategy
- **Heading-aware**: chunks never cross chapter or major-heading boundaries.
- **Target size**: 300–500 tokens per chunk, 50-token overlap.
- **Metadata on every chunk** (attached at index time):
  ```json
  {
    "chunk_id": "src_networks_014",
    "chapter_id": "ch_networks",
    "source_file": "chapter_sources/networks.pdf",
    "source_type": "textbook",     // textbook | markscheme | notes | syllabus
    "page": 12,
    "heading_path": ["Networks", "Topologies", "Star topology"],
    "token_count": 412
  }
  ```
- Code blocks, tables, and figure captions are kept intact as their own chunks to preserve the monospace / tabular structure for the generator.

#### Indexing cache
- Keyed by `sha256(source_file_hash + chunker_version + embedding_model + embedding_model_version)`.
- Stored at `runs/_shared/retrieval_index/` so successive runs against the same `/input/chapter_sources` do not re-embed.
- Invalidated automatically when any file hash, the chunker version, or the embedding model identifier changes.

### 7) Judge / verifier pipeline
Use multiple judges, not one.

#### A. Extraction judge

Run as a two-stage gate. Stage 1 is deterministic and handles the majority of questions; Stage 2 (LLM) is only invoked when Stage 1 cannot confidently pass the record.

##### A.1 Deterministic text-diff verifier (first gate)
- Source of truth: OCR of the source page crop via PyMuPDF `get_text("words")` with span geometry; for scanned papers, Tesseract over the bbox crop.
- Compare the reconstructed source text against `verbatim_text` using `rapidfuzz.fuzz.ratio` (or `difflib.SequenceMatcher`) at the character level after whitespace normalization.
- Thresholds:
  - `similarity >= 0.99` **and** numbering + marks regex-matched on the source crop: auto-pass, skip LLM judge.
  - `similarity >= 0.95` and below 0.99: escalate to LLM judge with the diff attached.
  - `similarity < 0.95`: hard fail, route to repair with the page crop.
- Also deterministic:
  - `numbering_path` must be locatable in the source crop via the numbering regex.
  - `marks` must match a `[N]` / `(N marks)` pattern in the crop.
  - Monospace runs in PyMuPDF spans must map 1:1 to entries in `code_blocks`.
- Target: ~80% of questions pass without calling the LLM extraction judge.

##### A.2 LLM extraction judge (second gate, invoked only on Stage 1 escalation)
Checks:
- Text fidelity to source page
- Numbering fidelity
- Marks fidelity
- Section / instruction fidelity
- Missing diagram labels / code indentation

Inputs:
- Source page image crop
- Extracted verbatim text
- Bounding boxes
- Neighboring text blocks
- The Stage 1 diff (so the model can focus on the specific delta)

Output:
```json
{
  "pass": true,
  "score": 0.99,
  "stage_1_similarity": 0.992,
  "stage_1_passed": true,
  "issues": []
}
```

#### B. Chapter-match judge
Checks:
- Does the question really belong to the assigned chapter?
- Is there a better chapter candidate?
- Is the question cross-topic?

#### C. Answer judge
Checks:
- correctness (scored against mark scheme when present; see §6b)
- grounding to source chunks (textbook + mark-scheme)
- completeness for marks awarded (must cover the required number of acceptable alternatives)
- age-appropriate clarity
- not lazy / not too short
- no unsupported claims

Rubric:
```json
{
  "correctness": 0.94,
  "grounding": 0.96,
  "completeness": 0.90,
  "clarity": 0.95,
  "age_fit": 0.97,
  "pass": true,
  "repair_instructions": []
}
```

#### D. Repair loop
- If extraction fails: re-run extraction with page crop context.
- If chapter match fails: re-rank candidates and reclassify.
- If answer fails: send question + evidence + judge feedback to repair prompt.
- Max repair loops should be configurable.

### 8) Renderer
Generate two outputs:

1. **Student PDFs** — one per chapter plus a master index
   - `site/runs/<run_id>/chapter_<chapter_id>.pdf` — one PDF per chapter, containing:
     - Chapter title
     - Questions only (preserving OR-branches as side-by-side choices)
     - Worked answers after the question section
     - Friendly explanations, plain-English first, technical terms second
   - `site/runs/<run_id>/index.html` — master index with links to every chapter PDF, counts, and last-updated timestamp.
   - Rationale: per-chapter PDFs make incremental republishing cheap, keep individual file sizes small on GitHub Pages, and match how students actually consume the material.

2. **Audit PDF / HTML**
   - Source provenance
   - Confidence scores (composite + sub-scores)
   - Judge results (per stage)
   - Page references and evidence chunks
   - Per-question accept / reject / edit actions (see "Human review workflow")

#### Render pipeline
- Structured JSON → Jinja HTML → PDF via **WeasyPrint**.
- WeasyPrint is pinned; wkhtmltopdf is explicitly dropped (deprecated, weak code-block and CSS support).
- **Math**: detect `$...$` / LaTeX patterns during answer assembly and pre-render to HTML via **KaTeX** (server-side render) before handing to WeasyPrint.
- **Code**: `<pre><code>` with a monospace stack (`"JetBrains Mono", "Menlo", monospace`). `code_blocks` from the `QuestionRecord` are rendered verbatim with indentation preserved.
- **Diagrams**: embed the `diagram_crops` images inline; the student PDF gets compressed rasters, the audit artifact keeps high-res.
- **Post-processing**: every generated PDF is passed through a Ghostscript compression step (`-dPDFSETTINGS=/ebook`) to keep file sizes within GitHub Pages limits and speed up first paint on mobile.
- **Reproducibility**: Jinja templates live under `app/render/html_templates/` and are versioned; the rendered PDF metadata records the template version, run id, and prompt versions.

### 9) Publisher
Responsibilities:
- Copy PDFs to a static site directory.
- Build an index page linking per-chapter PDFs and the audit artifact.
- Deploy to the configured target based on `publish.visibility`.
- Return final URLs (public or signed).

#### Visibility modes

Selected by `project.yaml -> publish.visibility`:

- **`public`** (default): deploy to GitHub Pages.
  - Example URL: `https://<user>.github.io/<repo>/runs/2026-04-20/chapter_networks.pdf`
  - Appropriate only when papers and mark schemes are not copyright-restricted and no student PII is present.
  - Quarantine artifacts are always excluded from the public sitemap and marked `noindex`.
- **`private`**: deploy to an authenticated or signed-URL target.
  - No specific provider is mandated. Any of the following satisfies the contract:
    - Vercel project with password protection or Clerk-gated routes.
    - S3 / R2 bucket with time-limited presigned URLs; the publisher returns the signed list.
    - Internal static host behind SSO.
  - The publisher must return URLs that are not trivially shareable outside the intended audience.

#### Hard rules
- If any of the input files carries a copyright notice or `/input/markschemes` is populated from a licensed source, `publish.visibility: public` is rejected at startup.
- The publisher writes a `runs/<run_id>/published.json` manifest listing every deployed artifact, its visibility mode, and the final URL.

## Model policy

The pipeline is heterogeneous by design. Every stage picks a model role from `project.yaml -> models`. Each output record logs the exact model, provider, and prompt version used.

### Roles

| Role | Used by | Selection criteria |
|------|---------|--------------------|
| `classifier` | Chapter selector parsing, chapter matching, ambiguous-merge resolution in the extractor | Cheap, fast, structured output. Latency and cost dominate over reasoning depth. |
| `generator` | Retrieval-grounded answer generation | Strong frontier model; best available reasoning + instruction following. |
| `judge` | Extraction judge (Stage 2), chapter-match judge, answer judge | Strong model from a **different provider family** than `generator`. |
| `embeddings` | Dense retrieval over chapter sources and mark schemes | High-quality long-context embedding model. |
| `reranker` | Cross-encoder rerank over top-20 retrieval candidates | Cross-encoder with strong exam-text relevance. |

### Independence requirement

- `judge.provider` MUST NOT equal `generator.provider`.
- The orchestrator validates this at startup and aborts if violated.
- Rationale: shared provider families share training-data overlap and systematic blind spots (e.g., identical hallucination patterns, identical numerical-reasoning gaps). A different-family judge is the cheapest way to approximate genuine independence.

### Per-record logging

Every record written under `runs/<run_id>/stage_outputs/` includes:
```json
{
  "models_used": {
    "classifier": "google/gemini-2.5-flash",
    "generator": "anthropic/claude-sonnet-4.6",
    "judge": "openai/gpt-5.4"
  },
  "prompt_versions": {
    "generate_answer_teacher": "v3",
    "judge_answer": "v2"
  }
}
```

This is what makes re-runs, regressions, and audits reproducible.

## Run execution model

The orchestrator is a **resumable DAG**, not a linear pipeline. Every stage is idempotent and keyed by stable ids so a failed or rate-limited run resumes from where it stopped.

### Idempotency keys
- Per-question key: `question_id = sha256(paper_hash + "/" + "/".join(numbering_path))`
- Per-chunk key: `chunk_id = sha256(source_file_hash + "/" + chunk_offset)`
- Per-stage key: `{stage}/{question_id}` or `{stage}/{chunk_id}`

### Stage output layout
```text
runs/<run_id>/
  manifest.json
  stage_outputs/
    ingest/<paper_id>.json
    extract/<question_id>.json
    match/<question_id>.json
    answer/<question_id>.json
    judge_extraction/<question_id>.json
    judge_match/<question_id>.json
    judge_answer/<question_id>.json
    repair/<question_id>.json
    render/<chapter_id>.json
  errors/
    <stage>/<id>.error.json
  metrics.json
  REPORT.md
```

### Resumption rules
- Before executing a stage on an input, the orchestrator hashes the stage's **input dependencies** and compares to the hash recorded in the existing output file.
- If the output exists and input hashes match: skip.
- If the output exists but input hashes differ: invalidate downstream outputs and re-run.
- Failed runs write `errors/<stage>/<id>.error.json` with stack trace and provider response (if LLM) and do **not** block unrelated questions.

### Parallelism
- Each stage processes its queue with an async worker pool sized by `runtime.concurrency` in `project.yaml`.
- LLM calls are rate-limited with a token-bucket semaphore keyed per-provider so a single rate-limited provider does not stall the whole run.
- CPU-bound stages (PyMuPDF parsing, OCR, Ghostscript compression) run in a process pool.

### Cost cap enforcement
- `metrics.json` is updated after every LLM call.
- When running total crosses `quality.max_run_cost_usd`, the orchestrator:
  1. Completes in-flight calls.
  2. Refuses to enqueue new LLM work.
  3. Proceeds to render whatever is available and exits non-zero.
- This keeps unattended CI runs from burning budget on a single misconfigured prompt.

## Run telemetry

Every run writes:

### `runs/<run_id>/metrics.json`
```json
{
  "run_id": "2026-04-20-demo",
  "started_at": "2026-04-20T14:00:00Z",
  "finished_at": "2026-04-20T14:14:37Z",
  "cost_usd": {
    "total": 4.82,
    "by_stage": { "extract": 0.11, "match": 0.06, "answer": 2.94, "judge_answer": 1.61, "repair": 0.10 },
    "by_model": { "anthropic/claude-sonnet-4.6": 2.94, "openai/gpt-5.4": 1.72, "google/gemini-2.5-flash": 0.16 }
  },
  "tokens": { "input": 1_842_111, "output": 184_203 },
  "latency_ms": { "extract_p50": 412, "answer_p50": 3_120, "judge_answer_p50": 2_780 },
  "cache": { "llm_hits": 318, "llm_misses": 214, "retrieval_hits": 912, "retrieval_misses": 18 },
  "judge_pass_rates": { "extraction": 0.97, "match": 0.94, "answer": 0.91 },
  "confidence_distribution": { "auto_publish": 142, "publish_with_judge_pass": 31, "quarantined": 9 }
}
```

### Prompt versioning
- All prompts live at `prompts/<name>.v<N>.txt` (e.g., `prompts/generate_answer_teacher.v3.txt`).
- The active version per prompt is pinned in `prompts/manifest.yaml`:
  ```yaml
  extract_question: v2
  classify_question_to_chapter: v1
  generate_answer_teacher: v3
  judge_extraction: v1
  judge_answer: v2
  repair_answer: v1
  ```
- Every record in `stage_outputs/` records the prompt version it was produced with (see §"Model policy"). Bumping a version automatically invalidates downstream outputs on the next run.

## Runtime rules

### Non-negotiable rules
1. Preserve exact question wording in the output document.
2. Preserve numbering hierarchy and marks.
3. Store provenance for every extracted question.
4. Use grounded retrieval for every answer.
5. Do not publish low-confidence answers automatically.
6. Keep a separate audit artifact for parents/QA.
7. Cache aggressively by file hash, page hash, and question hash.

### Confidence policy

Tiers are defined in terms of the **composite** confidence score (see §6 "Composite confidence"), not the model's self-reported value.

- `composite >= 0.95`: auto-publish (still requires all judges to pass)
- `composite 0.85 - 0.94`: publish only if all judges pass and no critical issue is flagged
- `composite < 0.85`: quarantine to review queue; emit a reviewer artifact (see §8 / §"Human review workflow")

Additional hard gates independent of the composite score:

- Any judge returning `pass: false` with a `critical` issue forces quarantine regardless of composite score.
- `grounding_ratio < 0.70` forces quarantine — an answer that cannot be traced to evidence must never be auto-published, even if the ensemble agreed.
- If mark schemes are present for the question's chapter and the answer judge flags `correctness` below threshold, the record is quarantined.

## Human review workflow

The audit HTML is not a read-only report — it is the reviewer UI. Without a structured review path, the quarantine tier accumulates forever.

### Audit HTML capabilities
- **Sort and filter** by: `composite` confidence, chapter, judge status, presence of mark scheme, cost per question.
- **Per-question actions** (emitted as JSON to `runs/<run_id>/review/decisions.json` when the reviewer clicks):
  - `accept` — marks the record as human-approved; publishable even if composite < threshold.
  - `reject` — marks the record as blocked; never published, kept for analysis.
  - `edit` — inline edit of `verbatim_text` and/or answer fields; edit diff is stored with reviewer id + timestamp.
- **Evidence overlay**: clicking a claim in the answer highlights the cited retrieval chunk and the source-page bbox.
- **Model and prompt transparency**: every card shows `models_used` and `prompt_versions` from the stage outputs so the reviewer can attribute regressions.

### Quarantine artifact
- A standalone `runs/<run_id>/quarantine/` directory contains one file per quarantined record (`<question_id>.json`) bundling the question, all candidate answers, judge outputs, retrieval hits, and confidence sub-scores.
- `runs/<run_id>/quarantine/INDEX.md` lists every quarantined question with the primary reason (e.g., `grounding_ratio_floor`, `judge_critical_issue`, `composite_below_0.85`).
- The quarantine index is linked from the master `index.html` but rendered with `<meta name="robots" content="noindex">` and excluded from the published sitemap.

### Golden promotion
- Reviewer `edit` actions that correct an extraction or an answer can be promoted into the golden set with a single CLI command:
  ```bash
  python -m app.cli promote-golden --run-id <run_id> --question-id <question_id>
  ```
- This writes the reviewer-approved record into `tests/goldens/` with the source crop, expected text, expected chapter, and accepted answer. The golden set therefore grows through real reviewer labor rather than synthetic curation.

## Recommended repository layout

```text
cs-question-agent/
  app/
    cli.py
    config.py
    models.py
    orchestrator.py
    cache.py
    logging.py
    adapters/
      llm_base.py
      openai_adapter.py
      anthropic_adapter.py
    ingest/
      discover.py
      pdf_parser.py
      image_parser.py
      ocr_fallback.py
    extract/
      regex_rules.py
      layout_rebuilder.py
      question_extractor.py
      structure_normalizer.py
    chapters/
      selector_parser.py
      chapter_matcher.py
    answer/
      retriever.py
      generator.py
      repair.py
    judge/
      extraction_judge.py
      match_judge.py
      answer_judge.py
      score_aggregator.py
    render/
      html_templates/
      pdf_renderer.py
      site_builder.py
    publish/
      github_pages.py
  prompts/
    extract_question.txt
    parse_chapter_selector.txt
    classify_question_to_chapter.txt
    generate_answer_teacher.txt
    judge_extraction.txt
    judge_answer.txt
    repair_answer.txt
  tests/
    goldens/
    unit/
    integration/
  site/
  runs/
  .github/workflows/
    build-and-deploy.yml
  README.md
```

## Suggested CLI

```bash
python -m app.cli ingest --input ./input --run-id 2026-04-20-demo
python -m app.cli extract --run-id 2026-04-20-demo
python -m app.cli match --run-id 2026-04-20-demo
python -m app.cli answer --run-id 2026-04-20-demo
python -m app.cli judge --run-id 2026-04-20-demo
python -m app.cli render --run-id 2026-04-20-demo
python -m app.cli publish --run-id 2026-04-20-demo
```

Also provide a single orchestration command:

```bash
python -m app.cli run --input ./input --run-id 2026-04-20-demo
```

### Targeted reruns

All stage commands and `run` accept `--only` filters for debugging and partial reprocessing:

```bash
python -m app.cli answer --run-id 2026-04-20-demo --only chapter=ch_networks
python -m app.cli judge  --run-id 2026-04-20-demo --only question_id=paper_2024_p2_q3_a_ii
python -m app.cli run    --input ./input --run-id 2026-04-20-demo --only paper=paper_2024_p2
```

`--only` accepts repeated key=value flags and combines them with AND semantics. Combined with the resumable DAG, this makes iteration cheap: fix a prompt, rerun only affected questions, republish.

### Progress and report

- During execution, the CLI prints a compact per-stage progress summary: `[extract] 48/57 (err 1, skipped 9, $0.12)`.
- At the end of a run, the orchestrator writes `runs/<run_id>/REPORT.md` with:
  - Run id, input summary, cost total, duration
  - Judge pass rates per stage
  - Confidence distribution (auto-publish / judge-gated / quarantined counts)
  - Top 10 most expensive questions (for cost debugging)
  - Deep links to the published artifacts and the quarantine index
- `REPORT.md` is also copied into the audit HTML header so reviewers see the run context without leaving the page.

## Prompt design

### Extract question prompt
Purpose:
- Convert page blocks into structured question JSON.

Hard rules:
- Do not paraphrase.
- Do not merge unrelated questions.
- Preserve exact numbering.
- Preserve marks and section instructions.
- Return only JSON.

### Answer generation prompt
Persona:
- You are an expert 10th-grade computer science teacher.
- The student is 15 and learning this topic for the first time.

Hard rules:
- Start with the direct answer.
- Then explain how we know.
- Use plain English first, technical terms second.
- Use retrieved evidence only.
- Mention uncertainty when source support is weak.

### Judge prompt
Hard rules:
- Do not be polite; be strict.
- Fail the answer if any major claim is unsupported.
- Fail extraction if numbering, marks, or wording are missing.
- Return machine-readable scores and repair notes.

## Testing strategy

### Unit tests
- regex segmentation
- numbering parser
- mark extraction
- duplicate grouping
- chapter alias matching

### Integration tests
- digital PDF paper
- scanned paper
- paper with diagrams
- paper with nested subquestions across page breaks
- paper with OR choices
- chapter selector screenshot parsing

### Golden tests
Maintain a hand-verified dataset of:
- source page crop
- exact extracted question text
- correct chapter label
- accepted answer
- judge pass/fail expectation

Goldens are **grown through reviewer edits** (see "Golden promotion" above), not just hand-curated.

### Shadow-run regression
Every prompt or model change must pass a shadow run against the golden set before merge. Configured as a CI job:

1. Run the pipeline against `tests/goldens/` using the **new** prompt/model versions.
2. Write outputs to `tests/goldens/actual/<question_id>.json`.
3. Compare against `tests/goldens/expected/<question_id>.json`:
   - Extraction: character-level diff on `verbatim_text`; numbering + marks must match exactly.
   - Chapter match: exact match on `primary_chapter`; secondary chapters F1 ≥ expected.
   - Answer: judge-based scoring (same judge model used in prod) against the accepted answer.
4. Produce `tests/goldens/report.md` summarizing per-question pass/fail with diffs.
5. The CI step fails (blocking merge) if any acceptance-criteria threshold regresses:
   - Extraction exact-wording rate < 0.95
   - Chapter F1 < 0.90
   - Answer judge pass rate < 0.90

The report is committed as a build artifact so regressions are visible in the PR review.

## Acceptance criteria
1. Exact wording preserved for at least 95% of gold questions.
2. Numbering tree and marks preserved for at least 99% of gold questions.
3. Chapter-assignment F1 above 0.90 on gold set.
4. Answer-judge pass rate above 0.90 for grounded chapters.
5. No auto-publishing when any critical judge fails.

## Build order

### Phase 1: MVP
- PDF ingestion
- chapter screenshot parsing
- question extraction
- question-to-chapter matching
- answer generation
- local PDF render

### Phase 2: Quality
- extraction judge
- answer judge
- repair loop
- golden tests
- caching

### Phase 3: Publishing
- static site build
- GitHub Pages deploy
- custom domain support
- audit report

## Practical recommendation
For your use case, the most important improvement is this:
- **Use chapter screenshots for routing**
- **Use actual chapter source PDFs/notes for answer grounding**
- **Use mark schemes when available for verification**

That combination is what will make the system accurate enough to trust with a student's learning.
