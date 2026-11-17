"""
Group the open-coded beliefs into candidate themes.

Input:   results/open_codes.csv   (written by pipeline.py with tag_open_v1)
Output:  results/open_code_clusters.csv   every belief, with its cluster and map position
         results/cluster_summary.csv      one row per cluster, for the consolidation meeting

Each belief's one-sentence definition is turned into a vector, beliefs with similar
definitions are grouped, and each group is summarised. The clusters are a first
draft for the team to name, merge and split. They are not the classification.

Usage:
    python cluster_open_codes.py                 # default grouping
    python cluster_open_codes.py --scan          # show cluster counts at several thresholds
    python cluster_open_codes.py --threshold 0.5 # looser groups (fewer, larger clusters)
    python cluster_open_codes.py --k 30          # ask for exactly 30 clusters

Needs: pandas, numpy, scikit-learn and sentence-transformers
(`pip install sentence-transformers`; the first run downloads a small model).
Without sentence-transformers the script still runs, grouping by shared words
(TF-IDF), but that works poorly on one-sentence definitions and is only a stopgap.
"""

import argparse
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
    ap.add_argument("--threshold", type=float, default=0.45,
                    help="cosine distance at which groups stop merging (0-1); higher = fewer, larger clusters")
    ap.add_argument("--k", type=int, default=None, help="exact number of clusters (overrides --threshold)")
    ap.add_argument("--scan", action="store_true", help="print cluster counts for a range of thresholds and stop")
    args = ap.parse_args()

    df = pd.read_csv(args.input, dtype=str).fillna("")
    df["duplicate"] = mark_duplicates(df)
    keep = df[~df["duplicate"] & (df["definition"].str.strip() != "")].copy()
    print(f"{len(df)} beliefs read; {int(df['duplicate'].sum())} overlap duplicates set aside; clustering {len(keep)}")
    if len(keep) < 3:
        raise SystemExit("Too few beliefs to cluster.")

    X, method = embed(keep["definition"])

    if args.scan:
        print("threshold  clusters  single-belief clusters")
        for t in (0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.70):
            sizes = pd.Series(cluster(X, threshold=t)).value_counts()
            print(f"   {t:.2f}     {len(sizes):5d}     {int((sizes == 1).sum()):5d}")
        return

    keep["cluster"] = cluster(X, threshold=args.threshold, k=args.k)
    xy = PCA(n_components=2).fit_transform(X)            # 2-D map of the beliefs, for plotting
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

    singles = int((summary["n_beliefs"] == 1).sum())
    print(f"method: {method}   clusters: {len(summary)}   single-belief clusters: {singles}")
    print(summary[["cluster", "n_beliefs", "n_sources", "top_labels"]].head(15).to_string(index=False))
    print(f"\nBeliefs with clusters → {out_path}\nCluster summary       → {sum_path}")


if __name__ == "__main__":
    main()
