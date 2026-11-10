"""Evaluate TF-IDF vs Sentence-BERT on the seed benchmark.

Run from the repository root:  python -m portal.evaluate
Writes portal/eval/results.json and the figures used in the paper.
"""
import json
import time
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import precision_recall_fscore_support, roc_auc_score, roc_curve

from .data.seed import QUERIES, REPOSITORY
from .similarity import DOMAINS, clean, combined, engine

OUT = Path(__file__).resolve().parent / "eval"
OUT.mkdir(exist_ok=True)

titles = [t for _d, t, _a in REPOSITORY]
corpus = [combined(t, a) for _d, t, a in REPOSITORY]
q_texts = [combined(t, a) for _k, _tg, t, a in QUERIES]
is_para = np.array([k == "paraphrase" for k, *_ in QUERIES])
targets = [titles.index(tg) if tg else -1 for _k, tg, *_ in QUERIES]


def tfidf_matrix():
    vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
    m = vec.fit_transform([clean(t) for t in corpus])
    q = vec.transform([clean(t) for t in q_texts])
    return (q @ m.T).toarray()


def sbert_matrix():
    rv = engine.embed(corpus)
    t0 = time.perf_counter()
    qv = engine.embed(q_texts)
    per_query_ms = (time.perf_counter() - t0) * 1000 / len(q_texts)
    return qv @ rv.T, rv, per_query_ms


def metrics(S, name):
    top = S.max(axis=1)
    ranks = []
    for i in np.where(is_para)[0]:
        order = np.argsort(-S[i])
        ranks.append(int(np.where(order == targets[i])[0][0]) + 1)
    ranks = np.array(ranks)
    auc = roc_auc_score(is_para, top)
    # best threshold by F1 (reported for analysis) and fixed operating threshold
    best = max(((t, *precision_recall_fscore_support(is_para, top >= t, average="binary", zero_division=0)[:3])
                for t in np.unique(top)), key=lambda x: x[3])
    fpr, tpr, _ = roc_curve(is_para, top)
    return {
        "method": name,
        "hit@1": float(np.mean(ranks == 1)),
        "hit@5": float(np.mean(ranks <= 5)),
        "mrr": float(np.mean(1 / ranks)),
        "auc": float(auc),
        "best_threshold": float(best[0]),
        "precision": float(best[1]), "recall": float(best[2]), "f1": float(best[3]),
        "mean_top_paraphrase": float(top[is_para].mean()),
        "mean_top_novel": float(top[~is_para].mean()),
        "top_scores": top.tolist(),
        "roc": {"fpr": fpr.tolist(), "tpr": tpr.tolist()},
    }


def fixed_threshold(S, t):
    top = S.max(axis=1)
    p, r, f, _ = precision_recall_fscore_support(is_para, top >= t, average="binary", zero_division=0)
    return {"threshold": t, "precision": float(p), "recall": float(r), "f1": float(f)}


def domain_accuracy(rv):
    names = list(DOMAINS)
    dv = engine.embed(DOMAINS.values())
    pred = np.argmax(rv @ dv.T, axis=1)
    gold = np.array([names.index(d) for d, *_ in REPOSITORY])
    cm = np.zeros((len(names), len(names)), dtype=int)
    for g_, p_ in zip(gold, pred):
        cm[g_, p_] += 1
    return float(np.mean(pred == gold)), cm.tolist(), names


def main():
    T = tfidf_matrix()
    S, rv, per_q = sbert_matrix()
    res = {
        "repository_size": len(REPOSITORY),
        "queries": {"paraphrase": int(is_para.sum()), "novel": int((~is_para).sum())},
        "tfidf": metrics(T, "TF-IDF + cosine"),
        "sbert": metrics(S, "SBERT + cosine"),
        "sbert_at_portal_threshold": fixed_threshold(S, 0.55),
        "sbert_ms_per_query": per_q,
    }
    acc, cm, names = domain_accuracy(rv)
    res["domain"] = {"accuracy": acc, "confusion": cm, "labels": names}
    # end-to-end latency of one portal check (embed + SBERT + TF-IDF + domain), CPU only
    records = [{"id": i, "title": t, "abstract": a, "domain": d, "embedding": v}
               for i, ((d, t, a), v) in enumerate(zip(REPOSITORY, rv))]
    engine.check("warm up", "warm up text", records)
    times = [engine.check(t, a, records)["elapsed_ms"] for _k, _tg, t, a in QUERIES]
    res["check_latency_ms"] = {"mean": float(np.mean(times)), "p95": float(np.percentile(times, 95))}
    print("check latency ms", res["check_latency_ms"])
    (OUT / "results.json").write_text(json.dumps(res, indent=2))
    for k in ("tfidf", "sbert"):
        m = res[k]
        print(f"{m['method']:18s} Hit@1={m['hit@1']:.3f} Hit@5={m['hit@5']:.3f} MRR={m['mrr']:.3f} "
              f"AUC={m['auc']:.3f} bestT={m['best_threshold']:.3f} P={m['precision']:.3f} R={m['recall']:.3f} "
              f"F1={m['f1']:.3f} para={m['mean_top_paraphrase']:.3f} novel={m['mean_top_novel']:.3f}")
    print("SBERT @0.55:", res["sbert_at_portal_threshold"])
    print(f"Domain accuracy {acc:.3f}; {per_q:.1f} ms/query embed")


if __name__ == "__main__":
    main()
