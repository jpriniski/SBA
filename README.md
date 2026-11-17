# Suffering Beliefs Annotation Pipeline

**Project:** Suffering Beliefs Framework (SBF), SCF Lab, Duke University
**Grant:** John Templeton Foundation FR#63879
**Protocol:** `SBF_AI_Text_Analysis_Protocol_v2.docx` (August 2026)

---

## What we are building

Across cultures and history, people hold deep, often implicit beliefs about why suffering exists and what it means. These beliefs — that suffering is punishment for wrongdoing, a path to growth, an inescapable shared condition, a divine mystery — shape how people cope, seek help, and make sense of their own pain.

The **Suffering Beliefs Framework** is a systematic effort to identify, catalog, and study these beliefs across a broad corpus of philosophical, religious, literary, and testimonial texts. The core research question: *what are the recurring belief structures humans invoke to make sense of suffering, and what are their psychological and cultural dimensions?*

This pipeline is the data extraction infrastructure for that project. It uses large language models to scan texts at scale, identify passages that express a general belief about suffering, and name each belief in its own terms — producing a structured archive and a list of open-coded beliefs that human researchers then validate, consolidate into a classification, and analyze.

**What goes in:** a set of texts (open-access corpus, eventually ~37 sources)
**What comes out:** a structured archive of suffering-belief passages, plus one row per belief (label, definition, evidence quote, construct dimension, ratings) — ready for human validation, clustering into candidate themes, and qualitative deep-dives

---

## Pipeline overview

The pipeline runs in five stages, each leaving a full audit trail. A separate script then groups the open-coded beliefs into candidate themes.

### Stage 1 — Preprocessing
Each text is cleaned (Gutenberg headers stripped, encoding normalized) and split into overlapping **~1,000-word chunks** with a 200-word overlap between consecutive chunks. Overlap prevents a belief statement that falls near a chunk boundary from being split and missed. Each chunk gets a stable ID like `dante_alighieri_inferno_c0012`.

### Stage 2 — Keyword scan
Every chunk is scanned for **tier 1–2 keywords** from the protocol (§4):
- **Tier 1:** suffer\*, pain, hardship, adversity
- **Tier 2:** affliction, misery, anguish, agony, torment, tribulation, ordeal, distress

Inflected forms count (tormented, miserable, hardships); "pain" does not match "painted". The keyword list has a version (`keywords_v2`) recorded in `run_log.json`.

Keyword hits are flagged as candidates and recorded in the archive. Each chunk is also scanned for Christine's **seed words** — a vocabulary tied to her nine construct dimensions (prevalence, controllability, meaning, fairness, etc.). These seed matches are recorded as secondary annotations but do not determine whether a chunk enters the pipeline. The seed words live in `seed_topics.py`, which is not in this repo; without it the pipeline runs and leaves `seed_constructs` blank.

### Stage 3a — Screening (Claude Haiku)
*Every* chunk — not just keyword hits — is screened with a yes/no question: could any part of it plausibly be read as stating, implying or disputing a general claim about suffering as a phenomenon, on any aspect of it? The screen favors recall: when unsure, YES.

Chunks that screen YES but had no keyword hit are **contextual passages** — beliefs the keyword search would have missed. The share of contextual passages in the final archive is the keyword-recall estimate reported in the methods.

### Stage 3b — Filter (Claude Haiku)
All keyword-hit chunks and contextual chunks are sent the full filter question:
> "Does this passage express or imply a general belief about suffering as a phenomenon, on any aspect of it?"

What counts as a belief is defined once, in the system prompt: the aspects it lists (what suffering is, how common it is, why it happens, what it does to people, how controllable it is, how to respond to one's own or others' suffering, how to judge it overall) are examples, and a claim about any other aspect counts equally.

The model returns **YES**, **MAYBE**, or **NO** with a one-line reason, plus, for YES/MAYBE passages, a verbatim evidence quote and a one-sentence core belief. Only YES and MAYBE passages proceed to Stage 4.

### Stage 4 — Open coding (Claude Sonnet)
The tagger is given **no code list and no list of topics**, so that beliefs nobody anticipated can surface. For each belief a passage expresses, it returns:

- a two-to-four-word **label** and a one-sentence **definition** in everyday words
- a verbatim **evidence** quote
- a **stance**: `endorses`, `denies`, `mentions` (reported as something people say, no side taken), `conditional` (held only under a stated condition) or `depicts` (shown through the events of a story, not stated)

These go to `results/open_codes.csv`, one row per belief. The classification is built from these open codes; it is not assumed in advance.

The earlier seven-code working classification (punishment, growth, craving, shared condition, compassion, acceptance, mystery) is **not used in this pass**. It remains in `pipeline.py` only for the deductive tag prompt (`tag_v3`), which is meant to be run later against the classification derived from the open codes.

### Stage 5 — Areas and ratings (Claude Sonnet)
Only after the beliefs have been named are they placed on a fixed grid. Each belief gets one **area**; each asserted belief is also rated 1–5 on evaluation, inevitability and intertwinement, with blank meaning the belief takes no position. See "Prompt layout" below.

### After the run — Clustering
`python cluster_open_codes.py` groups the beliefs by the similarity of their definitions and writes `results/cluster_summary.csv`: one row per candidate theme, with its size, most common labels and most central definition, for the team to name, merge and split into classification v1. It needs `pip install pandas scikit-learn sentence-transformers`; use `--scan` to see how many clusters different thresholds give, and `--k 30` to ask for a fixed number.

---

## Prompt layout (v3)

From `system_v1` / `screen_v2` / `filter_v3` / `tag_v3` on, every call has two parts:

- **System prompt** (`prompts/system_v1.txt`), shared by all three steps: the coder's role, the five tests for a suffering belief (the four in protocol §8 and §14, plus a Claim test added here), the recurring judgment calls, the rule to code from the page and not from prior knowledge of the work, and JSON-only output.
- **Task prompt** (one per step), sent as the user message with the passage filled in at `<<PASSAGE>>`. The tag prompt also takes `<<CLASSIFICATION>>`, `<<CONSTRUCTS>>` and `<<CORE_BELIEF>>`.

New output fields: the filter returns a short `reason` and a verbatim `evidence` quote (checked against the chunk and recorded as `evidence_verbatim`); the tagger returns `rejects`, the codes a passage explicitly denies.

The tag step has two modes, chosen by `TAG_PROMPT_VERSION` in `config.py`:

- `tag_open_v1` (current setting): **open coding**. The tagger is given no code list. For each belief a passage expresses it returns a label, a one-sentence definition, a verbatim evidence quote and a stance. These go to `results/open_codes.csv`, one row per belief, which is the input for building the classification. In the archive, `tags` is empty and `open_labels` lists the labels.
- `tag_v3`: **deductive coding** against the working classification in `pipeline.py`. Use it once a classification has been built from the open codes.

**Step 5, areas and ratings (`rate_v1`).** After open coding, each belief is assigned one area, so `open_codes.csv` can be tabulated to check coverage. The grid (`BELIEF_AREAS` in `pipeline.py`) follows the qualitative interview guide, so the text and interview streams share one grid:

`understanding`, `prevalence`, `causes`, `consequences`, `controllability`, `personal_response`, `interpersonal_response`, `overall_evaluation`, plus `meaning_fairness` (prominent in the texts, absent from the guide) and `other`.

A belief that fits no area is coded `other`, with a few words in `area_note` on what it is about; those rows are the candidates for areas the guide does not cover. Names outside the list are recorded as `INVALID(...)`. The grid is applied after open coding on purpose: it describes the beliefs that were found and plays no part in finding or naming them. Christine's nine construct dimensions are still used by `tag_v2` and `tag_v3`.

Each asserted belief is also rated 1-5 on three dimensions, with blank meaning the belief takes no position:

| Rating | 1 | 5 |
|--------|---|---|
| `rating_evaluation` | suffering is purely harmful | suffering can enrich a life |
| `rating_inevitability` | avoidable or exceptional | an inevitable part of every life |
| `rating_intertwinement` | separate from and opposed to what is good in life | bound up with what people care about most |

One call per passage (`RATE_MODEL`); results are columns in `open_codes.csv`, with empty `human_*` columns for blind validation. Beliefs the passage denies or only mentions get an area but no ratings. Set `RATE_PROMPT_VERSION = None` in `config.py` to skip the step. Before analysis: validate the ratings against human coders, and remove duplicate beliefs that come from the 200-word overlap between chunks.

The original prompts (`screen_v1`, `filter_v2`, `tag_v2`) still run unchanged: a prompt file without `<<PASSAGE>>` is sent as the system message with the passage as the user message, as before. Set the versions in `config.py`.

The v3 prompts were drafted after reading pilot output and have not yet been validated against human coding. Report agreement on texts the prompts were not developed on.

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
| `filter_reason` | the filter's one-line reason for its decision (v3 prompts) |
| `evidence`, `evidence_verbatim` | the sentence the filter quotes as carrying the belief, and whether it occurs verbatim in the chunk (v3 prompts) |
| `tags`, `tag_names` | working classification codes |
| `rejects` | codes the passage explicitly denies (v3 prompts) |
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
│   │   ├── system_v1.txt         ← shared system prompt (v3 layout)
│   │   ├── screen_v2.txt         ← screening task prompt
│   │   ├── filter_v3.txt         ← filter task prompt
│   │   ├── tag_open_v1.txt       ← open-coding task prompt (no code list)
│   │   ├── rate_v1.txt           ← rating task prompt (step 5)
│   │   ├── tag_v3.txt            ← tagging task prompt (working classification)
│   │   ├── screen_v1.txt         ← original screening prompt
│   │   ├── filter_v2.txt         ← original filter prompt
│   │   └── tag_v2.txt            ← original tagging prompt
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
