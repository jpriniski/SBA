"""
Draw a sample of passages and write a sheet for coding them by hand.

The hand codes are the yardstick for comparing runs: a person reads the passages
without seeing any model output and records the beliefs and themes they find.

Input:   the labeled files of one run (for the passage texts and the screen results)
Output, in results/validation/ (ignored by Git, because it holds source text):
    coding_sheet.xlsx   what the coder fills in
    passages.txt        the same passages as plain text, for easier reading
    sample_key.csv      which chunk each passage is. Not for the coder.

The sample is random with a fixed seed, so it can be drawn again. Each text gets
at least one passage; larger texts get more (in proportion to the square root of
their length), passages next to each other in a text are not both drawn, and one
passage that the screen turned down is included to check the screen.

Usage:
    python make_coding_sheet.py                                   # 12 passages from the run in config.py
    python make_coding_sheet.py --run results/run5_general_wording --n 15 --seed 7

Needs: openpyxl.
"""

import argparse
import csv
import glob
import math
import os
import random
import re

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

import config

FONT = "Arial"
HEAD_FILL = PatternFill("solid", start_color="2C2C2C")
FILL_IN = PatternFill("solid", start_color="FFF2A8")
EXAMPLE_FILL = PatternFill("solid", start_color="EEEEEE")
WRAP = Alignment(wrap_text=True, vertical="top")
WORDS_PER_PART = 200          # a 1,000-word passage is shown in five rows; Excel cannot show it in one cell
BELIEF_ROWS = 150

INSTRUCTIONS = [
    ("h", "Hand coding of passages"),
    ("p", "You will read a small set of passages and record what each one says about suffering. Your codes are "
          "the yardstick against which the language model's coding is judged, so please do not look at any model "
          "output for these texts (the viewer, open_codes.csv, the labeled files) before or while you code."),
    ("p", "Code from the page. A passage is about a thousand words cut from a longer text, so it may begin and end "
          "in the middle of a sentence. Use only what the passage says, not what you know about the work."),
    ("h", "What counts as suffering"),
    ("p", "By suffering, we mean experiences that cause physical pain, emotional distress, or unhappiness. This can "
          "include everyday experiences (such as being criticized or having an argument with a loved one) to major "
          "life challenges (such as serious illnesses, loss, and death)."),
    ("p", "Authors rarely use the word itself: pain, sorrow, grief, hardship, trouble and misery all count, and so "
          "do small, ordinary hurts."),
    ("h", "What counts as a suffering belief"),
    ("p", "A general claim about suffering. It must pass five tests."),
    ("p", "1. Claim. Someone could agree or disagree with it. It does not merely describe how suffering feels. "
          "\"Suffering is meaningless\" passes; \"Grief feels like drowning\" fails."),
    ("p", "2. Generality. It is about suffering in general, not one episode. \"Suffering builds character\" passes; "
          "\"My surgery was painful\" fails."),
    ("p", "3. Individual difference. People really differ on it. \"People bring their suffering on themselves\" "
          "passes; \"Suffering is unpleasant\" fails."),
    ("p", "4. Plain language. It can be said in everyday words."),
    ("p", "5. Broad relevance. It bears on how people meet suffering generally. \"Avoiding all pain makes life "
          "smaller\" passes; \"Chemotherapy causes nausea\" fails."),
    ("h", "Stated beliefs and depicted themes"),
    ("p", "A STATED BELIEF is a general claim that the author, the narrator or a speaker actually puts into words. "
          "You must be able to quote one continuous stretch of the passage in which the claim is made, and the "
          "generality must be in the speaker's own words: the stretch speaks of people in general (\"people\", "
          "\"one\", \"nobody\", or \"you\" and \"we\" meant of everyone or of a whole kind of person), or it is a "
          "maxim or a rule. \"Grief never really leaves you\" is a stated belief."),
    ("p", "A remark about one person's, one family's or one character's situation is not a stated belief, even when "
          "a general lesson is easy to draw from it. \"I can't bear this any longer\" and \"she has suffered "
          "enough\" state no belief. Narration of what a character did, felt or thought is about that character."),
    ("p", "A DEPICTED THEME is what a story, poem or anecdote shows about suffering through what happens, when no "
          "one in it says so. Record one only when the passage itself makes the link, presenting someone's "
          "suffering as following from something or leading to something. An event that involves suffering is "
          "not by itself a theme. Most passages have none, and a passage rarely has more than one."),
    ("p", "A passage can be about suffering from beginning to end and still state no belief. Recording nothing is "
          "a correct and common answer."),
    ("h", "What to fill in (yellow cells)"),
    ("p", "Sheet \"Passage judgments\", one row per passage. (a) Could any part of the passage be read as stating, "
          "implying or disputing a general claim about suffering? (b) Does it state at least one belief? "
          "(c) Does it show at least one depicted theme? Answer yes or no to each."),
    ("p", "Sheet \"Beliefs\", one row per stated belief or depicted theme. Choose the passage and the type. Copy the "
          "quote exactly from the passage: one continuous stretch, at most about 40 words. Write the belief as one "
          "short general sentence in everyday words, where possible beginning \"Suffering\". For a stated belief, "
          "give the stance."),
    ("p", "Stance. endorses: the passage puts the belief forward as true. denies: the passage rejects it; write "
          "the belief in its positive form (\"Suffering is a punishment\") and let the stance carry the rejection. "
          "mentions: the passage reports it as something people say, without taking a side. conditional: the "
          "passage holds it only under a stated condition; put the condition in the sentence."),
    ("p", "Two claims are separate beliefs when the same person could agree with one and disagree with the other. "
          "A restatement of a belief already listed is not a second belief."),
    ("p", "If you are unsure about an entry, record it and mark it \"unsure\". The first row of the Beliefs sheet "
          "is an example; leave it in place."),
]


def parse_labeled(path):
    """[(chunk_id, source, screen, text)] in the order of the file."""
    raw = open(path, encoding="utf-8").read().replace("\r\n", "\n")
    source = (re.search(r"^SOURCE:\s+(.*)$", raw, re.M) or [None, ""])[1].strip()
    parts = re.split(r"^--- (\w+) ---$", raw, flags=re.M)[1:]
    out = []
    for cid, body in zip(parts[0::2], parts[1::2]):
        head, _, rest = body.strip("\n").partition("\n\n")
        screen = (re.search(r"^SCREEN:\s+(.*)$", head, re.M) or [None, ""])[1].strip()
        text = re.split(r"^-{20,}$", rest, flags=re.M)[0].strip()
        out.append((cid, source, screen, text))
    return out


def draw_sample(texts, n, seed):
    """texts: {source: [(chunk_id, source, screen, text), ...]}. Returns the drawn chunks, shuffled."""
    rng = random.Random(seed)
    sources = sorted(texts)
    n_screen = 1 if any(c[2] != "YES" for cs in texts.values() for c in cs) else 0
    budget = max(n - n_screen, len(sources))

    # Quotas: one per text, the rest in proportion to the square root of the text's length
    weights = {s: math.sqrt(len(texts[s])) for s in sources}
    raw = {s: budget * weights[s] / sum(weights.values()) for s in sources}
    quota = {s: min(len(texts[s]), max(1, int(raw[s]))) for s in sources}
    while sum(quota.values()) < budget:
        room = [s for s in sources if quota[s] < len(texts[s])]
        if not room:
            break
        quota[max(room, key=lambda s: raw[s] - quota[s])] += 1
    while sum(quota.values()) > budget:
        quota[max(sources, key=lambda s: quota[s])] -= 1

    chosen = {}                                                          # source -> set of positions
    for s in sources:
        idx, k = list(range(len(texts[s]))), min(quota[s], len(texts[s]))
        for _ in range(2000):                                            # avoid neighbouring passages (they overlap)
            pick = sorted(rng.sample(idx, k))
            if all(b - a > 1 for a, b in zip(pick, pick[1:])):
                break
        chosen[s] = set(pick)

    if n_screen:                # the last place goes to a passage the screen turned down, unless one is already in
        free = [(s, i) for s in sources for i in range(len(texts[s]))
                if i not in chosen[s] and i - 1 not in chosen[s] and i + 1 not in chosen[s]]
        turned_down = [(s, i) for s, i in free if texts[s][i][2] != "YES"]
        already = any(texts[s][i][2] != "YES" for s in sources for i in chosen[s])
        pool = free if already else (turned_down or free)
        if pool:
            s, i = rng.choice(pool)
            chosen[s].add(i)

    sample = [texts[s][i] for s in sources for i in sorted(chosen[s])]
    rng.shuffle(sample)
    return sample


def header(ws, names, widths, fill_in=()):
    for j, (name, width) in enumerate(zip(names, widths), start=1):
        c = ws.cell(row=1, column=j, value=name)
        c.font = Font(name=FONT, size=10, bold=True, color="000000" if name in fill_in else "FFFFFF")
        c.fill = FILL_IN if name in fill_in else HEAD_FILL
        c.alignment = Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[chr(64 + j)].width = width
    ws.row_dimensions[1].height = 32
    ws.freeze_panes = "A2"


def write_workbook(sample, path, meta):
    wb = Workbook()
    ws = wb.active
    ws.title = "Instructions"
    ws.column_dimensions["A"].width = 118
    row = 1
    for kind, text in INSTRUCTIONS:
        c = ws.cell(row=row, column=1, value=text)
        c.font = Font(name=FONT, size=12 if kind == "h" else 10, bold=kind == "h")
        c.alignment = WRAP
        row += 1
    row += 1
    for label in ("Coder", "Date"):
        ws.cell(row=row, column=1, value=f"{label}:").font = Font(name=FONT, size=10, bold=True)
        row += 1
        ws.cell(row=row, column=1).fill = FILL_IN
        row += 1
    ws.cell(row=row + 1, column=1, value=meta).font = Font(name=FONT, size=9, color="888888")

    ids = [f"P{i:02d}" for i in range(1, len(sample) + 1)]
    titles = [c[1].replace("_", " ") for c in sample]

    # Passages, in parts of about 200 words
    ws = wb.create_sheet("Passages")
    header(ws, ["passage", "text", "part", "passage text"], [9, 30, 6, 120])
    r = 2
    for pid, title, (_, _, _, text) in zip(ids, titles, sample):
        words = text.split()
        n_parts = max(1, math.ceil(len(words) / WORDS_PER_PART))
        for k in range(n_parts):
            vals = [pid, title, f"{k + 1}/{n_parts}", " ".join(words[k * WORDS_PER_PART:(k + 1) * WORDS_PER_PART])]
            for j, v in enumerate(vals, start=1):
                c = ws.cell(row=r, column=j, value=v)
                c.font = Font(name=FONT, size=11 if j == 4 else 10, bold=(j == 1 and k == 0))
                c.alignment = WRAP
            r += 1
        r += 1                                                           # blank row between passages

    yes_no = DataValidation(type="list", formula1='"yes,no"', allow_blank=True)

    # One row of judgments per passage
    ws = wb.create_sheet("Passage judgments")
    names = ["passage", "text", "claim about suffering possible?", "states a belief?", "shows a depicted theme?",
             "minutes spent", "notes"]
    header(ws, names, [9, 34, 18, 14, 16, 10, 50], fill_in=names[2:])
    ws.add_data_validation(yes_no)
    for i, (pid, title) in enumerate(zip(ids, titles), start=2):
        ws.cell(row=i, column=1, value=pid).font = Font(name=FONT, size=10, bold=True)
        ws.cell(row=i, column=2, value=title).font = Font(name=FONT, size=10)
        for j in range(3, 8):
            c = ws.cell(row=i, column=j)
            c.fill, c.font, c.alignment = FILL_IN, Font(name=FONT, size=10), WRAP
        yes_no.add(f"C{i}:E{i}")

    # One row per belief or theme
    ws = wb.create_sheet("Beliefs")
    names = ["passage", "type", "quote (copied exactly)", "belief in one general sentence", "stance", "sure?", "notes"]
    header(ws, names, [9, 16, 60, 52, 13, 9, 36], fill_in=names)
    example = ["EXAMPLE", "stated belief", "Grief never really leaves you",
               "Suffering from loss never fully ends.", "endorses", "sure", "Example row. Leave it in place."]
    for j, v in enumerate(example, start=1):
        c = ws.cell(row=2, column=j, value=v)
        c.font, c.fill, c.alignment = Font(name=FONT, size=10, italic=True, color="666666"), EXAMPLE_FILL, WRAP
    last = 2 + BELIEF_ROWS
    lists = {"A": '"' + ",".join(ids) + '"', "B": '"stated belief,depicted theme"',
             "E": '"endorses,denies,mentions,conditional"', "F": '"sure,unsure"'}
    for col, formula in lists.items():
        dv = DataValidation(type="list", formula1=formula, allow_blank=True)
        ws.add_data_validation(dv)
        dv.add(f"{col}3:{col}{last}")
    for i in range(3, last + 1):
        for j in range(1, 8):
            c = ws.cell(row=i, column=j)
            c.fill, c.font, c.alignment = FILL_IN, Font(name=FONT, size=10), WRAP
    wb.save(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    ap.add_argument("--run", default=config.RESULTS_DIR, help="run folder whose labeled files supply the passages")
    ap.add_argument("--n", type=int, default=12, help="number of passages")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--out", default=os.path.join(config.BASE_DIR, "results", "validation"))
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.run, "labeled", "*_labeled.txt")))
    if not files:
        raise SystemExit(f"No labeled files in {os.path.join(args.run, 'labeled')}. Give a finished run with --run.")
    texts = {}
    for f in files:
        chunks = parse_labeled(f)
        if chunks:
            texts[chunks[0][1]] = chunks
    sample = draw_sample(texts, args.n, args.seed)

    os.makedirs(args.out, exist_ok=True)
    sheet = os.path.join(args.out, "coding_sheet.xlsx")
    if os.path.exists(sheet):
        raise SystemExit(f"{sheet} already exists and may hold someone's coding. Move or rename it first.")
    run_name = os.path.basename(os.path.normpath(args.run))
    write_workbook(sample, sheet, f"Sample of {len(sample)} passages, seed {args.seed}, drawn from {run_name}.")

    with open(os.path.join(args.out, "passages.txt"), "w", encoding="utf-8") as f:
        for i, (_, source, _, text) in enumerate(sample, start=1):
            f.write(f"===== P{i:02d}   {source.replace('_', ' ')} =====\n\n{text}\n\n\n")
    with open(os.path.join(args.out, "sample_key.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["passage", "chunk_id", "source", "screen", "words", "seed", "drawn_from"])
        for i, (cid, source, screen, text) in enumerate(sample, start=1):
            w.writerow([f"P{i:02d}", cid, source, screen, len(text.split()), args.seed, run_name])

    per_text = {}
    for c in sample:
        per_text[c[1]] = per_text.get(c[1], 0) + 1
    print(f"{len(sample)} passages: " + ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in sorted(per_text.items())))
    print(f"Screened out by the model: {sum(1 for c in sample if c[2] != 'YES')} (the coder is not told which)")
    print(f"Coding sheet → {sheet}\nPlain text   → {os.path.join(args.out, 'passages.txt')}\n"
          f"Key          → {os.path.join(args.out, 'sample_key.csv')}  (not for the coder)")


if __name__ == "__main__":
    main()
