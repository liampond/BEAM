# BEAM — the Benchmark for Encoding Assessment in Music

The repository contains the dataset, the deterministic answer extractors that
produced the ground truth, the LLM responses, and the SQLite database
(`beam.db`) that binds them together.

## Contents

- [What's in the benchmark](#whats-in-the-benchmark)
- [Repository layout](#repository-layout)
- [`beam.db` schema](#beamdb-schema)
- [Output tree](#output-tree)
- [Reproducing the ground truth](#reproducing-the-ground-truth)
- [Models evaluated](#models-evaluated)
- [Caveats and known issues](#caveats-and-known-issues)
- [Status](#status)

## What's in the benchmark

- **90 passages** from 16 Mozart piano sonatas (45 movements). From each
  movement one 1-bar and one 8-bar passage was randomly selected, giving
  45 + 45 = 90 passages total. The same musical content is provided in four
  formats.
- **4 encoding formats**, each sourced from a separate pre-existing dataset:
  - ABC notation (`.abc`)
  - Humdrum **kern (`.krn`)
  - MEI (`.mei`)
  - MusicXML (`.xml`)
- **9 question types**, each a short numeric or pitch-name probe ("how many
  rests are in this passage?", "what is the pitch of the first note in the
  upper staff?", etc.). The full text of each question lives in the
  `question_types` table; see also [`prompts/system_prompt.txt`](prompts/system_prompt.txt)
  for the system prompt shown to every model.
- **Ground truth** for every (passage × format × question) cell, computed by
  format-specific extractors under [`src/answer_extraction/`](src/answer_extraction/)
  and verified against the rendered score. 90 passages × 4 formats × 9
  questions = **3,240 ground-truth cells**.
- **LLM responses** from three reasoning-class models evaluated once each in a
  zero-shot setting: 3 models × 3,240 cells = **9,720 queries**, all stored in
  `beam.db` and mirrored to [`outputs/`](outputs/).

## Repository layout

```
.
├── beam.db                  SQLite — single source of truth
├── config.yaml              filter + provider config used by submission code
├── prompts/system_prompt.txt
├── data/                    raw Mozart sources (ABC, **kern, MEI, MusicXML, LilyPond)
├── passages/                per-passage excerpts in each format (P-001 … P-090)
├── outputs/                 publication tree: format/model/{1,8}bar/passage/q{qtype}.json
├── src/
│   ├── answer_extraction/   deterministic extractors, one per (format, qtype)
│   ├── core/extract_passage.py   slice a piece into a measure range
│   └── llm_eval/            provider clients, batch API, beam.db writers
├── tests/                   pytest suite (extractors vs. verified GT in beam.db)
```

`scripts/` and `docs/` exist locally but are gitignored — they hold one-off
submission drivers and handoff notes that aren't part of the published
artifact.

## `beam.db` schema

`beam.db` flattens all benchmark state into four tables, keyed by
`(passage_id, qtype, format)` for ground truth and
`(model, format, passage_id, qtype)` for responses.

```sql
question_types(qtype INTEGER PK, question_text TEXT)

passages(
    passage_id TEXT PK,                 -- 'P-001' … 'P-090'
    num_measures INTEGER,               -- 1 or 8
    sonata_number INTEGER, kv_number INTEGER, movement INTEGER,
    start_measure_abc, end_measure_abc,
    start_measure_humdrum, end_measure_humdrum,
    start_measure_mei, end_measure_mei,
    start_measure_musicxml, end_measure_musicxml
)

ground_truth(
    passage_id TEXT, qtype INTEGER, format TEXT,
    answer TEXT, verified INTEGER,
    PRIMARY KEY (passage_id, qtype, format)
)

llm_responses(
    model TEXT, format TEXT, passage_id TEXT, qtype INTEGER,
    raw_response TEXT,                  -- full model output as JSON string
    extracted_answer TEXT,              -- value pulled from {"answer": ...}
    is_correct INTEGER,                 -- compared against ground_truth.answer
    timestamp TEXT,
    source_log TEXT,                    -- path under outputs/
    batch_id TEXT,
    PRIMARY KEY (model, format, passage_id, qtype)
)
```

Per-format measure offsets in `passages` exist because Humdrum and MEI
sometimes label the first measure differently from MusicXML (anacrusis
handling); the `start_measure_<format>` / `end_measure_<format>` columns make
the offset explicit so excerpt boundaries line up across encodings.

## Output tree

Every LLM response in `beam.db` is also written to a flat per-question JSON
file:

```
outputs/{format}/{model}/{N}bar/{passage_id}/q{qtype}.json
```

Each file is self-describing:

```json
{
  "batch_id": "msgbatch_…",
  "expected_answer": "16",
  "extracted_answer": "16",
  "format": "abc",
  "is_correct": true,
  "model": "claude-opus-4-7",
  "num_measures": 1,
  "passage_id": "P-001",
  "qtype": 1,
  "question_text": "How many notes are in the lower staff …",
  "raw_response": "{\"answer\":\"16\"}",
  "source_log": "outputs/phase6_1bar_abc/claude-opus-4-7/abc/Q-001_r1.json",
  "timestamp": "2026-04-24T00:57:19.730207"
}
```

## Models evaluated

Three reasoning-class models, called via each provider's official SDK. The
provider client code in [`src/llm_eval/`](src/llm_eval/) is the reference for
exactly how each model was called (reasoning effort, JSON mode, batching).

| Provider  | Model                       | Reasoning effort | Notes |
|-----------|-----------------------------|------------------|-------|
| OpenAI    | `gpt-5.4`                   | `high`           | Responses API, batch mode |
| Anthropic | `claude-opus-4-7`           | `high`           | Streaming required for ≥128k output; batch mode |
| Google    | `gemini-3.1-pro-preview`    | (default)        | Batch mode |

Every cell was submitted at most once per model. Empty responses (timeouts,
content-policy refusals, batch-side dropouts) are stored verbatim with an
empty `extracted_answer` rather than retried.
