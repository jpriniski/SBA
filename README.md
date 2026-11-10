# Suffering Beliefs Annotation Pipeline

**Project:** Suffering Beliefs Framework (SBF), SCF Lab, Duke University
**Grant:** John Templeton Foundation FR#63879
**Protocol:** `SBF_AI_Text_Analysis_Protocol_v2.docx` (August 2026)

---

## What we are building

Across cultures and history, people hold deep, often implicit beliefs about why suffering exists and what it means. These beliefs — that suffering is punishment for wrongdoing, a path to growth, an inescapable shared condition, a divine mystery — shape how people cope, seek help, and make sense of their own pain.

The **Suffering Beliefs Framework** is a systematic effort to identify, catalog, and study these beliefs across a broad corpus of philosophical, religious, literary, and testimonial texts. The core research question: *what are the recurring belief structures humans invoke to make sense of suffering, and what are their psychological and cultural dimensions?*

This pipeline is the data extraction infrastructure for that project. It uses large language models to scan texts at scale, identify passages that express a general belief about suffering, and tag each one against a working classification of belief types — producing a structured archive that human researchers then validate, refine, and analyze.

**What goes in:** a set of texts (open-access corpus, eventually ~37 sources)
**What comes out:** a structured archive of suffering-belief passages, tagged by type, constructs, and confidence — ready for human validation, quantitative analysis, and qualitative deep-dives

---

## Pipeline overview

The pipeline runs in four stages, each leaving a full audit trail:

### Stage 1 — Preprocessing
Each text is cleaned (Gutenberg headers stripped, encoding normalized) and split into overlapping **~1,000-word chunks** with a 200-word overlap between consecutive chunks. Overlap prevents a belief statement that falls near a chunk boundary from being split and missed. Each chunk gets a stable ID like `dante_alighieri_inferno_c0012`.

### Stage 2 — Keyword scan
Every chunk is scanned for **tier 1–2 keywords** from the protocol (§4):
- **Tier 1:** suffer\*, pain, hardship, adversity
- **Tier 2:** affliction, misery, anguish, agony, torment, tribulation, ordeal, distress

Keyword hits are flagged as candidates and recorded in the archive. Each chunk is also scanned for Christine's **seed words** — a vocabulary tied to her nine construct dimensions (prevalence, controllability, meaning, fairness, etc.). These seed matches are recorded as secondary annotations but do not determine whether a chunk enters the pipeline.

### Stage 3a — Screening (Claude Haiku)
*Every* chunk — not just keyword hits — is screened with a minimal yes/no question:
> "Does this chunk plausibly contain a general claim about the nature, meaning, purpose, or value of suffering?"

Chunks that screen YES but had no keyword hit are **contextual passages** — beliefs the keyword search would have missed. The share of contextual passages in the final archive is the keyword-recall estimate reported in the methods.

### Stage 3b — Filter (Claude Haiku)
All keyword-hit chunks and contextual chunks are sent the full filter question:
> "Does this passage express or imply a general belief about the nature, meaning, purpose, or value of suffering *as a phenomenon*?"

The model returns **YES**, **MAYBE**, or **NO**, plus a one-sentence summary of the core belief for YES/MAYBE passages. Only YES and MAYBE passages proceed to tagging. This step reduces candidates by roughly 60–70%.

### Stage 4 — Tagging (Claude Sonnet)
Each surviving passage is tagged against the **working classification**:

| Code | Belief type |
|------|-------------|
| 1 | Punishment/consequence |
| 2 | Teacher/growth |
| 3 | Craving/attachment |
| 4 | Shared condition |
| 5 | Call to compassion |
| 6 | Acceptance/equanimity |
| 7 | Mystery/unknowable |
| 0 | None of the above → new candidate label proposed |

The model also identifies which of Christine's **nine construct dimensions** the belief engages (cause, meaning, fairness, controllability, etc.) and assigns a confidence level. Multiple codes may apply to one passage.

---

## Exploring results — the Viewer

The annotation viewer (`viewer.html`, in the root of this folder) is a self-contained browser tool for exploring any archive CSV. No server needed — open it directly.

### Loading data
1. Open `viewer.html` in any modern browser
2. Drag `results/pilot_archive.csv` onto the page (or click to browse)
3. Optionally load the companion `results/labeled/<source>_labeled.txt` file — this enables full passage context

### What the viewer shows

**Summary charts (left sidebar):**
- **Belief tag distribution** — how many passages express each type of suffering belief; click any bar to filter to those passages; updates the construct chart
- **Construct dimensions** — which of Christine's nine dimensions appear in the currently-selected passages; click to filter further; this chart cross-filters with the tag selection (true linked exploration)
- **Tag co-occurrence matrix** — which belief types tend to appear together in the same passage; click any cell to filter to passages that express both beliefs simultaneously

**Passage cards:**
- Core belief statement extracted by the model
- Belief type tags (click to filter) with hover explanations
- Construct dimension chips (click to filter) with hover explanations
- Confidence badge and trigger type (keyword-matched vs. contextual) with hover explanations
- Full text excerpt, expandable

**Full context panel** (requires labeled file):
Click "Show in context" on any card to see the two chunks before and after the archived passage, each showing its own screen/filter result. This lets reviewers judge whether a passage's neighbors were correctly handled and understand the full textual moment the belief appears in.

### EDA workflow
The charts use **cross-filtering**: the construct chart always shows the construct distribution *within your current tag selection*, not across all passages. This means clicking "Punishment" in the tag chart immediately answers "in punishment passages, which constructs are invoked?" — select "fairness" to drill into passages that frame punishment-as-suffering through a fairness lens. The search box narrows cards and both charts simultaneously.

---

## Quick start

**Requirements:** Python 3.9+, `pip install anthropic`, an Anthropic API key

```bash
# From the pilot/ directory:
export ANTHROPIC_API_KEY="sk-ant-..."
python pipeline.py
```

Results land in `pilot/results/`. Then open `viewer.html` in a browser and load the archive CSV.

**To change which texts are processed:** edit `PILOT_TEXTS` in `config.py`. Comment it out entirely to run all texts in `texts/open access/`.

**To change models:** edit `SCREEN_MODEL`, `FILTER_MODEL`, `TAG_MODEL` in `config.py`. The pipeline currently uses Haiku for screening/filtering and Sonnet for tagging.

**Estimated cost:** ~270 chunks from a single text costs roughly $0.50–1. Running the full 37-text corpus would cost roughly $15–25.

---

## Outputs

### `results/pilot_archive.csv`
One row per archived passage (filter = YES or MAYBE). The main deliverable — the Suffering Beliefs Archive described in protocol §5. Key columns:

| Column | What it contains |
|--------|-----------------|
| `chunk_id`, `source` | where the passage came from |
| `keyword`, `filter_trigger` | what flagged it (`keyword` or `contextual`) |
| `seed_constructs` | Christine's construct dimensions touched by the chunk's vocabulary |
| `core_belief` | one-sentence belief summary from the filter step |
| `tags`, `tag_names` | working classification codes |
| `constructs` | construct dimensions assigned by the tagger |
| `confidence` | HIGH / MEDIUM / LOW |
| `new_candidate_label/definition` | proposed new code, if any |
| `text_excerpt` | first 300 characters of the passage |
| `human_decision`, `human_tags`, `coder_notes`, `resolved_tag` | *empty — for RA validation* |
| `model_*`, `prompt_*`, `run_date` | full provenance |

### `results/labeled/<source>_labeled.txt`
One human-readable file per source. Shows every chunk with its pipeline decisions inline. Archived passages include the full belief summary and tags; screened-out chunks show briefly. Used for RA spot-checks (protocol §6): review ~10 YES and ~10 NO filter decisions after each run.

### `results/run_log.json`
Exact model names, prompt versions, run date, chunk counts, token usage, and any errors. Required for the methods report.

---

## Human validation

The archive CSV has empty columns for RA coding. The validation procedure (protocol §6):

1. 100% of MAYBE passages are human-coded
2. 100% of LOW-confidence tags are human-coded
3. 100% of new-candidate proposals are human-coded
4. A random 20% of HIGH-confidence YES passages are human-coded

RAs code **blind** — with AI columns hidden — using the labeled `.txt` files or a stripped version of the archive CSV. See protocol Part II for the RA coding manual and practice set.

---

## File structure

```
Annotation Pipeline/
├── viewer.html                   ← open in browser to explore any archive CSV
├── seed_topics.py                ← Christine's 9 construct dimensions + seed words
├── pilot/
│   ├── pipeline.py               ← main script (run this)
│   ├── preprocess.py             ← text cleaning and chunking
│   ├── keywords.py               ← keyword scan + seed word annotation
│   ├── config.py                 ← settings: texts, models, chunk size, paths
│   ├── prompts/
│   │   ├── screen_v1.txt         ← screening prompt
│   │   ├── filter_v2.txt         ← filter prompt
│   │   └── tag_v2.txt            ← tagging prompt
│   └── results/
│       ├── pilot_archive.csv
│       ├── run_log.json
│       └── labeled/
│           └── <source>_labeled.txt
└── texts/
    ├── open access/              ← public domain corpus texts
    └── free_to_read/             ← freely available texts
```

---

## Reproducibility

- Prompts are **versioned files** in `prompts/`. Never edit a prompt in place — create `screen_v2.txt` and update `config.py`. The old version stays on disk.
- `run_log.json` records everything needed to re-run a batch identically.
- All Claude calls use **temperature = 0** for deterministic output.
- Passages are extracted by string slicing from source files — no retyping, no paraphrasing (quote-fidelity control, protocol §5 Step 2).
