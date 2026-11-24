import re
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
try:
    from seed_topics import SEED_TOPICS, DOMAIN_LABELS
    SEED_TOPICS_LOADED = True
except ImportError:
    # seed_topics.py (the seed words for the nine construct dimensions) is not in
    # the repo. Without it the pipeline still runs; `seed_constructs` is left blank.
    SEED_TOPICS, DOMAIN_LABELS = [], []
    SEED_TOPICS_LOADED = False

# Protocol §4 tier 1–2 keywords: (label, regex for the word forms that count).
# Protocol §4 calls for case-insensitive stemmed patterns. v1 stemmed only
# "suffer" and "pain", so inflected forms such as "tormented", "miserable" and
# "hardships" were missed, and "pain" + any suffix also matched "painted".
# The labels are unchanged, so the archive's `keyword` column stays comparable.
# Bump KEYWORDS_VERSION whenever a pattern changes; it is written to run_log.json.
KEYWORDS_VERSION = "keywords_v2"

TIER1 = [
    ("suffer",    r"suffer\w*"),                    # suffer, suffers, suffering, suffered, sufferer
    ("pain",      r"pain(?:s|ed|ful|fully)?"),      # not paint, painted, painter
    ("hardship",  r"hardships?"),
    ("adversity", r"adversit(?:y|ies)"),
]
TIER2 = [
    ("affliction",  r"afflict\w*"),                 # afflict, afflicted, affliction(s)
    ("misery",      r"miser(?:y|ies|able|ably)"),   # not miser, miserly
    ("anguish",     r"anguish\w*"),                 # anguish, anguished
    ("agony",       r"agon(?:y|ies|i[sz](?:e|ed|es|ing))"),  # agony, agonies, agonize(d), agonizing; not agonist
    ("torment",     r"torment\w*"),                 # torment(s), tormented, tormentor
    ("tribulation", r"tribulations?"),
    ("ordeal",      r"ordeals?"),
    ("distress",    r"distress\w*"),                # distress, distressed, distressing
]

# Seed word → construct name lookup (secondary annotation only)
SEED_WORD_TO_CONSTRUCT: dict[str, str] = {}
for construct_words, construct_name in zip(SEED_TOPICS, DOMAIN_LABELS):
    for word in construct_words:
        SEED_WORD_TO_CONSTRUCT[word.lower()] = construct_name


def _pattern(forms):
    return re.compile(r'\b(?:' + forms + r')\b', re.IGNORECASE)


TIER1_PATTERNS = [(_pattern(f), w, 1) for w, f in TIER1]
TIER2_PATTERNS = [(_pattern(f), w, 2) for w, f in TIER2]
ALL_PATTERNS   = TIER1_PATTERNS + TIER2_PATTERNS


def keyword_scan(text: str):
    """
    Returns:
        keyword_hits  — list of {word, tier} for each matched keyword
        seed_matches  — sorted list of construct names matched by seed words
    """
    keyword_hits = []
    seen_keywords = set()

    for pattern, word, tier in ALL_PATTERNS:
        if pattern.search(text) and word not in seen_keywords:
            keyword_hits.append({'word': word, 'tier': tier})
            seen_keywords.add(word)

    text_words = set(re.findall(r'\b\w+\b', text.lower()))
    seed_matches = sorted({
        SEED_WORD_TO_CONSTRUCT[w]
        for w in text_words
        if w in SEED_WORD_TO_CONSTRUCT
    })

    return keyword_hits, seed_matches
