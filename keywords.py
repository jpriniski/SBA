import re
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from seed_topics import SEED_TOPICS, DOMAIN_LABELS

# Protocol §4 tier 1–2 keywords (stemmed where marked with *)
TIER1 = [
    ("suffer",    True),   # stemmed: suffer, suffers, suffering, suffered
    ("pain",      True),
    ("hardship",  False),
    ("adversity", False),
]
TIER2 = [
    ("affliction",  False),
    ("misery",      False),
    ("anguish",     False),
    ("agony",       False),
    ("torment",     False),
    ("tribulation", False),
    ("ordeal",      False),
    ("distress",    False),
]

# Seed word → construct name lookup (secondary annotation only)
SEED_WORD_TO_CONSTRUCT: dict[str, str] = {}
for construct_words, construct_name in zip(SEED_TOPICS, DOMAIN_LABELS):
    for word in construct_words:
        SEED_WORD_TO_CONSTRUCT[word.lower()] = construct_name


def _pattern(word, stemmed):
    stem = re.escape(word)
    return re.compile(r'\b' + stem + (r'\w*' if stemmed else r'') + r'\b', re.IGNORECASE)


TIER1_PATTERNS = [(_pattern(w, s), w, 1) for w, s in TIER1]
TIER2_PATTERNS = [(_pattern(w, s), w, 2) for w, s in TIER2]
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
