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
RESULTS_DIR = os.path.join(BASE_DIR, "results")
PROMPTS_DIR = os.path.join(BASE_DIR, "prompts")

# Pilot subset — comment out PILOT_TEXTS to run all texts in TEXTS_DIR
PILOT_TEXTS = [
    "Dante_Alighieri_Inferno.txt",
]

CHUNK_WORDS   = 1000
OVERLAP_WORDS = 200

SCREEN_MODEL = "claude-haiku-4-5-20251001"
FILTER_MODEL = "claude-haiku-4-5-20251001"
TAG_MODEL    = "claude-sonnet-4-6"
RATE_MODEL   = "claude-sonnet-4-6"

# Prompt versions (files in prompts/). Never edit a prompt in place: add a new
# file and change the version here.
#   v3 layout: one shared system prompt + one task prompt per step. Task prompts
#              contain <<PASSAGE>> and are sent as the user message.
#   To re-run the original pilot set: screen_v1 / filter_v2 / tag_v2. Those files
#   are sent as the system message and SYSTEM_PROMPT_VERSION is not used.
#
# Tag step, two modes:
#   tag_open_v1  open coding. No code list; the tagger names each belief it finds
#                (label, definition, evidence). Output: results/open_codes.csv, one
#                row per belief. Use this first, to build the classification.
#   tag_v3       deductive coding against WORKING_CLASSIFICATION in pipeline.py.
#                Use once a classification has been built from the open codes.
SYSTEM_PROMPT_VERSION = "system_v1"
SCREEN_PROMPT_VERSION = "screen_v2"
FILTER_PROMPT_VERSION = "filter_v3"
TAG_PROMPT_VERSION    = "tag_open_v1"

# Step 5: place each open-coded belief in an area (BELIEF_AREAS in pipeline.py)
# and rate it on evaluation, inevitability and intertwinement (1-5, blank = no
# position). Runs only after tag_open_v1. Set to None to skip the step; areas
# and ratings are then left blank.
RATE_PROMPT_VERSION   = "rate_v1"
