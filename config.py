import os

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
TEXTS_DIR  = os.path.join(BASE_DIR, "..", "texts", "open access")
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

SCREEN_PROMPT_VERSION = "screen_v1"
FILTER_PROMPT_VERSION = "filter_v2"
TAG_PROMPT_VERSION    = "tag_v2"
