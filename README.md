# Suffering Beliefs Pilot — AI Extraction Pipeline


---

## What this is

This folder contains a pilot implementation of the AI-assisted text extraction pipeline described in the v2 protocol. The goal is to scan a set of open-access historical and philosophical texts, identify passages that express a **general belief about suffering**, and tag each one against Christine's working classification of suffering belief types.

The pipeline replaces the first-pass human extraction step (as in Clifton et al., 2019) with a large language model (Claude), while keeping humans as validators. No AI output enters the framework without human review.

This pilot runs on **5 texts** spanning different sub-corpora to test the pipeline before scaling to the full corpus.

---

## How it works (plain language)

The pipeline has four stages, mirroring Steps 1–4 in the protocol:

### Stage 1 — Preprocessing
Each text is cleaned (Gutenberg headers/footers stripped) and split into overlapping **~1,000-word chunks** with a 200-word overlap between consecutive chunks. The overlap prevents a belief statement that falls near a chunk boundary from being split across two chunks and missed. Each chunk gets a stable ID like `dhammapada_c0012`.

### Stage 2 — Keyword scan
Every chunk is scanned for **tier 1–2 keywords** from the protocol (§4):
- **Tier 1:** suffer\*, pain, hardship, adversity
- **Tier 2:** affliction, misery, anguish, agony, torment, tribulation, ordeal, distress

Chunks with at least one keyword hit are flagged as **keyword candidates**. The keyword that triggered the flag is recorded in the archive (for the keyword-recall estimate in the final report).

Each chunk is also scanned for words from Christine's **seed topic lists** (`seed_topics.py`). These are recorded as secondary annotations — they tell us which of her nine construct dimensions (prevalence, controllability, meaning, etc.) the chunk's vocabulary touches. These seed words do *not* determine whether a chunk enters the pipeline; that is decided by keyword hits and the LLM screen below.

### Stage 3a — Whole-corpus screen (Claude Haiku)
*Every* chunk — not just keyword hits — is sent to Claude with a minimal yes/no question:

> "Does this chunk plausibly contain a general claim about the nature, meaning, purpose, or value of suffering?"

Chunks that say YES but had no keyword hit are called **contextual passages**. They would have been missed by keyword search alone. The share of contextual passages in the final archive is reported as the keyword-recall estimate (protocol §11).

### Stage 3b — Filter (Claude Haiku)
All keyword-hit chunks, plus contextual chunks, are sent to Claude with the full filter prompt (verbatim from Appendix A of the protocol):

> "Does this passage express or imply a general belief about the nature, meaning, purpose, or value of suffering *as a phenomenon*?"

The model returns **YES**, **MAYBE**, or **NO**, plus a one-sentence summary of the core belief for YES/MAYBE passages. Only YES and MAYBE passages proceed to tagging. This step is expected to reduce candidates by roughly 60–70%.

### Stage 4 — Tagging (Claude Sonnet)
Each surviving passage is tagged against the **working classification (v0)** from protocol §15:

| Code | Belief type |
|------|-------------|
| 1 | Punishment/consequence |
| 2 | Teacher/growth |
| 3 | Craving/attachment |
| 4 | Shared condition |
| 5 | Call to compassion |
| 6 | Acceptance/equanimity |
| 7 | Mystery/unknowable |
| 0 | None of the above → new candidate proposed |

The model also tags which of Christine's **nine construct dimensions** the belief relates to (cause, meaning, fairness, etc.) and assigns a confidence level (HIGH / MEDIUM / LOW). Multiple codes may apply to one passage.

---

## Outputs

After running, three types of output appear in `results/`:

### `pilot_archive.csv`
One row per archived passage (filter = YES or MAYBE). This is the main deliverable — the Suffering Beliefs Archive described in protocol §5 / Appendix B. Columns include:

- **chunk_id, source** — where the passage came from
- **keyword** — what triggered it, or "contextual"
- **seed_constructs** — which of Christine's dimensions the chunk vocabulary touched
- **filter_decision, core_belief** — YES/MAYBE and the one-sentence belief summary
- **tags, tag_names** — working classification codes
- **constructs** — Christine's construct dimensions assigned by the tagger
- **confidence** — HIGH / MEDIUM / LOW
- **new_candidate_label / definition** — if the model proposed a new code
- **text_excerpt** — first 300 characters of the passage
- **human_decision, human_tags, coder_notes, resolved_tag** — *empty columns for RA validation*
- **model_*, prompt_*, run_date** — full provenance for reproducibility

### `results/labeled/<source>_labeled.txt`
One human-readable file per source text. Shows every chunk with its decisions inline — designed for RA review. Chunks that were screened out are shown briefly; archived passages show the full belief summary and tags. Use these files for the **spot-checks** described in protocol §6 (RA duty: "review ~10 YES + ~10 NO filter decisions after each run").

### `run_log.json`
Records the exact model names, prompt file versions, run date, chunk counts, token usage, and any errors. Required for the methods report (protocol §11).

---

## File structure

```
11.3.26/
├── pilot/                        ← this folder
│   ├── pipeline.py               ← main script (run this)
│   ├── preprocess.py             ← text cleaning and chunking
│   ├── keywords.py               ← keyword scan + seed word annotation
│   ├── config.py                 ← settings: pilot texts, models, paths
│   ├── prompts/
│   │   ├── screen_v1.txt         ← verbatim screening prompt (Appendix A)
│   │   ├── filter_v2.txt         ← verbatim filter prompt (Appendix A)
│   │   └── tag_v2.txt            ← verbatim tagging prompt (Appendix A)
│   └── results/
│       ├── pilot_archive.csv
│       ├── run_log.json
│       └── labeled/
│           └── <source>_labeled.txt
├── seed_topics.py                ← Christine's 9 construct dimensions + seed words
├── texts/
│   └── open access/              ← downloaded corpus texts
└── SBF_AI_Text_Analysis_Protocol_v2.docx
```

---

## How to run it yourself

### Requirements
- Python 3.9 or later
- An Anthropic API key (get one at console.anthropic.com)
- The `anthropic` Python package: `pip install anthropic`

### Steps

1. Open a terminal and navigate to this folder:
   ```bash
   cd path/to/11.3.26/pilot
   ```

2. Run the pipeline with your API key:
   ```bash
   ANTHROPIC_API_KEY=sk-ant-your-key-here python3 pipeline.py
   ```

3. When finished, results appear in `results/`.

### To change which texts are processed
Open `config.py` and edit the `PILOT_TEXTS` list. To run all texts in the corpus, comment out the `PILOT_TEXTS` variable entirely.

### To change the models
Edit `SCREEN_MODEL`, `FILTER_MODEL`, and `TAG_MODEL` in `config.py`. The pipeline currently uses **Haiku** (cheaper, faster) for screening and filtering, and **Sonnet** (more capable) for tagging.

### Estimated cost
The 5-text pilot processes ~270 chunks. At current Anthropic pricing this costs roughly **$1–2**. Running the full 37-text corpus would cost roughly $10–20.

---

## What happens next (human validation)

The archive CSV has empty columns for RA coding (`human_decision`, `human_tags`, `coder_notes`, `resolved_tag`). The validation procedure is in protocol §6:

1. 100% of MAYBE passages are human-coded
2. 100% of LOW-confidence tags are human-coded  
3. 100% of new-candidate proposals are human-coded
4. A random 20% of HIGH-confidence YES passages are human-coded

RAs code **blind** — with the AI columns hidden — using the labeled `.txt` files or a stripped version of the archive CSV. See protocol Part II (the RA coding manual) for the step-by-step procedure and the practice set.

---

## Reproducibility notes

- Prompts are stored as versioned text files in `prompts/`. **Never edit a prompt in place** — create a new file (e.g. `screen_v2.txt`) and update `config.py`. The old version stays on disk.
- `run_log.json` records everything needed to re-run a batch identically: model, prompt version, date, token counts.
- Claude is called at **temperature = 0** for deterministic output.
- The pipeline never re-types quoted text — passages are extracted by string slicing from the source file (quote-fidelity control, protocol §5 Step 2).
