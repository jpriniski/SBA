"""
Pilot extraction pipeline — Suffering Beliefs Framework
Steps: preprocess → keyword scan → screen (3a) → filter (3b) → tag (4)
Outputs: results/pilot_archive.csv, results/run_log.json, results/labeled/*.txt
"""

import csv
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import anthropic

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import config
from preprocess import load_and_preprocess
from keywords import keyword_scan, KEYWORDS_VERSION, SEED_TOPICS_LOADED

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# NOT sent to the model in the open-coding pass (tag_open_v1), which has no code
# list. It is filled in only where a tag prompt contains <<CLASSIFICATION>>:
# tag_v2 (the original pilot) and tag_v3 (deductive coding). Replace it with the
# classification built from the open codes before running tag_v3.
WORKING_CLASSIFICATION = """\
1. Punishment/consequence  — Suffering results from wrongdoing or violated order
2. Teacher/growth          — Suffering instructs, refines, builds character
3. Craving/attachment      — Suffering arises from desire, clinging, resisting
4. Shared condition        — Suffering is the universal human lot
5. Call to compassion      — Suffering obligates care and solidarity
6. Acceptance/equanimity   — Suffering is to be met with calm or acceptance
7. Mystery/unknowable      — Suffering's meaning is unknowable to humans
0. None of the above       — propose a new candidate belief"""

# Filled in where a tag prompt contains <<CONSTRUCTS>>: tag_v2 and tag_v3 only.
# The open-coding prompt (tag_open_v1) is given no list of any kind.
CONSTRUCT_DIMENSIONS = """\
- prevalence      : how common or universal suffering is
- controllability : whether suffering can be avoided or controlled
- evaluation      : whether suffering is harmful, beneficial, or mixed
- cause           : what causes suffering (choice, chance, structural factors)
- consequences    : what suffering leads to (growth, decline, transformation)
- meaning         : whether suffering has meaning, purpose, or value
- fairness        : whether suffering is deserved, just, or equitable
- responsibility  : who bears responsibility for suffering
- helpful_responses: how one should respond to suffering"""

# Step 5 grid (rate_v1). Follows the qualitative interview guide's areas, so the
# text and interview streams can be compared on one grid, plus meaning_fairness
# (prominent in the texts, absent from the guide) and other. Assigned AFTER open
# coding, so the grid cannot shape which beliefs are found or how they are named.
BELIEF_AREAS = """\
- understanding          : what suffering is, what counts as suffering, how it shows itself
- prevalence             : how common or expected suffering is in a human life
- causes                 : why people suffer
- consequences           : what suffering does to people
- controllability        : how much control people have over suffering
- personal_response      : how people should respond to their own suffering
- interpersonal_response : how people should respond to the suffering of others
- overall_evaluation     : how suffering should be judged overall (bad, good, mixed)
- meaning_fairness       : whether suffering has a purpose or meaning, and whether it is deserved or just
- other                  : none of the above"""

AREA_NAMES = [line.split(":")[0].strip("- ").strip() for line in BELIEF_AREAS.splitlines()]

# How a passage stands toward a belief (tag_open_v1). Ratings are given only
# where the passage takes the belief's side in some form.
STANCES         = ["endorses", "denies", "mentions", "conditional", "depicts"]
UNRATED_STANCES = {"denies": "denied", "mentions": "mentioned only"}

# Step 5 ratings (rate_v1): 1-5, or blank when the belief takes no position
RATING_DIMENSIONS = ["evaluation", "inevitability", "intertwinement"]

TAG_NAMES = {
    0: "None of the above",
    1: "Punishment/consequence",
    2: "Teacher/growth",
    3: "Craving/attachment",
    4: "Shared condition",
    5: "Call to compassion",
    6: "Acceptance/equanimity",
    7: "Mystery/unknowable",
}

ARCHIVE_FIELDS = [
    "chunk_id", "text_id", "source",
    "keyword", "keyword_tier", "seed_constructs",
    "screen", "filter_trigger",
    "filter_decision", "filter_reason", "core_belief",
    "evidence", "evidence_verbatim",
    "tags", "tag_names", "rejects", "open_labels", "constructs", "confidence",
    "new_candidate_label", "new_candidate_definition",
    "text_excerpt",
    # Human validation (empty — for RAs)
    "human_decision", "human_tags", "human_new_candidate",
    "coder_notes", "coder_id", "date_coded", "resolved_tag",
    # Provenance
    "model_screen", "model_filter", "model_tag",
    "prompt_system", "prompt_screen", "prompt_filter", "prompt_tag",
    "run_date",
]

# One row per belief from the open-coding pass (tag_open_v1): the input to
# classification building. Written to results/open_codes.csv.
OPEN_CODE_FIELDS = [
    "chunk_id", "text_id", "source", "belief_n",
    "label", "definition", "stance", "evidence", "evidence_verbatim",
    "area", "area_note",
    "rating_evaluation", "rating_inevitability", "rating_intertwinement", "rating_reason",
    "confidence", "filter_decision", "core_belief",
    # Consolidation and rating validation (empty — for the research team)
    "consolidated_code",
    "human_evaluation", "human_inevitability", "human_intertwinement",
    "coder_notes",
    # Provenance
    "model_tag", "model_rate", "prompt_system", "prompt_tag", "prompt_rate", "run_date",
]

# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

client = anthropic.Anthropic()


def load_prompt(name: str) -> str:
    path = os.path.join(config.PROMPTS_DIR, f"{name}.txt")
    with open(path) as f:
        return f.read().strip()


# How temperature=0 is sent. Some SDK versions and models no longer take the
# `temperature` argument; the first refusal moves to the next mode and the mode
# in force at the end of the run is written to run_log.json.
TEMPERATURE_MODES = ["temperature=0", "temperature=0 via extra_body",
                     "model default (temperature=0 refused)"]
_temperature_mode = 0


def _create(**kw):
    global _temperature_mode
    while True:
        try:
            if _temperature_mode == 0:
                return client.messages.create(temperature=0, **kw)
            if _temperature_mode == 1:
                return client.messages.create(extra_body={"temperature": 0}, **kw)
            return client.messages.create(**kw)
        except anthropic.RateLimitError:
            raise
        except Exception as e:
            if "temperature" not in str(e).lower() or _temperature_mode == len(TEMPERATURE_MODES) - 1:
                raise
            _temperature_mode += 1
            print(f"    temperature refused ({str(e)[:80]}) — now using: {TEMPERATURE_MODES[_temperature_mode]}")


def call_claude(model: str, system: str, user: str, max_tokens=256, retries=3):
    for attempt in range(retries):
        try:
            msg = _create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return msg.content[0].text, msg.usage
        except anthropic.RateLimitError:
            wait = 2 ** (attempt + 1)
            print(f"    Rate limit — waiting {wait}s")
            time.sleep(wait)
        except Exception as e:
            if attempt == retries - 1:
                print(f"    API error after {retries} attempts: {e}")
            else:
                time.sleep(2 ** attempt)
    return None, None


def parse_json(text: str):
    if text is None:
        return None
    m = re.search(r'\{.*\}', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    return None


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------

_system_prompt = None
_screen_prompt = None
_filter_prompt = None
_tag_prompt    = None
_rate_prompt   = None


def get_system_prompt():
    """Shared system prompt: construct definition and coding rules for every step."""
    global _system_prompt
    if _system_prompt is None:
        _system_prompt = load_prompt(config.SYSTEM_PROMPT_VERSION)
    return _system_prompt


def build_call(prompt: str, passage: str, legacy_user: str, core_belief: str = ""):
    """
    Returns (system, user) for one API call.

    Task prompts (screen_v2, filter_v3, tag_v3 and later) contain <<PASSAGE>>:
    the shared system prompt is the system message and the filled task prompt
    is the user message.

    Earlier prompts (screen_v1, filter_v2, tag_v2) have no <<PASSAGE>>: the
    prompt file is the system message and `legacy_user` is the user message,
    exactly as in the original pipeline, so old runs stay reproducible.
    """
    if "<<PASSAGE>>" not in prompt:
        return prompt, legacy_user
    user = prompt.replace("<<CORE_BELIEF>>", core_belief).replace("<<PASSAGE>>", passage)
    return get_system_prompt(), user


def uses_system_prompt() -> bool:
    return any("<<PASSAGE>>" in p for p in
               (get_screen_prompt(), get_filter_prompt(), get_tag_prompt()))


def is_verbatim(evidence: str, text: str) -> str:
    """Quote-fidelity check on the model's evidence quote: 'yes'/'no', '' if none."""
    if not evidence:
        return ""
    return "yes" if " ".join(evidence.split()) in " ".join(text.split()) else "no"


def get_screen_prompt():
    global _screen_prompt
    if _screen_prompt is None:
        _screen_prompt = load_prompt(config.SCREEN_PROMPT_VERSION)
    return _screen_prompt


def get_filter_prompt():
    global _filter_prompt
    if _filter_prompt is None:
        _filter_prompt = load_prompt(config.FILTER_PROMPT_VERSION)
    return _filter_prompt


def get_tag_prompt():
    global _tag_prompt
    if _tag_prompt is None:
        raw = load_prompt(config.TAG_PROMPT_VERSION)
        _tag_prompt = (raw
                       .replace("<<CLASSIFICATION>>", WORKING_CLASSIFICATION)
                       .replace("<<CONSTRUCTS>>", CONSTRUCT_DIMENSIONS))
    return _tag_prompt


def get_rate_prompt():
    """Step 5 prompt, or None when rating is switched off in config.py."""
    global _rate_prompt
    version = getattr(config, "RATE_PROMPT_VERSION", None)
    if not version:
        return None
    if _rate_prompt is None:
        _rate_prompt = load_prompt(version).replace("<<AREAS>>", BELIEF_AREAS)
    return _rate_prompt


def screen(text: str):
    system, user = build_call(get_screen_prompt(), text, legacy_user=text)
    result, usage = call_claude(config.SCREEN_MODEL, system, user)
    parsed = parse_json(result)
    decision = parsed.get("screen", "ERROR").upper() if parsed else "ERROR"
    return decision, usage


def filter_passage(text: str):
    system, user = build_call(get_filter_prompt(), text, legacy_user=text)
    result, usage = call_claude(config.FILTER_MODEL, system, user, max_tokens=400)
    parsed = parse_json(result)
    extra = {"reason": "", "evidence": ""}          # filter_v3 fields; empty for filter_v2
    if parsed:
        decision    = parsed.get("decision", "ERROR").upper()
        core_belief = parsed.get("core_belief") or ""
        extra = {"reason":   parsed.get("reason") or "",
                 "evidence": parsed.get("evidence") or ""}
    else:
        decision, core_belief = "ERROR", ""
    return decision, core_belief, extra, usage


def clean_beliefs(raw):
    """
    Open-coding output (tag_open_v1): one dict per belief with label, definition,
    stance and evidence. Area and ratings are added by step 5.
    """
    beliefs = []
    for b in raw if isinstance(raw, list) else []:
        if isinstance(b, dict):
            belief = {k: str(b.get(k) or "").strip()
                      for k in ("label", "definition", "stance", "evidence")}
            stance = belief["stance"].lower()
            stance = "endorses" if stance == "asserts" else stance
            belief["stance"] = stance if stance in STANCES else f"INVALID({stance[:20]})"
            belief["area"] = belief["area_note"] = belief["rating_reason"] = ""
            for dim in RATING_DIMENSIONS:
                belief[dim] = ""
            beliefs.append(belief)
    return beliefs


def stance_mark(belief, brackets="()"):
    """' (denied)' / ' (mentioned only)' for beliefs the passage does not side with, else ''."""
    word = UNRATED_STANCES.get(belief["stance"])
    return f" {brackets[0]}{word}{brackets[1]}" if word else ""


def belief_areas(beliefs):
    """Passage-level list for the archive's `constructs` column, from the beliefs' areas."""
    names = []
    for b in beliefs:
        name = b["area"]
        if name and name != "other" and not name.startswith("INVALID") and name not in names:
            names.append(name)
    return names


def rate_beliefs(text: str, beliefs: list):
    """
    Step 5: give each belief an area from BELIEF_AREAS, and rate each asserted
    belief on RATING_DIMENSIONS (1-5, "" = no position). One call per passage.
    Fills the belief dicts in place. An area name that is not in the list is kept
    visible as INVALID(<name>), not dropped.
    Returns (ok, usage); ok is None when there was nothing to do.
    """
    prompt = get_rate_prompt()
    if not prompt or not beliefs:
        return None, None
    listing = "\n".join(
        f'{n}. {b["label"]}{stance_mark(b)}: {b["definition"]}\n'
        f'   Evidence: "{b["evidence"]}"'
        for n, b in enumerate(beliefs, start=1))
    user = prompt.replace("<<BELIEFS>>", listing).replace("<<PASSAGE>>", text)
    result, usage = call_claude(config.RATE_MODEL, get_system_prompt(), user, max_tokens=1000)
    parsed  = parse_json(result)
    ratings = parsed.get("ratings") if parsed else None
    if not isinstance(ratings, list):
        return False, usage
    by_number = {r.get("belief"): r for r in ratings if isinstance(r, dict)}
    ok = True
    for n, b in enumerate(beliefs, start=1):
        r = by_number.get(n)
        if r is None:
            ok = False
            continue
        area = str(r.get("area") or "").strip()
        b["area"] = area if area in AREA_NAMES else f"INVALID({area[:30]})"
        b["area_note"] = str(r.get("area_note") or "").strip() if area == "other" else ""
        b["rating_reason"] = str(r.get("reason") or "").strip()
        if b["stance"] in UNRATED_STANCES:
            continue                                  # denied / mentioned beliefs get an area but no ratings
        for dim in RATING_DIMENSIONS:
            value = r.get(dim)
            b[dim] = value if isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 5 else ""
    return ok, usage


def tag_passage(text: str, core_belief: str):
    legacy = f"Core belief: {core_belief}\n\nPassage:\n{text}"
    system, user = build_call(get_tag_prompt(), text, legacy_user=legacy, core_belief=core_belief)
    result, usage = call_claude(config.TAG_MODEL, system, user, max_tokens=800)
    parsed = parse_json(result)
    if parsed:
        return {
            "tags":          [int(t) for t in parsed.get("tags", [])],
            "rejects":       [int(t) for t in parsed.get("rejects") or []],   # tag_v3
            "beliefs":       clean_beliefs(parsed.get("beliefs")),            # tag_open_v1
            "confidence":    parsed.get("confidence", ""),
            "constructs":    parsed.get("constructs") or [],
            "new_candidate": parsed.get("new_candidate"),
        }, usage
    return {"tags": [], "rejects": [], "beliefs": [], "confidence": "ERROR",
            "constructs": [], "new_candidate": None}, usage


# ---------------------------------------------------------------------------
# Labeled text writer
# ---------------------------------------------------------------------------

def write_labeled_file(source_name: str, chunks: list, run_date: str):
    os.makedirs(os.path.join(config.RESULTS_DIR, "labeled"), exist_ok=True)
    path = os.path.join(config.RESULTS_DIR, "labeled", f"{source_name}_labeled.txt")

    n_keyword    = sum(1 for c in chunks if c["is_keyword_hit"])
    n_contextual = sum(1 for c in chunks if c["screen"] == "YES" and not c["is_keyword_hit"])
    n_archived   = sum(1 for c in chunks if c.get("filter_decision") in ("YES", "MAYBE"))

    with open(path, "w", encoding="utf-8") as f:
        f.write(f"SOURCE:    {source_name}\n")
        f.write(f"RUN DATE:  {run_date}\n")
        f.write(f"CHUNKS:    {len(chunks)}  |  KEYWORD HITS: {n_keyword}"
                f"  |  CONTEXTUAL: {n_contextual}  |  ARCHIVED: {n_archived}\n")
        f.write("=" * 80 + "\n\n")

        for chunk in chunks:
            f.write(f"--- {chunk['chunk_id']} ---\n")

            kw_str = ", ".join(f"{h['word']} [T{h['tier']}]" for h in chunk["keyword_hits"])
            f.write(f"KEYWORD:   {kw_str or 'none'}\n")

            if chunk["seed_matches"]:
                f.write(f"SEED:      {', '.join(chunk['seed_matches'])}\n")

            f.write(f"SCREEN:    {chunk['screen']}\n")

            fd = chunk.get("filter_decision", "N/A")
            if fd not in ("N/A", None):
                f.write(f"FILTER:    {fd}\n")
                if chunk.get("filter_reason"):
                    f.write(f"REASON:    {chunk['filter_reason']}\n")
                if chunk.get("core_belief"):
                    f.write(f"BELIEF:    {chunk['core_belief']}\n")
                if chunk.get("evidence"):
                    f.write(f"EVIDENCE:  {' '.join(chunk['evidence'].split())}\n")
                    if chunk.get("evidence_verbatim") == "no":
                        f.write("QUOTE CHECK: evidence not found verbatim in chunk\n")

            if fd in ("YES", "MAYBE"):
                tag_str = ", ".join(
                    f"{t} ({TAG_NAMES.get(t, '?')})" for t in chunk.get("tags", [])
                )
                f.write(f"TAGS:      {tag_str or 'none'}\n")
                if chunk.get("rejects"):
                    f.write(f"REJECTS:   {', '.join(str(t) for t in chunk['rejects'])}\n")
                for b in chunk.get("beliefs", []):
                    f.write(f"OPEN CODE: {b['label']} — {b['definition']}\n")
                    detail = [f"stance {b['stance'] or 'none'}", f"area {b['area'] or 'not assigned'}"
                              + (f" ({b['area_note']})" if b["area_note"] else "")]
                    if any(b[dim] != "" for dim in RATING_DIMENSIONS):
                        detail += [f"{dim} {b[dim] if b[dim] != '' else 'NA'}" for dim in RATING_DIMENSIONS]
                    f.write(f"CODE DETAIL: {', '.join(detail)}\n")
                f.write(f"CONSTRUCTS:{' ' + ', '.join(chunk.get('constructs', [])) or ' none'}\n")
                f.write(f"CONFIDENCE:{' ' + chunk.get('confidence', '')}\n")
                nc = chunk.get("new_candidate")
                if nc:
                    f.write(f"NEW CAND:  {nc.get('label','')} — {nc.get('definition','')}\n")

            f.write(f"\n{chunk['text']}\n")
            f.write("-" * 80 + "\n\n")

    return path


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run():
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    run_date = datetime.now().isoformat()

    # Resolve text file paths
    if config.PILOT_TEXTS:
        filepaths = [
            os.path.join(config.TEXTS_DIR, fname)
            for fname in config.PILOT_TEXTS
        ]
    else:
        filepaths = sorted(Path(config.TEXTS_DIR).glob("*.txt"))

    if not SEED_TOPICS_LOADED:
        print("[note] seed_topics.py not found — seed_constructs will be blank")

    # "" when all three step prompts are the pre-v3 kind that carry their own system text
    system_version = config.SYSTEM_PROMPT_VERSION if uses_system_prompt() else ""

    run_log = {
        "run_date":      run_date,
        "screen_model":  config.SCREEN_MODEL,
        "filter_model":  config.FILTER_MODEL,
        "tag_model":     config.TAG_MODEL,
        "system_prompt": system_version,
        "screen_prompt": config.SCREEN_PROMPT_VERSION,
        "filter_prompt": config.FILTER_PROMPT_VERSION,
        "tag_prompt":    config.TAG_PROMPT_VERSION,
        "rate_model":    getattr(config, "RATE_MODEL", ""),
        "rate_prompt":   getattr(config, "RATE_PROMPT_VERSION", None) or "",
        "keywords":      KEYWORDS_VERSION,
        "seed_topics":   SEED_TOPICS_LOADED,
        "texts":         [],
        "totals": {"chunks": 0, "keyword_hits": 0, "contextual": 0, "archived": 0},
        "tokens": {"input": 0, "output": 0},
        "errors": [],
    }

    archive_rows = []
    open_rows    = []      # one row per belief, open-coding pass only

    for filepath in filepaths:
        if not os.path.exists(filepath):
            print(f"[skip] not found: {filepath}")
            continue

        source_name = os.path.splitext(os.path.basename(filepath))[0]
        print(f"\n{'='*60}\n{source_name}")

        chunks, text_id = load_and_preprocess(
            filepath, config.CHUNK_WORDS, config.OVERLAP_WORDS
        )
        print(f"  {len(chunks)} chunks")

        # Keyword scan
        for chunk in chunks:
            kw_hits, seed_matches  = keyword_scan(chunk["text"])
            chunk["keyword_hits"]  = kw_hits
            chunk["seed_matches"]  = seed_matches
            chunk["is_keyword_hit"] = len(kw_hits) > 0

        n_kw = sum(1 for c in chunks if c["is_keyword_hit"])
        print(f"  {n_kw} keyword hits")

        # Step 3a — screen every chunk
        print(f"  Screening {len(chunks)} chunks...")
        for i, chunk in enumerate(chunks):
            decision, usage = screen(chunk["text"])
            chunk["screen"] = decision
            if usage:
                run_log["tokens"]["input"]  += usage.input_tokens
                run_log["tokens"]["output"] += usage.output_tokens
            if decision == "ERROR":
                run_log["errors"].append(f"{chunk['chunk_id']} screen")
            time.sleep(0.05)
            if (i + 1) % 25 == 0:
                print(f"    screened {i+1}/{len(chunks)}")

        n_ctx = sum(1 for c in chunks if c["screen"] == "YES" and not c["is_keyword_hit"])
        print(f"  {n_ctx} contextual (screen YES, no keyword)")

        # Step 3b — filter keyword hits + contextual chunks
        to_filter = [c for c in chunks if c["is_keyword_hit"] or c["screen"] == "YES"]
        print(f"  Filtering {len(to_filter)} candidates...")

        for chunk in to_filter:
            decision, core_belief, extra, usage = filter_passage(chunk["text"])
            chunk["filter_decision"] = decision
            chunk["core_belief"]     = core_belief
            chunk["filter_reason"]   = extra["reason"]
            chunk["evidence"]        = extra["evidence"]
            chunk["evidence_verbatim"] = is_verbatim(extra["evidence"], chunk["text"])
            if usage:
                run_log["tokens"]["input"]  += usage.input_tokens
                run_log["tokens"]["output"] += usage.output_tokens
            if decision == "ERROR":
                run_log["errors"].append(f"{chunk['chunk_id']} filter")
            time.sleep(0.05)

        for chunk in chunks:
            if "filter_decision" not in chunk:
                chunk["filter_decision"] = "N/A"
                chunk["core_belief"]     = ""
                chunk["filter_reason"]   = ""
                chunk["evidence"]        = ""
                chunk["evidence_verbatim"] = ""

        # Step 4 — tag YES/MAYBE passages
        to_tag = [c for c in chunks if c.get("filter_decision") in ("YES", "MAYBE")]
        print(f"  Tagging {len(to_tag)} archived passages...")

        for chunk in to_tag:
            tag_result, usage = tag_passage(chunk["text"], chunk.get("core_belief", ""))
            chunk["tags"]          = tag_result["tags"]
            chunk["rejects"]       = tag_result["rejects"]
            chunk["beliefs"]       = tag_result["beliefs"]
            chunk["confidence"]    = tag_result["confidence"]
            chunk["constructs"]    = tag_result["constructs"]
            chunk["new_candidate"] = tag_result["new_candidate"]
            if usage:
                run_log["tokens"]["input"]  += usage.input_tokens
                run_log["tokens"]["output"] += usage.output_tokens
            if tag_result["confidence"] == "ERROR":
                run_log["errors"].append(f"{chunk['chunk_id']} tag")
            time.sleep(0.05)

        # Step 5 — areas and ratings for the open-coded beliefs (open-coding runs only)
        to_rate = [c for c in to_tag if c["beliefs"]]
        if to_rate and get_rate_prompt():
            print(f"  Assigning areas and ratings in {len(to_rate)} passages...")
        for chunk in to_rate:
            ok, usage = rate_beliefs(chunk["text"], chunk["beliefs"])
            if ok is not None:
                chunk["constructs"] = belief_areas(chunk["beliefs"])
            for b in chunk["beliefs"]:
                if b["area"].startswith("INVALID"):
                    run_log["errors"].append(f"{chunk['chunk_id']} area name")
                if b["stance"].startswith("INVALID"):
                    run_log["errors"].append(f"{chunk['chunk_id']} stance value")
            if usage:
                run_log["tokens"]["input"]  += usage.input_tokens
                run_log["tokens"]["output"] += usage.output_tokens
            if ok is False:
                run_log["errors"].append(f"{chunk['chunk_id']} rate")
            if ok is not None:
                time.sleep(0.05)

        for chunk in chunks:
            if "tags" not in chunk:
                chunk["tags"]          = []
                chunk["rejects"]       = []
                chunk["beliefs"]       = []
                chunk["confidence"]    = "N/A"
                chunk["constructs"]    = []
                chunk["new_candidate"] = None

        # Build archive rows (archived = filter YES or MAYBE)
        for chunk in chunks:
            if chunk.get("filter_decision") not in ("YES", "MAYBE"):
                continue

            kw_words = ", ".join(h["word"] for h in chunk["keyword_hits"])
            kw_tiers = ", ".join(str(h["tier"]) for h in chunk["keyword_hits"])
            tag_name_str = ", ".join(TAG_NAMES.get(t, str(t)) for t in chunk["tags"])
            nc = chunk["new_candidate"] or {}

            archive_rows.append({
                "chunk_id":   chunk["chunk_id"],
                "text_id":    chunk["text_id"],
                "source":     source_name,
                "keyword":    kw_words or ("contextual" if chunk["screen"] == "YES" else "none"),
                "keyword_tier": kw_tiers or "",
                "seed_constructs": ", ".join(chunk["seed_matches"]),
                "screen":     chunk["screen"],
                "filter_trigger": "keyword" if chunk["is_keyword_hit"] else "contextual",
                "filter_decision": chunk["filter_decision"],
                "filter_reason":  chunk["filter_reason"],
                "core_belief":    chunk["core_belief"],
                "evidence":       chunk["evidence"],
                "evidence_verbatim": chunk["evidence_verbatim"],
                "tags":           ", ".join(str(t) for t in chunk["tags"]),
                "tag_names":      tag_name_str,
                "rejects":        ", ".join(str(t) for t in chunk["rejects"]),
                "open_labels":    "; ".join(b["label"] + stance_mark(b) for b in chunk["beliefs"]),
                "constructs":     ", ".join(chunk["constructs"]),
                "confidence":     chunk["confidence"],
                "new_candidate_label":      nc.get("label", ""),
                "new_candidate_definition": nc.get("definition", ""),
                "text_excerpt":   chunk["text"][:300],
                # Human validation (empty)
                "human_decision": "", "human_tags": "", "human_new_candidate": "",
                "coder_notes": "", "coder_id": "", "date_coded": "", "resolved_tag": "",
                # Provenance
                "model_screen":  config.SCREEN_MODEL,
                "model_filter":  config.FILTER_MODEL,
                "model_tag":     config.TAG_MODEL,
                "prompt_system": system_version,
                "prompt_screen": config.SCREEN_PROMPT_VERSION,
                "prompt_filter": config.FILTER_PROMPT_VERSION,
                "prompt_tag":    config.TAG_PROMPT_VERSION,
                "run_date":      run_date,
            })

            for n, b in enumerate(chunk["beliefs"], start=1):
                open_rows.append({
                    "chunk_id":   chunk["chunk_id"],
                    "text_id":    chunk["text_id"],
                    "source":     source_name,
                    "belief_n":   n,
                    "label":      b["label"],
                    "definition": b["definition"],
                    "stance":     b["stance"],
                    "evidence":   b["evidence"],
                    "evidence_verbatim": is_verbatim(b["evidence"], chunk["text"]),
                    "area":      b["area"],
                    "area_note": b["area_note"],
                    "rating_evaluation":     b["evaluation"],
                    "rating_inevitability":  b["inevitability"],
                    "rating_intertwinement": b["intertwinement"],
                    "rating_reason":         b["rating_reason"],
                    "confidence": chunk["confidence"],
                    "filter_decision": chunk["filter_decision"],
                    "core_belief": chunk["core_belief"],
                    "consolidated_code": "",
                    "human_evaluation": "", "human_inevitability": "", "human_intertwinement": "",
                    "coder_notes": "",
                    "model_tag":     config.TAG_MODEL,
                    "model_rate":    getattr(config, "RATE_MODEL", "") if get_rate_prompt() else "",
                    "prompt_system": system_version,
                    "prompt_tag":    config.TAG_PROMPT_VERSION,
                    "prompt_rate":   (getattr(config, "RATE_PROMPT_VERSION", None) or ""),
                    "run_date":      run_date,
                })

        # Labeled text file
        labeled_path = write_labeled_file(source_name, chunks, run_date)
        n_archived = sum(1 for c in chunks if c.get("filter_decision") in ("YES", "MAYBE"))
        print(f"  Archived: {n_archived}  |  labeled → {labeled_path}")

        run_log["texts"].append({
            "source":       source_name,
            "chunks":       len(chunks),
            "keyword_hits": n_kw,
            "contextual":   n_ctx,
            "archived":     n_archived,
        })
        run_log["totals"]["chunks"]       += len(chunks)
        run_log["totals"]["keyword_hits"] += n_kw
        run_log["totals"]["contextual"]   += n_ctx
        run_log["totals"]["archived"]     += n_archived

    # Write archive CSV
    archive_path = os.path.join(config.RESULTS_DIR, "pilot_archive.csv")
    if archive_rows:
        with open(archive_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=ARCHIVE_FIELDS)
            writer.writeheader()
            writer.writerows(archive_rows)

    # Write open codes (one row per belief), if the tag step was the open-coding prompt
    open_path = os.path.join(config.RESULTS_DIR, "open_codes.csv")
    if open_rows:
        with open(open_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=OPEN_CODE_FIELDS)
            writer.writeheader()
            writer.writerows(open_rows)
    run_log["totals"]["open_codes"] = len(open_rows)
    run_log["temperature"] = TEMPERATURE_MODES[_temperature_mode]

    # Write run log
    log_path = os.path.join(config.RESULTS_DIR, "run_log.json")
    with open(log_path, "w") as f:
        json.dump(run_log, f, indent=2)

    # Summary
    t = run_log["totals"]
    print(f"\n{'='*60}")
    print(f"PILOT COMPLETE")
    print(f"  Texts:          {len(run_log['texts'])}")
    print(f"  Chunks:         {t['chunks']}")
    print(f"  Keyword hits:   {t['keyword_hits']}")
    print(f"  Contextual:     {t['contextual']}")
    print(f"  Archived:       {t['archived']}")
    print(f"  Tokens in/out:  {run_log['tokens']['input']:,} / {run_log['tokens']['output']:,}")
    print(f"  Errors:         {len(run_log['errors'])}")
    print(f"  Archive:        {archive_path}")
    if open_rows:
        print(f"  Open codes:     {len(open_rows)} beliefs → {open_path}")
    print(f"  Run log:        {log_path}")


if __name__ == "__main__":
    run()
