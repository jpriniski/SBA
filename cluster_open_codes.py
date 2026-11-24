"""
Group the open-coded beliefs into candidate themes.

Input:   open_codes.csv in the current run's results folder (stated beliefs only).
         Depicted themes are a separate file and are not clustered unless you ask:
         python cluster_open_codes.py --input results/<run>/depicted_themes.csv
Output:  results/open_code_clusters.csv   every belief, with its cluster and map position
         results/cluster_summary.csv      one row per cluster, for the consolidation meeting
         results/cluster_meta.json        how the grouping was done (read by build_master.py)

Each belief's one-sentence definition is turned into a vector, beliefs with similar
definitions are grouped, and each group is summarised. The clusters are a first
draft for the team to name, merge and split. They are not the classification.

Every definition is about suffering, so the vectors share a large common part. Left in,
it makes most beliefs look alike and the grouping collapses into one very large cluster.
By default the common part (the mean vector) is removed before grouping. --no-centre
keeps the vectors as they are, which is how this script worked before.

Usage:
    python cluster_open_codes.py                 # default grouping
    python cluster_open_codes.py --scan          # show cluster counts at several thresholds
    python cluster_open_codes.py --threshold 0.85 # looser groups (fewer, larger clusters)
    python cluster_open_codes.py --k 30          # ask for exactly 30 clusters
    python cluster_open_codes.py --no-centre     # earlier behaviour (default threshold 0.45)

Needs: pandas, numpy, scikit-learn and sentence-transformers
(`pip install sentence-transformers`; the first run downloads a small model).
Without sentence-transformers the script still runs, grouping by shared words
(TF-IDF), but that works poorly on one-sentence definitions and is only a stopgap.
"""

import argparse
import datetime
import json
import os
import re

import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering
from sklearn.decomposition import PCA

import config

EMBEDDING_MODEL = "all-MiniLM-L6-v2"


def embed(texts):
    """Unit-length vectors, one per text. Returns (matrix, method name)."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        from sklearn.feature_extraction.text import TfidfVectorizer
        print("[warning] sentence-transformers is not installed, so beliefs are grouped by shared words\n"
              "          (TF-IDF). One-sentence definitions share few words, so expect poor groups:\n"
              "          paraphrases split apart and unrelated beliefs lumped together.\n"
              "          Install it with:  pip install sentence-transformers")
        X = TfidfVectorizer(ngram_range=(1, 2), stop_words="english", sublinear_tf=True
                            ).fit_transform(texts).toarray()
        norms = np.linalg.norm(X, axis=1, keepdims=True)
        return X / np.where(norms == 0, 1, norms), "tfidf"
    model = SentenceTransformer(EMBEDDING_MODEL)
    return np.asarray(model.encode(list(texts), normalize_embeddings=True)), EMBEDDING_MODEL


def remove_common(X):
    """Remove what all the vectors have in common (their mean) and rescale to unit length."""
    Xc = X - X.mean(axis=0)
    norms = np.linalg.norm(Xc, axis=1, keepdims=True)
    flat = norms[:, 0] < 1e-9                    # a vector equal to the mean has nothing left: keep it as it was
    Xc[flat], norms[flat] = X[flat], 1.0
    return Xc / norms


def cluster(X, threshold=None, k=None):
    """Average-linkage clustering on cosine distance. Returns labels numbered from 1, largest first."""
    kw = dict(linkage="average", n_clusters=k, distance_threshold=None if k else threshold)
    try:
        model = AgglomerativeClustering(metric="cosine", **kw)
    except TypeError:                                    # scikit-learn < 1.2
        model = AgglomerativeClustering(affinity="cosine", **kw)
    raw = model.fit_predict(X)
    order = pd.Series(raw).value_counts().index          # largest cluster first
    renumber = {old: new for new, old in enumerate(order, start=1)}
    return np.array([renumber[c] for c in raw])


def mark_duplicates(df):
    """
    Consecutive chunks overlap by ~200 words, so one sentence can be coded twice.
    A belief is a duplicate when an earlier belief from the same source has the
    same stance and the same evidence quote (case and spacing ignored).
    """
    key = (df["source"].astype(str) + "|" + df["stance"].astype(str) + "|" +
           df["evidence"].fillna("").map(lambda s: " ".join(re.findall(r"\w+", s.lower()))))
    has_quote = df["evidence"].fillna("").str.strip() != ""
    return key.duplicated() & has_quote


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    ap.add_argument("--input", default=os.path.join(config.RESULTS_DIR, "open_codes.csv"))
    ap.add_argument("--threshold", type=float, default=None,
                    help="cosine distance at which groups stop merging; higher = fewer, larger clusters "
                         "(default 0.80, or 0.45 with --no-centre)")
    ap.add_argument("--no-centre", action="store_true",
                    help="do not remove the part all definitions share before grouping")
    ap.add_argument("--k", type=int, default=None, help="exact number of clusters (overrides --threshold)")
    ap.add_argument("--scan", action="store_true", help="print cluster counts for a range of thresholds and stop")
    args = ap.parse_args()

    df = pd.read_csv(args.input, dtype=str).fillna("")
    if "stance" not in df:                 # depicted_themes.csv has no stance column
        df["stance"] = "depicts"
    df["duplicate"] = mark_duplicates(df)
    keep = df[~df["duplicate"] & (df["definition"].str.strip() != "")].copy()
    print(f"{len(df)} beliefs read; {int(df['duplicate'].sum())} overlap duplicates set aside; clustering {len(keep)}")
    if len(keep) < 3:
        raise SystemExit("Too few beliefs to cluster.")

    X, method = embed(keep["definition"])
    centred = not args.no_centre
    if centred:
        X = remove_common(X)
    if args.threshold is None:
        args.threshold = 0.80 if centred else 0.45

    if args.scan:
        print("threshold  clusters  single-belief clusters  largest cluster")
        scan = (0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90) if centred else \
               (0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.70)
        for t in scan:
            sizes = pd.Series(cluster(X, threshold=t)).value_counts()
            print(f"   {t:.2f}     {len(sizes):5d}     {int((sizes == 1).sum()):5d}"
                  f"                   {int(sizes.iloc[0]):5d}")
        print("\nA good setting has few single-belief clusters and no cluster that holds a large share of all beliefs.")
        return

    keep["cluster"] = cluster(X, threshold=args.threshold, k=args.k)
    dims = min(2, X.shape[0], X.shape[1])                # 2-D map of the beliefs, for plotting
    xy = np.zeros((len(keep), 2))
    xy[:, :dims] = PCA(n_components=dims).fit_transform(X)
    keep["pca_x"], keep["pca_y"] = xy[:, 0].round(4), xy[:, 1].round(4)

    rows = []
    for c, g in keep.groupby("cluster"):
        idx = [keep.index.get_loc(i) for i in g.index]
        centre = X[idx].mean(axis=0)
        central = g.iloc[int(np.argmax(X[idx] @ centre))]     # the belief closest to the cluster's centre
        rows.append({
            "cluster": c,
            "n_beliefs": len(g),
            "n_sources": g["source"].nunique(),
            "stances": "; ".join(f"{k} ({v})" for k, v in g["stance"].value_counts().items()),
            "top_labels": "; ".join(g["label"].value_counts().index[:4]),
            "central_definition": central["definition"],
            "other_definitions": " | ".join(d for d in g["definition"].drop_duplicates()[:6]
                                            if d != central["definition"]),
            "areas": "; ".join(f"{k} ({v})" for k, v in
                               g["area"].replace("", "not assigned").value_counts().items()) if "area" in g else "",
            # For the consolidation meeting
            "theme_name": "", "decision": "", "notes": "",
        })
    summary = pd.DataFrame(rows).sort_values("cluster")

    out = df.join(keep[["cluster", "pca_x", "pca_y"]])
    out_path = os.path.join(config.RESULTS_DIR, "open_code_clusters.csv")
    sum_path = os.path.join(config.RESULTS_DIR, "cluster_summary.csv")
    out.to_csv(out_path, index=False)
    summary.to_csv(sum_path, index=False)
    with open(os.path.join(config.RESULTS_DIR, "cluster_meta.json"), "w", encoding="utf-8") as f:
        json.dump({"date": datetime.date.today().isoformat(), "input": os.path.basename(args.input),
                   "method": method, "centred": centred,
                   "threshold": None if args.k else args.threshold, "k": args.k,
                   "beliefs_clustered": int(len(keep)), "clusters": int(len(summary))}, f, indent=2)

    singles = int((summary["n_beliefs"] == 1).sum())
    print(f"method: {method}   clusters: {len(summary)}   single-belief clusters: {singles}")
    print(summary[["cluster", "n_beliefs", "n_sources", "top_labels"]].head(15).to_string(index=False))
    print(f"\nBeliefs with clusters → {out_path}\nCluster summary       → {sum_path}")


if __name__ == "__main__":
    main()
