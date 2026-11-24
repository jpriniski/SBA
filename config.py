import os

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))


def _first_existing(*paths):
    for path in paths:
        if os.path.isdir(path):
            return path
    return paths[0]


# The GitHub repo keeps the texts beside the scripts, in "texts/open acess"
# (spelled that way). The original layout had them one level up, in
# "texts/open access". Use whichever exists.
TEXTS_DIR  = _first_existing(
    os.path.join(BASE_DIR, "texts", "open access"),
    os.path.join(BASE_DIR, "texts", "open acess"),
    os.path.join(BASE_DIR, "..", "texts", "open access"),
)

# Texts that must stay off GitHub (copyrighted transcripts, licensed translations)
# go in texts/local/, which Git ignores. A file named in PILOT_TEXTS is looked
# for in TEXTS_DIR first, then here.
LOCAL_TEXTS_DIR = os.path.join(BASE_DIR, "texts", "local")

# Each run writes to results/<RUN_NAME>/, so an earlier run is never overwritten.
# Change the name for every new run. Run folders are ignored by Git because the
# archive and labeled files contain the full text of the sources.
# Set to "" to write straight into results/, as the original pipeline did.
RUN_NAME    = "run6_screen_selects"
RESULTS_DIR = os.path.join(BASE_DIR, "results", RUN_NAME) if RUN_NAME else os.path.join(BASE_DIR, "results")
PROMPTS_DIR = os.path.join(BASE_DIR, "prompts")

# Pilot subset — comment out PILOT_TEXTS to run all texts in TEXTS_DIR
PILOT_TEXTS = [
    "Laozi_Tao_Te_Ching.txt",                                          # Legge translation, Project Gutenberg #216
    "Franz_Kafka_The_Metamorphosis.txt",                               # Wyllie translation, Project Gutenberg #5200
    "Brene_Brown_The_Power_of_Vulnerability.txt",                      # TEDxHouston 2010 transcript
    "Andrew_Solomon_Why_Is_It_So_Hard_To_Talk_About_Depression.txt",   # NPR TED Radio Hour transcript
    # "Dante_Alighieri_Inferno.txt",
]

CHUNK_WORDS   = 1000
OVERLAP_WORDS = 200

# ── API provider ─────────────────────────────────────────────────────────────
#   "openrouter"  OpenRouter. Needs OPENROUTER_API_KEY; no extra Python package.
#   "anthropic"   Anthropic's API directly. Needs ANTHROPIC_API_KEY and
#                 `pip install anthropic`.
PROVIDER = "openrouter"

# The same two models under each provider's naming.
MODELS = {
    "anthropic":  {"small": "claude-haiku-4-5-20251001",  "large": "claude-sonnet-4-6"},
    "openrouter": {"small": "anthropic/claude-haiku-4.5", "large": "anthropic/claude-sonnet-4.6"},
}
SCREEN_MODEL = MODELS[PROVIDER]["small"]
FILTER_MODEL = MODELS[PROVIDER]["small"]
TAG_MODEL    = MODELS[PROVIDER]["large"]
RATE_MODEL   = MODELS[PROVIDER]["large"]

# OpenRouter can pass a request to any of several companies that host the same
# model. These settings (sent with every request) keep that fixed:
#   only             : the request goes to Anthropic itself, not another host
#   allow_fallbacks  : if Anthropic is unavailable, fail; do not switch host
#   data_collection  : refuse hosts that keep or train on the text (protocol §2)
# The host and model that actually answered are recorded in run_log.json.
OPENROUTER_ROUTING = {
    "only": ["anthropic"],
    "allow_fallbacks": False,
    "data_collection": "deny",
}

# Prompt versions (files in prompts/). Never edit a prompt in place: add a new
# file and change the version here.
#   v3 layout: one shared system prompt + one task prompt per step. Task prompts
#              contain <<PASSAGE>> and are sent as the user message.
#   To re-run the original pilot set: screen_v1 / filter_v2 / tag_v2. Those files
#   are sent as the system message and SYSTEM_PROMPT_VERSION is not used.
#
# Tag step, two modes:
#   tag_open_v4  open coding, current. Two lists: stated beliefs (someone in the
#                passage makes the general claim, in general words) and depicted
#                themes (a story shows it, nobody states it). Themes go to
#                depicted_themes.csv and never into open_codes.csv. Tighter than
#                v3: a remark about one person's situation is not a stated belief,
#                at most two themes per passage, and an empty answer is expected
#                for many passages. Use with system_v2 and rate_v2.
#   tag_open_v3  run 4. First version with the two lists.
#   tag_open_v2  run 3. One list, for passages that have not been through the filter.
#   tag_open_v1  run 2. One list; the tagger names each belief it finds.
#   tag_v3       deductive coding against WORKING_CLASSIFICATION in pipeline.py.
#                Use once a classification has been built from the open codes.
SYSTEM_PROMPT_VERSION = "system_v2"
SCREEN_PROMPT_VERSION = "screen_v2"
FILTER_PROMPT_VERSION = "filter_v3"
TAG_PROMPT_VERSION    = "tag_open_v4"

# Step 3b, the filter. In run 2 it passed only 4 of 42 candidate chunks and never
# answered MAYBE, so most of the texts were never coded.
#   False : skip it. Every candidate chunk (screened YES; see KEYWORD_SELECTS) goes
#           straight to the tag step, which can itself answer that the passage states no belief
#           (tag_open_v2 or later). A chunk is archived if the tag step finds at
#           least one stated belief or depicted theme.
#   True  : run the filter as before; only YES and MAYBE chunks are tagged.
USE_FILTER = False

# Step 2, the keyword scan. Every chunk is screened in step 3a, so the scan is not
# needed to find passages: in run 4, 23 of the 24 keyword-hit chunks also screened
# YES, and the one passage that entered on its keyword alone gave a weak belief.
#   False : keywords are recorded for every chunk but do not select it. A chunk is
#           coded only if the screen says YES. run_log.json counts the keyword-hit
#           chunks the screen turned down, so they can be checked by hand.
#   True  : a keyword hit sends a chunk to coding even when the screen says NO,
#           as in runs 2 to 5.
KEYWORD_SELECTS = False

# Step 5: place each open-coded belief in an area (BELIEF_AREAS in pipeline.py)
# and rate it on evaluation, inevitability and intertwinement (1-5, blank = no
# position). Runs only after an open-coding prompt (tag_open_*). Set to None to
# skip the step; areas and ratings are then left blank.
RATE_PROMPT_VERSION   = "rate_v2"
