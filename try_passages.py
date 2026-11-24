"""
Try the prompts on a few passages and print what the model returns.

Each passage goes through the same steps, prompts and models as pipeline.py
(screen -> filter -> tag -> areas and ratings), but without chunking, so short
items such as a single sentence or a social-media post can be tested.

Usage:
    python try_passages.py                       # reads test_passages.txt
    python try_passages.py my_examples.txt       # another file
    python try_passages.py --text "Suffering builds character."

File format: passages separated by a line containing only ---
A line starting with # is a note to yourself (for example what you expect);
it is printed with the result and is not sent to the model.

This makes real API calls: up to four per passage. Results are also saved to
results/test_passages_output.json.
"""

import argparse
import json
import os
from datetime import datetime

import config
import pipeline
from keywords import keyword_scan


def read_passages(path):
    """Returns a list of (notes, text)."""
    with open(path, encoding="utf-8") as f:
        blocks = f.read().split("\n---")
    passages = []
    for block in blocks:
        lines = [l for l in block.strip().splitlines()]
        notes = [l.lstrip("# ").strip() for l in lines if l.startswith("#")]
        text  = "\n".join(l for l in lines if not l.startswith("#")).strip()
        if text:
            passages.append((notes, text))
    return passages


def run_one(text):
    """All steps for one passage. Returns a dict of results."""
    out = {"text": text, "keywords": [h["word"] for h in keyword_scan(text)[0]]}
    out["screen"], _ = pipeline.screen(text)
    if getattr(config, "USE_FILTER", True):
        decision, core_belief, extra, _ = pipeline.filter_passage(text)
    else:
        decision, core_belief, extra = "SKIPPED", "", {"reason": "filter step is off", "evidence": ""}
    out.update(filter=decision, reason=extra["reason"], evidence=extra["evidence"],
               evidence_verbatim=pipeline.is_verbatim(extra["evidence"], text), core_belief=core_belief)
    if decision in pipeline.CODED:
        tag, _ = pipeline.tag_passage(text, core_belief)
        out.update(confidence=tag["confidence"], tags=tag["tags"], rejects=tag["rejects"],
                   new_candidate=tag["new_candidate"], beliefs=tag["beliefs"], depicted=tag["depicted"])
        if tag["beliefs"] or tag["depicted"]:
            ok, _ = pipeline.rate_beliefs(text, tag["beliefs"] + tag["depicted"])
            out["step5"] = {None: "skipped (switched off)", True: "ok", False: "ERROR"}[ok]
    return out


def show(n, notes, r):
    print("=" * 78)
    print(f"PASSAGE {n}")
    print(r["text"])
    for note in notes:
        print(f"  note: {note}")
    print("-" * 78)
    print(f"keywords: {', '.join(r['keywords']) or 'none'}    screen: {r['screen']}")
    print(f"FILTER:   {r['filter']}   ({r['reason'] or 'no reason given'})")
    if r["evidence"]:
        flag = "" if r["evidence_verbatim"] == "yes" else "   [NOT found verbatim in the passage]"
        print(f"evidence: \"{r['evidence']}\"{flag}")
    if r["core_belief"]:
        print(f"core belief: {r['core_belief']}")
    if "confidence" in r:
        print(f"confidence: {r['confidence']}")
        if r["tags"] or r["rejects"]:
            names = ", ".join(f"{t} {pipeline.TAG_NAMES.get(t, '?')}" for t in r["tags"])
            print(f"tags: {names or 'none'}    rejects: {r['rejects'] or 'none'}")
        if r["new_candidate"]:
            print(f"new candidate: {r['new_candidate']}")
        if not r["beliefs"] and not r["depicted"] and not r["tags"]:
            print("beliefs: none (the tag step found no qualifying belief)")
        for i, b in enumerate(r["beliefs"], start=1):
            print(f"\n  BELIEF {i}: {b['label']}   [stance: {b['stance']}]")
            print(f"    {b['definition']}")
            print(f"    evidence: \"{b['evidence']}\"")
            if b["area"]:
                note = f" ({b['area_note']})" if b["area_note"] else ""
                ratings = ", ".join(f"{d} {b[d] if b[d] != '' else '-'}" for d in pipeline.RATING_DIMENSIONS)
                print(f"    area: {b['area']}{note}    ratings: {ratings}")
                if b["rating_reason"]:
                    print(f"    why: {b['rating_reason']}")
        for i, b in enumerate(r["depicted"], start=1):
            print(f"\n  DEPICTED THEME {i}: {b['label']}   [shown, not stated]")
            print(f"    {b['definition']}")
            print(f"    evidence: \"{b['evidence']}\"")
            if b["area"]:
                print(f"    area: {b['area']}" + (f" ({b['area_note']})" if b["area_note"] else ""))
        if r.get("step5") == "ERROR":
            print("  [step 5 returned something that could not be read]")
    print()


def main():
    ap = argparse.ArgumentParser(description="Try the prompts on a few passages.")
    ap.add_argument("file", nargs="?", default=os.path.join(config.BASE_DIR, "test_passages.txt"))
    ap.add_argument("--text", help="one passage given on the command line")
    args = ap.parse_args()

    passages = [([], args.text)] if args.text else read_passages(args.file)
    print(f"provider: {pipeline.PROVIDER} | models: {config.FILTER_MODEL}, {config.TAG_MODEL}")
    print(f"{len(passages)} passage(s) | screen {config.SCREEN_PROMPT_VERSION}, filter {config.FILTER_PROMPT_VERSION}, "
          f"tag {config.TAG_PROMPT_VERSION}, step 5 {getattr(config, 'RATE_PROMPT_VERSION', None) or 'off'}\n")
    results = []
    for n, (notes, text) in enumerate(passages, start=1):
        r = run_one(text)
        r["notes"] = notes
        results.append(r)
        show(n, notes, r)

    results_dir = os.path.join(config.BASE_DIR, "results")
    os.makedirs(results_dir, exist_ok=True)
    out_path = os.path.join(results_dir, "test_passages_output.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"run_date": datetime.now().isoformat(),
                   "provider": pipeline.PROVIDER, "served_by": sorted(pipeline.SERVED_BY),
                   "cost_usd": round(pipeline.COST["usd"], 4) if pipeline.PROVIDER == "openrouter" else None,
                   "temperature": pipeline.TEMPERATURE_MODES[pipeline._temperature_mode],
                   "prompts": {"system": config.SYSTEM_PROMPT_VERSION, "screen": config.SCREEN_PROMPT_VERSION,
                               "filter": config.FILTER_PROMPT_VERSION, "tag": config.TAG_PROMPT_VERSION,
                               "rate": getattr(config, "RATE_PROMPT_VERSION", None)},
                   "models": {"screen": config.SCREEN_MODEL, "filter": config.FILTER_MODEL,
                              "tag": config.TAG_MODEL, "rate": getattr(config, "RATE_MODEL", None)},
                   "results": results}, f, indent=2, ensure_ascii=False)
    if pipeline.PROVIDER == "openrouter":
        print(f"Cost: ${pipeline.COST['usd']:.2f} (as reported by OpenRouter)")
    print(f"Saved to {out_path}")


if __name__ == "__main__":
    main()
