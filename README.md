# Suffering Beliefs Annotation Pipeline

**Project:** Suffering Beliefs Framework (SBF), SHARE Lab, Duke University (named SCF Lab in the protocol)
**Grant:** John Templeton Foundation FR#63879
**Protocol:** `SBF_AI_Text_Analysis_Protocol_v2.docx` (August 2026, draft)

The protocol is a draft. It describes an earlier design, with a filter step and a fixed list of seven codes, and it does not bind the pipeline. This README describes the pipeline as it runs now; the protocol and the coding manual will be revised to match what the pilot runs support.

---

## Status (24 November 2026)

| Setting | Current value |
|---|---|
| Coding approach | Open coding: no code list and no topic list is given to the model |
| System prompt | `system_v2` |
| Screen (step 3a) | `screen_v2`, Claude Haiku 4.5 |
| Filter (step 3b) | **off** (`USE_FILTER = False`) |
| Open coding (step 4) | `tag_open_v4`, Claude Sonnet 4.6 |
| Areas and ratings (step 5) | `rate_v2`, Claude Sonnet 4.6 |
| Provider | OpenRouter, restricted to Anthropic, data collection denied |
| Passage selection | the screen decides; keywords are recorded but do not select a passage (`KEYWORD_SELECTS = False`, from run 6) |
| Keywords | `keywords_v2` |

Runs so far:

| Run | Date | Texts | Prompts (system / open coding / ratings) | Filter | Result |
|---|---|---|---|---|---|
| Original pilot | 10 Nov | Inferno | none / `tag_v2` / none | on | 25 archived passages, fixed code list |
| Test passages | 18 Nov | 8 short constructed passages | `system_v1` / `tag_open_v1` / `rate_v1` | on | 8 of 8 coded as expected |
| Run 2 | 18 Nov | Tao Te Ching, The Metamorphosis, two talk transcripts | `system_v1` / `tag_open_v1` / `rate_v1` | on | 4 of 42 candidate passages passed the filter; 26 beliefs; $0.47 |
| Run 3 | 18 Nov | same four | `system_v1` / `tag_open_v2` / `rate_v1` | off | 42 of 42 coded; 136 beliefs, 74 from The Metamorphosis; $1.49 |
| Run 4 | 24 Nov | same four | `system_v2` / `tag_open_v3` / `rate_v2` | off | 42 of 42 coded; 93 stated beliefs, 39 from The Metamorphosis; 76 depicted themes, all from The Metamorphosis; $1.59 |
| Run 5 | 24 Nov | same four | `system_v2` / `tag_open_v4` / `rate_v2` | off | 39 of 42 candidates yielded something; 67 stated beliefs, 20 from The Metamorphosis; 22 depicted themes, all from The Metamorphosis; $1.43 |
| Run 6 | not yet run | same four | as run 5, with keywords recorded only | off | |

Run 2 showed the filter was too strict. Run 3 showed open coding without the filter was too loose: no passage came back empty, and morals were read into the fiction. Run 4 separated stated beliefs from depicted themes to correct this.

| Text | Stated, run 3 | Stated, run 4 | Stated, run 5 | Depicted, run 3 | Depicted, run 4 | Depicted, run 5 |
|---|---|---|---|---|---|---|
| Tao Te Ching | 35 | 30 | 23 | 1 | 0 | 0 |
| Brené Brown | 22 | 19 | 19 | 0 | 0 | 0 |
| Andrew Solomon | 4 | 5 | 5 | 0 | 0 | 0 |
| The Metamorphosis | 31 | 39 | 20 | 43 | 76 | 22 |

Run 3's counts treat its `depicts` entries as depicted themes.

**What run 4 showed.** The split works for the texts that argue directly and does not yet work for fiction.

- The Tao Te Ching and the two talks kept their yields and produced no depicted themes, as intended. Most of their stated beliefs are maxims or generalizations in the speaker's own words.
- The Metamorphosis did not improve. Stated beliefs rose from 31 to 39, and 25 of its 26 coded passages still yielded at least one. Read against the passages, about 8 of the 39 are general claims in a speaker's own words ("we people in commerce ... simply have to overcome it"). About 27 generalize a remark about one situation or a sentence of narration, and 4 repeat a belief from the overlap between chunks.
- Depicted themes reached the limit of three in 24 of the 26 Kafka passages. The limit acted as a target.
- 41 of the 42 candidate passages yielded a stated belief. The coding step did not return an empty answer for a passage that is about suffering but states no belief.
- All three beliefs coded `denies` were malformed: the definition already gave the passage's own view, so the stance reversed its meaning.
- 29 of 169 evidence quotes were not word for word. Of these, 13 joined separate parts with an ellipsis, 14 differed from the passage only in punctuation or capital letters, and 2 left words out.

**What run 5 changed (`tag_open_v4`).**
- A stated belief must be general in the speaker's own words. A remark about one person's, one family's or one character's situation is not a stated belief, and neither is narration of what a character did or felt.
- The limit of three depicted themes is gone. Most passages are expected to have none, and no more than two are recorded.
- The prompt says outright that a passage can be about suffering and state no belief, and gives an example of an empty answer.
- A check on every `denies`, and a rule against leaving words out of the middle of an evidence quote.

**What run 5 showed.** The stricter prompt roughly halved the output from fiction and left the other texts close to where they were.

- The Metamorphosis: stated beliefs fell from 39 to 20 and depicted themes from 76 to 22. Twenty passages have one theme, one has two, and none reached a limit.
- Empty answers now occur. Three of the 42 candidate passages yielded nothing, and a further 11 Kafka passages yielded a depicted theme and no stated belief.
- The rule on general wording is applied only in part. Of the 20 Kafka stated beliefs, about 8 are general in a speaker's own words and about 12 still rest on a remark about one situation ("Please, don't make my parents suffer!").
- The Tao Te Ching fell from 30 to 23, and the two talks kept their counts. Between runs 4 and 5 the model did not always pick the same sentences from the same passage, so counts for a text should be read as approximate.
- No belief was coded `denies`. The three malformed ones are gone, and the passage that rejects the idea that seeking help is weakness is now coded as endorsing the opposite.
- 12 of 89 evidence quotes were not word for word, against 29 of 169 in run 4.

Still open: particular remarks in fiction that are coded as stated beliefs, and repeats from the overlap between chunks.

None of the prompts has been validated against human coding.

---

## What we are building

Across cultures and history, people hold deep, often implicit beliefs about why suffering exists and what it means. These beliefs shape how people cope, seek help, and make sense of their own pain.

The **Suffering Beliefs Framework** is a systematic effort to identify, catalog, and study these beliefs across a broad corpus of philosophical, religious, literary, and testimonial texts, including contemporary spoken sources such as talks, podcasts and interviews. The core research question: *what are the recurring belief structures humans invoke to make sense of suffering, and what are their psychological and cultural dimensions?*

This pipeline is the data extraction step. It uses large language models to scan texts, find passages that state a general belief about suffering, and name each belief in its own terms. Human researchers then validate the output, consolidate it into a classification, and use it to write items for the Suffering Beliefs Scale.

**What goes in:** a set of texts (open-access corpus, eventually about 37 sources, plus texts kept locally).

**What comes out, per run:**
- one row per **stated belief**: label, definition, stance, evidence quote, area, three ratings
- one row per **depicted theme**: what a story shows about suffering without anyone stating it
- one row per coded passage, and a readable file per text showing every decision
- after clustering: candidate themes and a master workbook for framework generation

---

## Pipeline overview

The pipeline runs in five steps, each leaving an audit trail. Two further scripts group the beliefs into candidate themes and build the master file.

### Step 1: Preprocessing
Each text is cleaned (Gutenberg headers stripped, line endings normalized) and split into overlapping **1,000-word chunks** with a 200-word overlap. The overlap keeps a belief near a chunk boundary from being cut in two. A trailing fragment under 50 words is dropped. Each chunk gets a stable ID such as `laozi_tao_te_ching_c0012`.

### Step 2: Keyword scan
Every chunk is scanned for the protocol's tier 1 and tier 2 keywords (§4):
- **Tier 1:** suffer\*, pain, hardship, adversity
- **Tier 2:** affliction, misery, anguish, agony, torment, tribulation, ordeal, distress

Inflected forms count (tormented, miserable, hardships); "pain" does not match "painted". The list has a version (`keywords_v2`) recorded in `run_log.json`.

From run 6 the keywords are **recorded only** (`KEYWORD_SELECTS = False` in `config.py`): they are noted for every chunk and reported, and the screen in step 3a decides which chunks are coded. Up to run 5 a keyword hit also sent a chunk to coding by itself.

### Step 3a: Screening (Claude Haiku)
*Every* chunk is screened with a yes/no question: could any part of it plausibly be read as stating, implying or disputing a general claim about suffering? The screen favors recall: when unsure, YES.

A chunk is a **candidate** if it screens YES. Candidates with no keyword are *contextual* passages, the ones a keyword search alone would have missed: 18 of the 42 candidates in runs 3 to 5.

The keyword scan was dropped as a selector because it added almost nothing once every chunk was screened. In run 4, 23 of the 24 keyword-hit chunks also screened YES, and the one passage that entered on its keyword alone gave a weak belief. The risk is that the screen misses a passage a keyword would have caught. `run_log.json` therefore counts the keyword-hit chunks the screen turned down (`keyword_screen_no`), and the labeled files show them, so they can be checked by hand. Set `KEYWORD_SELECTS = True` to restore the earlier rule.

### Step 3b: Filter (Claude Haiku), currently off
The filter asks whether a candidate passage expresses a general belief about suffering, and answers YES, MAYBE or NO. It is switched off (`USE_FILTER = False` in `config.py`) because in run 2 it passed only 4 of 42 candidates, never answered MAYBE, rejected all of the fiction, and treated shame and vulnerability as outside suffering.

With the filter off, every candidate goes to step 4, which makes the same judgment itself and may return nothing. The prompt (`filter_v3`) stays in the repo; whether to rewrite it more leniently for the full corpus, where cost matters more, is an open question.

### Step 4: Open coding (Claude Sonnet)
The model is given **no code list and no list of topics**, so that beliefs nobody anticipated can surface. It records what the passage says about suffering in two separate lists (`tag_open_v4`).

**Stated beliefs** are general claims that the author, the narrator or a speaker actually puts into words. The model must be able to quote one continuous stretch of the passage in which the claim is made, and the generality must be in the speaker's own words: the stretch speaks of people in general, or it is a maxim or a rule. A remark about one person's situation is not a stated belief, however easy it is to draw a lesson from it. For each belief the model returns:
- a two-to-four-word **label** and a one-sentence **definition** in everyday words
- a verbatim **evidence** quote of at most 40 words
- a **stance**: `endorses`, `denies` (the belief is stated in its positive form and the stance carries the rejection), `mentions` (reported as something people say, no side taken), or `conditional` (held only under a stated condition)

These go to `open_codes.csv`, one row per belief.

**Depicted themes** are what a story, poem or anecdote shows about suffering through its events, when no one in it says so. They are the model's reading. Most passages have none and no more than two are recorded. They are written to `depicted_themes.csv` and never mixed into `open_codes.csv`.

Either list may be empty, and a passage can be about suffering throughout and still state no belief. The model also reports its **confidence** (HIGH, MEDIUM, LOW) that an independent coder would produce the same two lists.

What counts as a suffering belief is defined once, in the system prompt: the lab's definition of suffering, and five tests (claim, generality, individual difference, plain language, broad relevance) applied to each claim separately.

### Step 5: Areas and ratings (Claude Sonnet)
Only after the beliefs have been named are they placed on a fixed grid (`rate_v2`), one call per passage.

Each stated belief and each depicted theme gets one **area**. The grid (`BELIEF_AREAS` in `pipeline.py`) follows the qualitative interview guide, so the text and interview streams share one grid:

`understanding`, `prevalence`, `causes`, `consequences`, `controllability`, `personal_response`, `interpersonal_response`, `overall_evaluation`, plus `meaning_fairness` (prominent in the texts, absent from the guide) and `other`.

A belief that fits no area is coded `other`, with a few words in `area_note`; those rows show where the grid is incomplete. The grid is applied after open coding on purpose: it describes the beliefs that were found and plays no part in finding or naming them.

Each belief the passage endorses or holds conditionally is also rated 1-5 on three dimensions. A blank means the belief takes no position.

| Rating | 1 | 5 |
|--------|---|---|
| `rating_evaluation` | suffering is purely harmful | suffering can enrich a life |
| `rating_inevitability` | avoidable or exceptional | an inevitable part of every life |
| `rating_intertwinement` | separate from and opposed to what is good in life | bound up with what people care about most |

Denied beliefs, mentioned beliefs and depicted themes get an area but no ratings. Set `RATE_PROMPT_VERSION = None` in `config.py` to skip the step.

### After the run: candidate themes
`python cluster_open_codes.py` groups the stated beliefs by the similarity of their definitions. It first sets aside duplicates that come from the overlap between chunks. Every definition is about suffering, so their vectors share a large common part; the script removes it before grouping, because otherwise most beliefs fall into one very large cluster (`--no-centre` turns this off). Use `--scan` to see how many clusters different thresholds give, `--threshold` to choose one, and `--k 30` to ask for a fixed number.

The clusters are a first draft for the team to name, merge and split. They are not the classification.

### After the run: master file
`python build_master.py` writes `framework_master.xlsx`, the summary file for framework generation:

| Sheet | Contents |
|---|---|
| Themes | one row per candidate theme: definition, keywords, area, number of beliefs and texts, stance counts, mean ratings, example quotes, number of depicted themes that support it, and empty columns for the team's name, decision and notes |
| Coverage | stated beliefs by area and text |
| Depicted | each depicted theme with the stated theme it is closest to |
| Beliefs | every stated belief with its theme |
| About | how the file was built and what to fill in |

Counts and means are formulas, so they update when a belief is moved to another theme. A `stream` column marks where each belief comes from, so beliefs from the interviews, surveys and reviews can be appended later.

---

## Prompts

Every call has two parts:

- **System prompt** (`system_v2`), shared by all steps: the coder's role, the lab's definition of suffering, the five tests, the recurring judgment calls, guidance for spoken and contemporary sources, the rule to code from the page and not from prior knowledge of the work, and JSON-only output.
- **Task prompt** (one per step), sent as the user message with the passage filled in at `<<PASSAGE>>`.

Prompt files, with the ones in use marked:

| File | Step | Status |
|---|---|---|
| `system_v2` | all | **in use** |
| `screen_v2` | 3a | **in use** |
| `tag_open_v4` | 4 | **in use**: stated beliefs and depicted themes as two lists, with the stricter rules listed under Status |
| `rate_v2` | 5 | **in use** |
| `filter_v3` | 3b | not in use (filter off) |
| `tag_open_v3` | 4 | used by run 4 |
| `system_v1`, `tag_open_v1`, `tag_open_v2`, `rate_v1` | | used by runs 2 and 3 |
| `tag_v3` | 4 | deductive coding against a fixed code list; for use once a classification exists |
| `screen_v1`, `filter_v2`, `tag_v2` | | the original pilot's prompts |

The versions are set in `config.py`. The original prompts still run unchanged: a prompt file without `<<PASSAGE>>` is sent as the system message with the passage as the user message.

The seven-code working classification and the nine construct dimensions remain in `pipeline.py` only for `tag_v2` and `tag_v3`. They are not used in open coding and appear in no current prompt.

---

## Exploring results: the viewer

The annotation viewer (`viewer.html`) is a self-contained browser tool for exploring one run. No server needed; open it directly. It reads the open-coding outputs. For a run that used the fixed code list (`tag_v2`, `tag_v3`), use `viewer_legacy.html`, which is the earlier viewer unchanged.

### Loading data
1. Open `viewer.html` in any modern browser
2. Click **Open run folder** and choose the run's folder, for example `results/run5_general_wording` (or drop the folder onto the page)

The viewer picks up `open_codes.csv`, `depicted_themes.csv`, `pilot_archive.csv`, `run_log.json` and every file in `labeled/`. Any subset works. Without the labeled files, passages show only their first 300 characters and passages where nothing was found are not listed.

### What the viewer shows

**Summary charts (left sidebar), each clickable as a filter:**
- **Passages**: with stated beliefs, with depicted themes only, coded with nothing found, not coded
- **Texts**: passages per text
- **Belief areas**: stated beliefs and depicted themes by step 5 area
- **Stance**: endorses, denies, mentions, conditional, and depicted theme
- **Ratings**: distribution of the three 1-5 ratings over stated beliefs, including beliefs with no rating

**Passage cards (Passages view):**
- Stated beliefs: label, definition, stance, area, ratings, evidence quote and the basis for the ratings
- Depicted themes, listed separately and marked as the coder's reading
- A flag on any evidence quote not found word for word in the passage
- The full passage with the evidence quotes marked, and the two passages before and after it

**Beliefs view:** one row per stated belief or depicted theme, sortable by column. Click a row to go to its passage.

The charts cross-filter: each shows its distribution within the other current selections. Selecting one text and then the area "causes" answers "what does this text say about why people suffer?". The search box narrows cards, table and charts together.

---

## Quick start

**Requirements:** Python 3.9+ and an API key for the provider set in `config.py`. The pipeline itself needs no extra packages with OpenRouter. Clustering and the master file need:

```bash
pip install pandas scikit-learn sentence-transformers openpyxl
```

**To run:**

```bash
# From the folder that holds pipeline.py:
export OPENROUTER_API_KEY="sk-or-..."     # lasts for this Terminal window only
python try_passages.py                    # a few short test passages first
python pipeline.py                        # the texts listed in PILOT_TEXTS
python cluster_open_codes.py --scan       # see how many themes each threshold gives
python cluster_open_codes.py              # group the stated beliefs
python build_master.py                    # write framework_master.xlsx
```

Never write the key into a file in this folder: the repository is public.

Results land in `results/<RUN_NAME>/`. `RUN_NAME` is set in `config.py`; change it for each run so nothing is overwritten. Then open `viewer.html` and open that run's folder.

**Testing single passages.** `try_passages.py` sends short passages (a sentence, a social-media post) through the same steps without chunking. It reads `test_passages.txt`, where passages are separated by a line containing only `---` and a line starting with `#` is a note on the expected coding. Results are printed and saved to `results/test_passages_output.json`.

**Texts that cannot be shared.** Put copyrighted transcripts and licensed translations in `texts/local/`. Git ignores that folder and the run folders under `results/`, because the outputs contain the full text of the sources. A file named in `PILOT_TEXTS` is looked for in the main texts folder first, then in `texts/local/`.

**Provider.** `PROVIDER` in `config.py` selects where the calls go:

- `"openrouter"`: OpenRouter, with `OPENROUTER_API_KEY`. OpenRouter can hand a request to any of several companies hosting the same model, so `OPENROUTER_ROUTING` pins it: Anthropic only, no fallback to another host, and no hosts that keep or train on the text. The host and model that actually answered are written to `run_log.json` (`served_by`), as is the cost.
- `"anthropic"`: Anthropic's API directly, with `ANTHROPIC_API_KEY` and `pip install anthropic`.

The models are the same under both; only their names differ. Report the provider in the methods, since a run through OpenRouter and a run through Anthropic are not guaranteed to be identical.

**To change which texts are processed:** edit `PILOT_TEXTS` in `config.py`. Comment it out entirely to run all texts in the main texts folder.

**To change models:** edit `MODELS` in `config.py`.

**Cost.** With the filter off, the four pilot texts (42,500 words, 47 chunks) cost $1.49 in run 3, $1.59 in run 4 and $1.43 in run 5, or about $3.40 to $3.75 per 100,000 words. Steps 4 and 5 on Sonnet account for most of it.

---

## Outputs

All in `results/<RUN_NAME>/`.

### `open_codes.csv`
One row per **stated belief**. This is the file that feeds clustering and the item pool.

| Column | What it contains |
|--------|-----------------|
| `chunk_id`, `source`, `belief_n` | where the belief came from |
| `label`, `definition` | the belief in the model's words |
| `stance` | `endorses`, `denies`, `mentions`, `conditional` |
| `evidence`, `evidence_verbatim` | the quote, and whether it occurs word for word in the chunk |
| `area`, `area_note` | step 5 area |
| `rating_evaluation`, `rating_inevitability`, `rating_intertwinement`, `rating_reason` | step 5 ratings and their basis |
| `confidence` | HIGH / MEDIUM / LOW, for the passage |
| `consolidated_code`, `human_evaluation`, `human_inevitability`, `human_intertwinement`, `coder_notes` | *empty, for the research team* |
| `model_*`, `prompt_*`, `run_date` | provenance |

### `depicted_themes.csv`
One row per **depicted theme**: `label`, `definition`, `evidence`, `area`, and an empty `reviewer_decision`. No stance and no ratings. Written only when at least one theme is found.

### `pilot_archive.csv`
One row per **passage** in which step 4 found at least one stated belief or depicted theme (with the filter on: one row per passage the filter passed). Use it to check passage selection and to read beliefs in context.

| Column | What it contains |
|--------|-----------------|
| `chunk_id`, `source` | where the passage came from |
| `keyword`, `keyword_tier`, `filter_trigger` | the keywords it contains, and whether it has one (`keyword`) or none (`contextual`) |
| `screen`, `filter_decision` | step 3 results; `filter_decision` is `SKIPPED` when the filter is off |
| `open_labels`, `depicted_labels` | labels of the passage's stated beliefs and depicted themes |
| `constructs` | the areas of the passage's beliefs |
| `confidence` | HIGH / MEDIUM / LOW |
| `text_excerpt` | first 300 characters of the passage |
| `core_belief`, `filter_reason`, `evidence` | filled only when the filter is on |
| `tags`, `tag_names`, `rejects`, `new_candidate_*` | filled only by the fixed-code prompts (`tag_v2`, `tag_v3`) |
| `human_decision`, `human_tags`, `coder_notes`, `coder_id`, `date_coded`, `resolved_tag` | *empty, for RA validation* |
| `model_*`, `prompt_*`, `run_date` | provenance |

### `labeled/<source>_labeled.txt`
One readable file per text, showing **every** chunk with its full text and its decisions: keywords, screen result, each stated belief with stance, area and ratings, each depicted theme, or `OPEN CODE: none found`. This is the only output that lists passages where nothing was found and passages that were not selected.

### `run_log.json`
Provider, routing, model names, prompt versions, keyword version, whether keywords selected passages, whether the filter ran, run date, counts per text (including keyword-hit chunks the screen turned down), token usage, cost, the host that answered, and any errors. Required for the methods report.

### After clustering
`open_code_clusters.csv` (every belief with its cluster), `cluster_summary.csv` (one row per cluster), `cluster_meta.json` (how the grouping was done) and `framework_master.xlsx`.

---

## Human validation

Not yet designed for the current pipeline. The procedure in protocol §6 was written for the filter and the fixed code list (all MAYBE passages, all new-candidate proposals, a 20% sample of confident YES passages), and none of those categories exists under open coding.

What is in place:
- Passages the model marks LOW confidence are meant for human review.
- `open_codes.csv` has empty columns for a human rating on each of the three dimensions; `depicted_themes.csv` has an empty reviewer decision; `pilot_archive.csv` has the original RA columns.
- The labeled files show every chunk, so a coder can check passages the model coded as empty.

Still to decide: the sample of passages to be coded by hand, and the agreement statistics for belief presence, stance, area and ratings. Report agreement on texts the prompts were not developed on.

---

## File structure

```
SBA/
├── pipeline.py                 ← main script (run this)
├── config.py                   ← settings: texts, run name, provider, models, prompt versions
├── preprocess.py               ← text cleaning and chunking
├── keywords.py                 ← keyword scan
├── try_passages.py             ← test the prompts on short passages
├── test_passages.txt           ← eight test passages with expected coding
├── cluster_open_codes.py       ← group stated beliefs into candidate themes
├── build_master.py             ← write framework_master.xlsx
├── viewer.html                 ← explore a run in the browser (open coding)
├── viewer_legacy.html          ← earlier viewer, for runs with the fixed code list
├── prompts/                    ← versioned prompt files (see "Prompts")
├── texts/
│   ├── open acess/             ← public-domain texts (the folder name is spelled this way)
│   └── local/                  ← texts that cannot be shared; ignored by Git
└── results/
    ├── pilot_archive.csv, run_log.json, labeled/   ← the original Inferno pilot
    └── <RUN_NAME>/             ← one folder per run; ignored by Git
```

---

## Reproducibility

- Prompts are **versioned files** in `prompts/`. Never edit a prompt that a run has used: create a new version file and change the version in `config.py`. The old version stays on disk.
- `run_log.json` records what is needed to repeat a run.
- All calls request **temperature 0**. `run_log.json` records whether the setting was applied.
- Passages are extracted by string slicing from source files, with no retyping or paraphrasing (quote-fidelity control, protocol §5 Step 2). Evidence quotes are checked against the passage, ignoring only spacing and typographic quotes and dashes.
- Each run writes to its own folder, so earlier results are never overwritten.
