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
from keywords import keyword_scan

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WORKING_CLASSIFICATION = """\
1. Punishment/consequence  — Suffering results from wrongdoing or violated order
2. Teacher/growth          — Suffering instructs, refines, builds character
3. Craving/attachment      — Suffering arises from desire, clinging, resisting
4. Shared condition        — Suffering is the universal human lot
5. Call to compassion      — Suffering obligates care and solidarity
6. Acceptance/equanimity   — Suffering is to be met with calm or acceptance
7. Mystery/unknowable      — Suffering's meaning is unknowable to humans
0. None of the above       — propose a new candidate belief"""

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
    "filter_decision", "core_belief",
    "tags", "tag_names", "constructs", "confidence",
    "new_candidate_label", "new_candidate_definition",
    "text_excerpt",
    # Human validation (empty — for RAs)
    "human_decision", "human_tags", "human_new_candidate",
    "coder_notes", "coder_id", "date_coded", "resolved_tag",
    # Provenance
    "model_screen", "model_filter", "model_tag",
    "prompt_screen", "prompt_filter", "prompt_tag",
    "run_date",
]

# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

client = anthropic.Anthropic()


def load_prompt(name: str) -> str:
    path = os.path.join(config.PROMPTS_DIR, f"{name}.txt")
    with open(path) as f:
        return f.read().strip()


def call_claude(model: str, system: str, user: str, max_tokens=256, retries=3):
    for attempt in range(retries):
        try:
            msg = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=0,
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

_screen_prompt = None
_filter_prompt = None
_tag_prompt    = None


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


def screen(text: str):
    result, usage = call_claude(config.SCREEN_MODEL, get_screen_prompt(), text)
    parsed = parse_json(result)
    decision = parsed.get("screen", "ERROR").upper() if parsed else "ERROR"
    return decision, usage


def filter_passage(text: str):
    result, usage = call_claude(config.FILTER_MODEL, get_filter_prompt(), text)
    parsed = parse_json(result)
    if parsed:
        decision    = parsed.get("decision", "ERROR").upper()
        core_belief = parsed.get("core_belief") or ""
    else:
        decision, core_belief = "ERROR", ""
    return decision, core_belief, usage


def tag_passage(text: str, core_belief: str):
    user   = f"Core belief: {core_belief}\n\nPassage:\n{text}"
    result, usage = call_claude(config.TAG_MODEL, get_tag_prompt(), user, max_tokens=400)
    parsed = parse_json(result)
    if parsed:
        return {
            "tags":          [int(t) for t in parsed.get("tags", [])],
            "confidence":    parsed.get("confidence", ""),
            "constructs":    parsed.get("constructs", []),
            "new_candidate": parsed.get("new_candidate"),
        }, usage
    return {"tags": [], "confidence": "ERROR", "constructs": [], "new_candidate": None}, usage


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
                if chunk.get("core_belief"):
                    f.write(f"BELIEF:    {chunk['core_belief']}\n")

            if fd in ("YES", "MAYBE"):
                tag_str = ", ".join(
                    f"{t} ({TAG_NAMES.get(t, '?')})" for t in chunk.get("tags", [])
                )
                f.write(f"TAGS:      {tag_str or 'none'}\n")
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

    run_log = {
        "run_date":      run_date,
        "screen_model":  config.SCREEN_MODEL,
        "filter_model":  config.FILTER_MODEL,
        "tag_model":     config.TAG_MODEL,
        "screen_prompt": config.SCREEN_PROMPT_VERSION,
        "filter_prompt": config.FILTER_PROMPT_VERSION,
        "tag_prompt":    config.TAG_PROMPT_VERSION,
        "texts":         [],
        "totals": {"chunks": 0, "keyword_hits": 0, "contextual": 0, "archived": 0},
        "tokens": {"input": 0, "output": 0},
        "errors": [],
    }

    archive_rows = []

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
            decision, core_belief, usage = filter_passage(chunk["text"])
            chunk["filter_decision"] = decision
            chunk["core_belief"]     = core_belief
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

        # Step 4 — tag YES/MAYBE passages
        to_tag = [c for c in chunks if c.get("filter_decision") in ("YES", "MAYBE")]
        print(f"  Tagging {len(to_tag)} archived passages...")

        for chunk in to_tag:
            tag_result, usage = tag_passage(chunk["text"], chunk.get("core_belief", ""))
            chunk["tags"]          = tag_result["tags"]
            chunk["confidence"]    = tag_result["confidence"]
            chunk["constructs"]    = tag_result["constructs"]
            chunk["new_candidate"] = tag_result["new_candidate"]
            if usage:
                run_log["tokens"]["input"]  += usage.input_tokens
                run_log["tokens"]["output"] += usage.output_tokens
            if tag_result["confidence"] == "ERROR":
                run_log["errors"].append(f"{chunk['chunk_id']} tag")
            time.sleep(0.05)

        for chunk in chunks:
            if "tags" not in chunk:
                chunk["tags"]          = []
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
                "core_belief":    chunk["core_belief"],
                "tags":           ", ".join(str(t) for t in chunk["tags"]),
                "tag_names":      tag_name_str,
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
                "prompt_screen": config.SCREEN_PROMPT_VERSION,
                "prompt_filter": config.FILTER_PROMPT_VERSION,
                "prompt_tag":    config.TAG_PROMPT_VERSION,
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
    print(f"  Run log:        {log_path}")


if __name__ == "__main__":
    run()
