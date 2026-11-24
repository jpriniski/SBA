"""
Build the master workbook for framework generation from one run.

Input (the run's results folder):
    open_code_clusters.csv   stated beliefs with their cluster  (run cluster_open_codes.py first)
    depicted_themes.csv      optional
    run_log.json             optional
Output:
    framework_master.xlsx    in the same folder

Sheets:
    About      what the file is, how it was built, what to fill in
    Themes     one row per belief theme (cluster): definition, keywords, counts, mean ratings,
               example quotes, and empty columns for the team's decisions
    Coverage   stated beliefs by area and text
    Depicted   each depicted theme with the stated theme it is closest to
    Beliefs    every stated belief with its theme, for tracing a theme back to the text

Counts and means on Themes and Coverage are formulas over the Beliefs and Depicted sheets,
so they update if a belief is moved to another theme. Definitions, keywords, example quotes
and text lists are fixed when the file is built; run this script again to refresh them.

Usage:
    python build_master.py                         # the run named in config.py
    python build_master.py --run results/run4_depicted_separate
    python build_master.py --stream "text analysis"

Needs: pandas, numpy, scikit-learn, openpyxl, and sentence-transformers (as for clustering).
"""

import argparse
import datetime
import json
import os
import re

import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer

import config
from cluster_open_codes import embed

# Same names and order as BELIEF_AREAS in pipeline.py
AREAS = ["understanding", "prevalence", "causes", "consequences", "controllability",
         "personal_response", "interpersonal_response", "overall_evaluation",
         "meaning_fairness", "other"]
RATINGS = ["evaluation", "inevitability", "intertwinement"]
STANCES = ["endorses", "conditional", "denies", "mentions"]

# Words too common in the definitions to tell one theme from another
KEYWORD_STOP = set(ENGLISH_STOP_WORDS) | {
    "suffering", "suffer", "suffers", "suffered", "people", "person", "persons", "one", "ones",
    "can", "may", "often", "make", "makes", "made", "thing", "things", "something", "way", "ways",
}

FONT = "Arial"
HEAD_FILL = PatternFill("solid", start_color="2C2C2C")
FILL_IN = PatternFill("solid", start_color="FFF2A8")       # cells for the team to fill in
WRAP = Alignment(wrap_text=True, vertical="top")


def nice(name):
    return str(name).replace("_", " ").strip()


def to_number(v):
    """'4' or '4.0' -> 4; anything else -> None (left blank in the sheet)."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return int(f) if f == int(f) else f


def theme_keywords(docs, n=5):
    """Most distinctive words of each theme: TF-IDF with one document per theme."""
    if not docs:
        return []
    vec = TfidfVectorizer(stop_words=sorted(KEYWORD_STOP), sublinear_tf=True,
                          token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z'-]{2,}\b")
    try:
        X = vec.fit_transform(docs).toarray()
    except ValueError:                      # nothing but stop words
        return ["" for _ in docs]
    words = np.array(vec.get_feature_names_out())
    out = []
    for row in X:
        order = sorted(np.nonzero(row)[0], key=lambda j: (-row[j], words[j]))
        chosen = []
        for j in order:
            w = words[j]
            # skip a plural or other form of a word already chosen
            if any(w.startswith(c[:max(4, len(c) - 3)]) and c.startswith(w[:max(4, len(w) - 3)]) for c in chosen):
                continue
            chosen.append(w)
            if len(chosen) == n:
                break
        out.append(", ".join(chosen))
    return out


def load_run(run_dir):
    path = os.path.join(run_dir, "open_code_clusters.csv")
    if not os.path.exists(path):
        raise SystemExit(f"{path} not found.\nRun  python cluster_open_codes.py  first; "
                         "it groups the beliefs in open_codes.csv into candidate themes.")
    df = pd.read_csv(path, dtype=str).fillna("")
    df["cluster"] = df["cluster"].map(to_number)
    if "duplicate" not in df:
        df["duplicate"] = "False"
    df["duplicate"] = df["duplicate"].astype(str).str.lower().eq("true")

    dep_path = os.path.join(run_dir, "depicted_themes.csv")
    dep = pd.read_csv(dep_path, dtype=str).fillna("") if os.path.exists(dep_path) else pd.DataFrame()

    # Runs before the stated/depicted split kept depicted themes in open_codes.csv with stance "depicts"
    old = df[df["stance"] == "depicts"]
    if len(old):
        dep = pd.concat([dep, old[[c for c in ("chunk_id", "source", "label", "definition", "evidence",
                                               "evidence_verbatim", "area") if c in old]]],
                        ignore_index=True).fillna("")
        df = df[df["stance"] != "depicts"]

    log, grouping = {}, {}
    for name, target in (("run_log.json", log), ("cluster_meta.json", grouping)):
        path = os.path.join(run_dir, name)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                target.update(json.load(f))
    return df.reset_index(drop=True), dep.reset_index(drop=True), log, grouping


def build_tables(df, dep, stream, centred):
    """Returns (themes, beliefs, depicted, method) as lists of dicts ready to write."""
    df = df.copy()
    df["text"] = df["source"].map(nice)
    in_theme = df["cluster"].notna() & ~df["duplicate"]

    # Themes: clusters that hold at least one stated belief, largest first
    sizes = df[in_theme].groupby("cluster").size().sort_values(ascending=False, kind="stable")
    theme_id = {c: f"T{i:03d}" for i, c in enumerate(sizes.index, start=1)}
    df["theme_id"] = [theme_id.get(c, "") if ok else "" for c, ok in zip(df["cluster"], in_theme)]

    # One embedding call for stated definitions and depicted definitions together
    stated = df[df["theme_id"] != ""]
    dep_defs = list(dep["definition"]) if len(dep) else []
    X, method = embed(list(stated["definition"]) + dep_defs)
    if centred:                             # as in cluster_open_codes.py: drop what the stated beliefs share
        Xc = X - X[:len(stated)].mean(axis=0)
        norms = np.linalg.norm(Xc, axis=1, keepdims=True)
        flat = norms[:, 0] < 1e-9
        Xc[flat], norms[flat] = X[flat], 1.0
        X = Xc / norms
    Xs, Xd = X[:len(stated)], X[len(stated):]

    docs, themes, members = [], [], []
    for c, tid in theme_id.items():
        pos = np.flatnonzero((stated["cluster"] == c).to_numpy())
        g = stated.iloc[pos]
        centre = Xs[pos].mean(axis=0)
        centre = centre / (np.linalg.norm(centre) or 1)
        near = np.argsort(-(Xs[pos] @ centre))                  # closest to the theme's centre first
        central = g.iloc[near[0]]

        # Up to three example quotes: beliefs the text itself holds, one per text where possible
        quotes, seen = [], set()
        ranked = [g.iloc[i] for i in near]
        for only_new_text in (True, False):
            for r in ranked:
                if len(quotes) == 3:
                    break
                if not r["evidence"].strip() or r["stance"] not in ("endorses", "conditional"):
                    continue
                if r.get("evidence_verbatim", "") == "no" or r.name in seen:
                    continue
                if only_new_text and r["text"] in {q[1] for q in quotes}:
                    continue
                quotes.append((" ".join(r["evidence"].split()), r["text"]))
                seen.add(r.name)

        area_counts = g["area"].replace("", "not assigned").value_counts()
        others = [d for d in g["definition"].drop_duplicates() if d != central["definition"]][:5]
        themes.append({
            "theme_id": tid, "stream": stream,
            "working_label": central["label"],
            "definition": central["definition"],
            "area": area_counts.index[0],
            "texts": "; ".join(sorted(g["text"].unique())),
            "example_quotes": "\n".join(f"“{q}” ({t})" for q, t in quotes),
            "other_wordings": "\n".join(others),
            "areas": "; ".join(f"{k} ({v})" for k, v in area_counts.items()),
        })
        docs.append(" ".join(g["definition"]) + " " + " ".join(g["label"]))
        members.append(pos)
    for t, kw in zip(themes, theme_keywords(docs)):
        t["keywords"] = kw

    beliefs = []
    for i, r in enumerate(df.itertuples(index=False), start=1):
        d = r._asdict()
        beliefs.append({
            "belief_id": f"B{i:04d}", "theme_id": d["theme_id"], "stream": stream, "text": d["text"],
            "chunk_id": d.get("chunk_id", ""), "label": d["label"], "definition": d["definition"],
            "stance": d["stance"], "area": d["area"] or "not assigned",
            "evaluation": to_number(d.get("rating_evaluation")),
            "inevitability": to_number(d.get("rating_inevitability")),
            "intertwinement": to_number(d.get("rating_intertwinement")),
            "evidence": " ".join(str(d.get("evidence", "")).split()),
            "quote_verbatim": d.get("evidence_verbatim", ""),
            "note": "overlap duplicate, not counted" if d["duplicate"] else ("" if d["theme_id"] else "not clustered"),
            "confidence": d.get("confidence", ""),
        })

    depicted = []
    ids = list(theme_id.values())
    for i, r in enumerate(dep.to_dict("records"), start=1):
        # Similarity to a theme = mean similarity to its beliefs, the quantity the clustering itself uses
        sims = np.array([float((Xs[pos] @ Xd[i - 1]).mean()) for pos in members])
        j = int(np.argmax(sims)) if len(sims) else -1
        depicted.append({
            "depicted_id": f"D{i:04d}", "stream": stream, "text": nice(r.get("source", "")),
            "chunk_id": r.get("chunk_id", ""), "label": r.get("label", ""), "definition": r.get("definition", ""),
            "area": r.get("area", "") or "not assigned",
            "evidence": " ".join(str(r.get("evidence", "")).split()),
            "nearest_theme": ids[j] if j >= 0 else "",
            "similarity": round(float(sims[j]), 2) if j >= 0 else None,
        })
    return themes, beliefs, depicted, method


# ---------------------------------------------------------------------------
# Workbook
# ---------------------------------------------------------------------------

def write_sheet(ws, columns, rows, freeze, fill_in=()):
    """columns: [(header, key, width)]. Cell values starting with '=' are written as formulas."""
    for j, (header, key, width) in enumerate(columns, start=1):
        c = ws.cell(row=1, column=j, value=header)
        c.font = Font(name=FONT, size=10, bold=True, color="000000" if key in fill_in else "FFFFFF")
        c.fill = FILL_IN if key in fill_in else HEAD_FILL
        c.alignment = Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[get_column_letter(j)].width = width
    for i, row in enumerate(rows, start=2):
        for j, (_, key, _) in enumerate(columns, start=1):
            v = row.get(key)
            c = ws.cell(row=i, column=j, value=v(i) if callable(v) else v)
            c.font = Font(name=FONT, size=10)
            c.alignment = WRAP
            if key in fill_in:
                c.fill = FILL_IN
    ws.row_dimensions[1].height = 30
    ws.freeze_panes = freeze
    if rows:
        ws.auto_filter.ref = f"A1:{get_column_letter(len(columns))}{len(rows) + 1}"


def col_of(columns, key):
    return get_column_letter([k for _, k, _ in columns].index(key) + 1)


def build_workbook(themes, beliefs, depicted, meta, match):
    wb = Workbook()
    about = wb.active
    about.title = "About"
    ws_t, ws_c, ws_d, ws_b = (wb.create_sheet(n) for n in ("Themes", "Coverage", "Depicted", "Beliefs"))

    B_COLS = [("belief_id", "belief_id", 10), ("theme_id", "theme_id", 10), ("stream", "stream", 13),
              ("text", "text", 30), ("chunk_id", "chunk_id", 30), ("label", "label", 26),
              ("definition", "definition", 52), ("stance", "stance", 12), ("area", "area", 22),
              ("evaluation", "evaluation", 11), ("inevitability", "inevitability", 12),
              ("intertwinement", "intertwinement", 14), ("evidence", "evidence", 60),
              ("quote_verbatim", "quote_verbatim", 13), ("note", "note", 24), ("confidence", "confidence", 11)]
    D_COLS = [("depicted_id", "depicted_id", 11), ("stream", "stream", 13), ("text", "text", 30),
              ("chunk_id", "chunk_id", 30), ("label", "label", 26), ("definition", "definition", 52),
              ("area", "area", 22), ("evidence", "evidence", 60), ("nearest_theme", "nearest_theme", 13),
              ("similarity", "similarity", 10), ("match", "match", 11),
              ("nearest_theme_definition", "nearest_def", 52),
              ("reviewer_decision", "reviewer_decision", 18), ("notes", "notes", 34)]
    T_COLS = [("theme_id", "theme_id", 9), ("stream", "stream", 13), ("theme_name", "theme_name", 24),
              ("working_label", "working_label", 26), ("definition", "definition", 52),
              ("keywords", "keywords", 30), ("area", "area", 22),
              ("n_beliefs", "n_beliefs", 9), ("n_texts", "n_texts", 8), ("texts", "texts", 34),
              ("endorses", "endorses", 9), ("conditional", "conditional", 10), ("denies", "denies", 8),
              ("mentions", "mentions", 9),
              ("evaluation_mean", "evaluation_mean", 11), ("evaluation_n", "evaluation_n", 10),
              ("inevitability_mean", "inevitability_mean", 12), ("inevitability_n", "inevitability_n", 11),
              ("intertwinement_mean", "intertwinement_mean", 13), ("intertwinement_n", "intertwinement_n", 13),
              ("depicted_support", "depicted_support", 10),
              ("example_quotes", "example_quotes", 70), ("other_wordings", "other_wordings", 52),
              ("areas", "areas", 30),
              ("decision", "decision", 12), ("merge_with", "merge_with", 12), ("notes", "notes", 40)]

    bc = lambda k: f"Beliefs!${col_of(B_COLS, k)}:${col_of(B_COLS, k)}"
    dc = lambda k: f"Depicted!${col_of(D_COLS, k)}:${col_of(D_COLS, k)}"
    texts = sorted({b["text"] for b in beliefs})
    cov_first, cov_last = "B", get_column_letter(1 + len(texts))
    text_range = f"Coverage!${cov_first}$3:${cov_last}$3"
    THRESH = "About!$B$12"

    # ── Beliefs ──
    write_sheet(ws_b, B_COLS, beliefs, "C2")

    # ── Depicted ──
    t_id, t_def = f"Themes!${col_of(T_COLS, 'theme_id')}:${col_of(T_COLS, 'theme_id')}", \
                  f"Themes!${col_of(T_COLS, 'definition')}:${col_of(T_COLS, 'definition')}"
    for d in depicted:
        nt, sm = col_of(D_COLS, "nearest_theme"), col_of(D_COLS, "similarity")
        d["match"] = (lambda nt=nt, sm=sm: (lambda i: f'=IF({nt}{i}="","unmatched",IF({sm}{i}>={THRESH},"matched","unmatched"))'))()
        d["nearest_def"] = (lambda nt=nt: (lambda i: f'=IFERROR(INDEX({t_def},MATCH({nt}{i},{t_id},0)),"")'))()
    write_sheet(ws_d, D_COLS, depicted, "C2", fill_in=("reviewer_decision", "notes"))
    for i in range(2, len(depicted) + 2):
        ws_d[f"{col_of(D_COLS, 'similarity')}{i}"].number_format = "0.00"

    # ── Themes ──
    for t in themes:
        t["n_beliefs"] = lambda i: f"=COUNTIFS({bc('theme_id')},$A{i})"
        t["n_texts"] = lambda i: f"=SUMPRODUCT(--(COUNTIFS({bc('theme_id')},$A{i},{bc('text')},{text_range})>0))"
        for s in STANCES:
            t[s] = (lambda s=s: (lambda i: f'=COUNTIFS({bc("theme_id")},$A{i},{bc("stance")},"{s}")'))()
        for r in RATINGS:
            t[f"{r}_mean"] = (lambda r=r: (lambda i: f'=IFERROR(AVERAGEIFS({bc(r)},{bc("theme_id")},$A{i}),"")'))()
            t[f"{r}_n"] = (lambda r=r: (lambda i: f'=COUNTIFS({bc("theme_id")},$A{i},{bc(r)},">0")'))()
        t["depicted_support"] = lambda i: f'=COUNTIFS({dc("nearest_theme")},$A{i},{dc("match")},"matched")'
    write_sheet(ws_t, T_COLS, themes, "E2", fill_in=("theme_name", "decision", "merge_with", "notes"))
    for i in range(2, len(themes) + 2):
        for r in RATINGS:
            ws_t[f"{col_of(T_COLS, r + '_mean')}{i}"].number_format = "0.0"
    if themes:
        dv = DataValidation(type="list", formula1='"keep,merge,split,drop"', allow_blank=True)
        ws_t.add_data_validation(dv)
        dv.add(f"{col_of(T_COLS, 'decision')}2:{col_of(T_COLS, 'decision')}{len(themes) + 1}")

    # ── Coverage ──
    f10, bold = Font(name=FONT, size=10), Font(name=FONT, size=10, bold=True)
    ws_c["A1"] = "Stated beliefs by area and text (overlap duplicates not counted)"
    ws_c["A1"].font = Font(name=FONT, size=11, bold=True)
    heads = ["area"] + texts + ["all texts", "themes mainly in this area"]
    for j, h in enumerate(heads, start=1):
        c = ws_c.cell(row=3, column=j, value=h)
        c.font = Font(name=FONT, size=10, bold=True, color="FFFFFF")
        c.fill = HEAD_FILL
        c.alignment = Alignment(wrap_text=True, vertical="center")
        ws_c.column_dimensions[get_column_letter(j)].width = 26 if j == 1 else 18
    ws_c.row_dimensions[3].height = 44
    area_rows = AREAS + ["not assigned"]
    tot_col, th_col = get_column_letter(len(texts) + 2), get_column_letter(len(texts) + 3)
    for i, a in enumerate(area_rows, start=4):
        ws_c.cell(row=i, column=1, value=a).font = f10
        for j in range(len(texts)):
            L = get_column_letter(j + 2)
            ws_c[f"{L}{i}"] = f'=COUNTIFS({bc("area")},$A{i},{bc("text")},{L}$3,{bc("theme_id")},"T*")'
            ws_c[f"{L}{i}"].font = f10
        ws_c[f"{tot_col}{i}"] = f"=SUM({cov_first}{i}:{cov_last}{i})"
        ws_c[f"{th_col}{i}"] = f"=COUNTIFS(Themes!${col_of(T_COLS, 'area')}:${col_of(T_COLS, 'area')},$A{i})"
        ws_c[f"{tot_col}{i}"].font = ws_c[f"{th_col}{i}"].font = f10
    last = 3 + len(area_rows)
    ws_c.cell(row=last + 1, column=1, value="all areas").font = bold
    for j in range(len(texts) + 2):
        L = get_column_letter(j + 2)
        ws_c[f"{L}{last + 1}"] = f"=SUM({L}4:{L}{last})"
        ws_c[f"{L}{last + 1}"].font = bold
    ws_c.freeze_panes = "B4"

    # ── About ──
    about.column_dimensions["A"].width = 30
    about.column_dimensions["B"].width = 100
    lines = [
        ("Suffering beliefs: master file for framework generation", None),
        ("", None),
        ("Stream", meta["stream"]),
        ("Run folder", meta["run"]),
        ("Run date", meta["run_date"]),
        ("Prompts", meta["prompts"]),
        ("Built", meta["built"]),
        ("Grouping method", meta["method"]),
        ("Stated beliefs counted", '=COUNTIFS(Beliefs!$B:$B,"T*")-1'),     # minus the header "theme_id"
        ("Themes", "=COUNTA(Themes!$A:$A)-1"),
        ("Depicted themes", "=COUNTA(Depicted!$A:$A)-1"),
        ("Match threshold", match),
        ("", None),
        ("Sheets", None),
        ("Themes", "One row per belief theme. A theme is a group of stated beliefs with similar definitions. "
                   "The groups are a first draft for the team to name, merge and split. They are not the classification."),
        ("Coverage", "Stated beliefs by area and text. Empty cells show where the texts say little."),
        ("Depicted", "Themes a story shows without stating them, each with the stated theme it is closest to. "
                     "Similarity is the mean similarity between the depicted theme and that theme's beliefs. "
                     "A depicted theme supports a stated theme only when it reaches the match threshold."),
        ("Beliefs", "Every stated belief with its theme. Use it to trace a theme back to the text."),
        ("", None),
        ("What to fill in", "Yellow columns. Themes: theme_name (for example \"Suffering as teacher\"), decision "
                            "(keep, merge, split or drop), merge_with (for example T004), notes. "
                            "Depicted: reviewer_decision (for example \"supports T004\" or \"new theme\"), notes."),
        ("What updates by itself", "Counts, means and coverage are formulas. They update when a theme_id is changed "
                                   "on the Beliefs sheet or a nearest_theme on the Depicted sheet."),
        ("What is fixed", "Definition, keywords, example quotes, text lists and similarity are set when the file is "
                          "built. Run build_master.py again to refresh them."),
        ("", None),
        ("Columns", None),
        ("definition", "The belief closest to the centre of the theme, in the coder's words."),
        ("keywords", "The words that most set this theme's definitions apart from the other themes'."),
        ("area", "The area most of the theme's beliefs fall in. The areas column gives the full breakdown."),
        ("endorses ... mentions", "Number of beliefs with each stance. Denied beliefs are stated in positive form."),
        ("evaluation_mean etc.", "Mean of the 1-5 rating over the theme's rated beliefs; the _n column is how many "
                                 "were rated. Evaluation: 1 purely harmful, 5 can enrich a life. Inevitability: "
                                 "1 avoidable, 5 part of every life. Intertwinement: 1 separate from the good "
                                 "things in life, 5 bound up with them."),
        ("depicted_support", "Number of depicted themes matched to this theme."),
        ("stream", "Where the belief comes from. Beliefs from interviews, surveys or reviews can be appended "
                   "to the Beliefs sheet with their own stream name."),
    ]
    for i, (k, v) in enumerate(lines, start=1):
        a, b = about.cell(row=i, column=1, value=k), about.cell(row=i, column=2, value=v)
        a.font = Font(name=FONT, size=14 if i == 1 else 10, bold=True)
        b.font = Font(name=FONT, size=10)
        a.alignment = Alignment(vertical="top")
        b.alignment = Alignment(wrap_text=True, vertical="top", horizontal="left")
    assert about["A12"].value == "Match threshold"          # the Depicted sheet's formulas point at B12
    about["B12"].fill = FILL_IN
    about["B12"].comment = Comment(
        "Similarity at or above which a depicted theme counts as supporting its nearest stated theme. "
        "The default is the level at which the clustering itself would have put the two together "
        "(1 minus the clustering threshold). Raise it to be stricter. "
        "Change it here and the match column and depicted_support update.", "build_master.py")
    return wb


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    ap.add_argument("--run", default=config.RESULTS_DIR, help="the run's results folder")
    ap.add_argument("--stream", default="text analysis", help="name written in the stream column")
    ap.add_argument("--match", type=float, default=None,
                    help="similarity at which a depicted theme counts as supporting a stated theme "
                         "(default: 1 minus the clustering threshold)")
    args = ap.parse_args()

    df, dep, log, grouping = load_run(args.run)
    centred = bool(grouping.get("centred", False))
    if args.match is None:
        t = grouping.get("threshold")
        args.match = round(1 - t, 2) if t else (0.20 if centred else 0.55)
    themes, beliefs, depicted, method = build_tables(df, dep, args.stream, centred)
    any_row = df.iloc[0] if len(df) else {}
    meta = {
        "stream": args.stream,
        "run": os.path.basename(os.path.normpath(args.run)),
        "run_date": str(log.get("run_date") or any_row.get("run_date", "")).split("T")[0],
        "prompts": " / ".join(p for p in (log.get("system_prompt") or any_row.get("prompt_system", ""),
                                          log.get("tag_prompt") or any_row.get("prompt_tag", ""),
                                          log.get("rate_prompt") or any_row.get("prompt_rate", "")) if p),
        "built": datetime.date.today().isoformat(),
        "method": ("sentence embeddings (" + method + ")" if method != "tfidf"
                   else "shared words (TF-IDF); install sentence-transformers for better groups")
                  + (", common part removed" if centred else "")
                  + ", average linkage"
                  + (f", {grouping['k']} clusters requested" if grouping.get("k")
                     else f", distance threshold {grouping['threshold']}" if grouping.get("threshold") else ""),
    }
    wb = build_workbook(themes, beliefs, depicted, meta, args.match)
    out = os.path.join(args.run, "framework_master.xlsx")
    wb.save(out)
    n_counted = sum(1 for b in beliefs if b["theme_id"])
    print(f"{len(themes)} themes from {n_counted} stated beliefs; {len(depicted)} depicted themes")
    print(f"Master file → {out}")


if __name__ == "__main__":
    main()
