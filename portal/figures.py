"""Draw the paper's diagrams and result charts into portal/eval/figures/.

Run from the repository root after evaluate.py:  python -m portal.figures
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

HERE = Path(__file__).resolve().parent
OUT = HERE / "eval" / "figures"
OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.family": "Times New Roman", "font.size": 9})

DARK, TEAL, LIGHT, GREY = "#1b1b1b", "#1f8f8f", "#e8f4f4", "#f2f2f2"


def box(ax, x, y, w, h, text, fc=LIGHT, ec=DARK, bold=False, size=8.5, shape="round"):
    style = "round,pad=0.02,rounding_size=0.08" if shape == "round" else "square,pad=0.02"
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle=style, fc=fc, ec=ec, lw=0.9))
    ax.text(x, y, text, ha="center", va="center", fontsize=size, weight="bold" if bold else "normal", wrap=True)


def diamond(ax, x, y, w, h, text, size=8):
    ax.fill([x, x + w / 2, x, x - w / 2], [y + h / 2, y, y - h / 2, y], fc="white", ec=DARK, lw=0.9)
    ax.text(x, y, text, ha="center", va="center", fontsize=size)


def arrow(ax, p, q, text=None, rad=0.0, tx=0.0, ty=0.0):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=9, lw=0.9, color=DARK,
                                 connectionstyle=f"arc3,rad={rad}", shrinkA=0, shrinkB=0))
    if text:
        ax.text((p[0] + q[0]) / 2 + tx, (p[1] + q[1]) / 2 + ty, text, fontsize=7.5, ha="center", va="center",
                bbox=dict(fc="white", ec="none", pad=0.6))


def save(fig, name):
    fig.savefig(OUT / name, dpi=300, bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)


# ------------------------------------------------------------ architecture
def architecture():
    fig, ax = plt.subplots(figsize=(7.0, 4.3))
    ax.set_xlim(0, 10.6); ax.set_ylim(0, 6.0); ax.axis("off")
    W = 8.55  # width of the four internal layers; external services sit to the right
    layers = [(5.2, "Users"), (3.75, "Application layer (Flask)"),
              (2.2, "Processing layer"), (0.7, "Data layer (SQLite prototype / PostgreSQL)")]
    for y, name in layers:
        ax.add_patch(FancyBboxPatch((0.05, y - 0.62), W, 1.24, boxstyle="round,pad=0,rounding_size=0.1",
                                    fc=GREY, ec="#999999", lw=0.6))
        mid = name.startswith("Application")
        ax.text(5.5 if mid else 0.2, y + 0.47, name, fontsize=7.5, style="italic", va="center",
                ha="center" if mid else "left", color="#444444")
    ax.add_patch(FancyBboxPatch((8.8, 1.58), 1.75, 2.79, boxstyle="round,pad=0,rounding_size=0.1",
                                fc="white", ec="#999999", lw=0.6, ls="--"))
    ax.text(9.675, 4.18, "External services", fontsize=7.5, style="italic", ha="center", color="#444444")
    xs = [0.72 + i * 1.18 for i in range(7)]
    mods = ["Check\nmy idea", "Check my\ndocument", "Report &\nsubmit", "Faculty\nreview", "Search &\ninsights",
            "Verify\nreport", "Google\nsign-in"]
    for x, t in zip(xs, mods):
        box(ax, x, 3.6, 1.06, 0.62, t, size=7.5)
    eng = ["Text\npreparation", "SBERT\nembedding", "Cosine\nranking", "TF-IDF word\noverlap", "Domain\nclassifier",
           "HMAC\nsigning", "iThenticate\nclient"]
    for x, t in zip(xs, eng):
        box(ax, x, 2.05, 1.06, 0.62, t, fc="white", size=7.5)
    users = [((xs[0] + xs[1]) / 2, "Student (verified\n@mlrit.ac.in)", [xs[0], xs[1]]),
             (xs[3], "Faculty reviewer", [xs[3]]),
             (xs[5] + 0.3, "External verifier\n(placement / NAAC)", [xs[5]])]
    for x, t, targets in users:
        box(ax, x, 5.05, 2.0, 0.6, t, fc="white", size=8)
        for tx in targets:
            arrow(ax, (x + (tx - x) * 0.35, 4.75), (tx, 3.91))
    box(ax, 9.675, 3.6, 1.55, 0.62, "Google identity\n(OpenID Connect)", fc=LIGHT, size=7.5)
    box(ax, 9.675, 2.05, 1.55, 0.72, "iThenticate v2 API\n(college licence:\ninternet, journals)", fc=LIGHT, size=7.2)
    ax.annotate("", xy=(8.9, 3.6), xytext=(xs[6] + 0.53, 3.6),
                arrowprops=dict(arrowstyle="<|-|>", lw=1.0, color=DARK, mutation_scale=9))
    ax.annotate("", xy=(8.9, 2.05), xytext=(xs[6] + 0.53, 2.05),
                arrowprops=dict(arrowstyle="<|-|>", lw=1.0, color=DARK, mutation_scale=9))
    tabs = ["users", "projects (+ 384-d\nembedding)", "checks\n(idea reports)", "doc_checks\n(iThenticate)", "reviews"]
    for i, t in enumerate(tabs):
        box(ax, 0.98 + i * 1.66, 0.58, 1.5, 0.6, t, fc=LIGHT, shape="square", size=7.5)
    for x0, lbl in ((2.55, "proposal text / scores, matches, domain"), ):
        ax.annotate("", xy=(x0, 2.37), xytext=(x0, 3.28),
                    arrowprops=dict(arrowstyle="<|-|>", lw=1.6, color=TEAL, mutation_scale=12))
        ax.text(x0 + 0.1, 2.83, lbl, fontsize=6.8, va="center", color="#145f5f")
    ax.annotate("", xy=(4.3, 0.9), xytext=(4.3, 1.73),
                arrowprops=dict(arrowstyle="<|-|>", lw=1.6, color=TEAL, mutation_scale=12))
    ax.text(4.42, 1.31, "embeddings, signed reports, scores and decisions", fontsize=6.8, va="center", color="#145f5f")
    save(fig, "fig_architecture.png")


# ------------------------------------------------------------ doc sequence
def doc_sequence():
    fig, ax = plt.subplots(figsize=(3.45, 4.6))
    ax.set_xlim(0, 6); ax.set_ylim(0, 10.6); ax.axis("off")
    cols = {"S": 0.7, "P": 3.0, "T": 5.3}
    for k, t in (("S", "Student"), ("P", "Portal\n(Flask server)"), ("T", "iThenticate\nv2 API")):
        box(ax, cols[k], 10.05, 1.25, 0.7, t, fc=LIGHT if k != "T" else "white", size=7.5)
        ax.plot([cols[k]] * 2, [9.68, 0.2], color="#888888", lw=0.7, ls="--")
    msgs = [
        ("S", "P", "upload file + accept EULA"),
        ("P", "P", "type, size and weekly-quota check"),
        ("P", "T", "POST /submissions"),
        ("P", "T", "PUT /submissions/{id}/original"),
        ("P", "T", "GET /submissions/{id} → COMPLETE"),
        ("P", "T", "PUT /similarity (add_to_index: false)"),
        ("P", "T", "GET /similarity → overall_match_%"),
        ("P", "P", "store score, SHA-256; sign"),
        ("P", "S", "similarity % and DC- code"),
        ("S", "T", "full report via viewer-url"),
    ]
    y = 9.15
    for a, b, t in msgs:
        if a == b:
            x = cols[a]
            ax.plot([x, x + 0.45, x + 0.45, x], [y + 0.12, y + 0.12, y - 0.18, y - 0.18], color=DARK, lw=0.8)
            ax.annotate("", xy=(x, y - 0.18), xytext=(x + 0.2, y - 0.18),
                        arrowprops=dict(arrowstyle="-|>", lw=0.8, color=DARK, mutation_scale=7))
            ax.text(x + 0.55, y - 0.03, t, fontsize=6.6, va="center")
        else:
            dashed = (a == "P" and b == "S")
            ax.annotate("", xy=(cols[b], y - 0.1), xytext=(cols[a], y - 0.1),
                        arrowprops=dict(arrowstyle="-|>", lw=0.8, color=TEAL if b == "T" or a == "S" and b == "T" else DARK,
                                        mutation_scale=8, ls="--" if dashed else "-"))
            ax.text((cols[a] + cols[b]) / 2, y + 0.1, t, fontsize=6.6, ha="center", va="bottom")
        y -= 0.9
    save(fig, "fig_doc_sequence.png")


# ----------------------------------------------------------------- workflow
def workflow():
    fig, ax = plt.subplots(figsize=(3.45, 6.9))
    ax.set_xlim(0, 5); ax.set_ylim(0, 13.4); ax.axis("off")
    cx = 2.3
    box(ax, cx, 12.9, 2.6, 0.55, "Student opens portal", fc="white")
    box(ax, cx, 11.95, 2.6, 0.6, "Sign in with Google\n(OpenID Connect)")
    diamond(ax, cx, 10.85, 2.7, 0.95, "Verified\n@mlrit.ac.in?")
    box(ax, cx, 9.75, 2.6, 0.6, "Enter title and abstract")
    box(ax, cx, 8.75, 2.6, 0.75, "Embed text (SBERT);\ncosine vs. repository")
    box(ax, cx, 7.65, 2.6, 0.75, "Report: originality score,\ntop-5 matches, code")
    diamond(ax, cx, 6.45, 2.7, 1.0, "Student satisfied\nwith score?")
    box(ax, cx, 5.3, 2.6, 0.6, "Submit for faculty review")
    box(ax, cx, 4.3, 2.6, 0.65, "Faculty inspects report\nand closest projects")
    diamond(ax, cx, 3.1, 2.7, 1.0, "Decision")
    box(ax, 0.75, 1.55, 1.35, 0.6, "Approved:\nadd to repository", size=7.5)
    box(ax, 2.3, 1.55, 1.35, 0.6, "Revision\nrequested", size=7.5)
    box(ax, 3.85, 1.55, 1.35, 0.6, "Rejected", size=7.5)
    box(ax, 0.75, 0.45, 1.35, 0.55, "Report verifiable\nby code", fc="white", size=7.5)
    box(ax, 4.5, 10.85, 0.9, 0.5, "Access\ndenied", fc="white", size=7.5)
    seq = [(12.62, 12.25), (11.65, 11.33), (10.38, 10.05), (9.45, 9.13), (8.37, 8.03), (7.27, 6.95),
           (5.95, 5.6), (5.0, 4.63), (3.97, 3.6)]
    for a, b in seq:
        arrow(ax, (cx, a), (cx, b))
    ax.text(cx + 0.15, 10.22, "yes", fontsize=7.5); ax.text(cx + 0.15, 5.78, "yes", fontsize=7.5)
    arrow(ax, (cx + 1.35, 10.85), (4.05, 10.85), "no", ty=0.15)
    ax.plot([cx - 1.35, 0.25, 0.25], [6.45, 6.45, 9.75], color=DARK, lw=0.9)
    arrow(ax, (0.25, 9.75), (cx - 1.3, 9.75))
    ax.text(0.45, 6.62, "no: revise", fontsize=7.5)
    arrow(ax, (cx - 0.6, 2.85), (0.75, 1.86)); arrow(ax, (cx, 2.6), (cx, 1.86)); arrow(ax, (cx + 0.6, 2.85), (3.85, 1.86))
    arrow(ax, (0.75, 1.25), (0.75, 0.73))
    ax.plot([2.3 + 0.68, 4.85, 4.85], [1.55, 1.55, 1.55], color="none")
    ax.plot([2.3, 2.3, 4.85, 4.85], [1.25, 0.95, 0.95, 9.75], color=DARK, lw=0.9, ls="--")
    arrow(ax, (4.85, 9.75), (cx + 1.3, 9.75))
    save(fig, "fig_workflow.png")


# ------------------------------------------------------------------ results
def results():
    res = json.loads((HERE / "eval" / "results.json").read_text())
    t, s = res["tfidf"], res["sbert"]
    keys = [("hit@1", "Hit@1"), ("hit@5", "Hit@5"), ("mrr", "MRR"), ("auc", "ROC-AUC"), ("f1", "Best F1")]
    fig, ax = plt.subplots(figsize=(3.45, 2.1))
    xs = range(len(keys)); w = 0.38
    b1 = ax.bar([x - w / 2 for x in xs], [t[k] for k, _ in keys], w, label="TF-IDF + cosine", color="#bdbdbd", ec=DARK, lw=0.5)
    b2 = ax.bar([x + w / 2 for x in xs], [s[k] for k, _ in keys], w, label="SBERT + cosine", color=TEAL, ec=DARK, lw=0.5)
    for bars in (b1, b2):
        for b in bars:
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.015, f"{b.get_height():.2f}", ha="center", fontsize=6.5)
    ax.set_xticks(list(xs)); ax.set_xticklabels([n for _, n in keys], fontsize=7.5)
    ax.tick_params(axis="y", labelsize=7.5)
    ax.set_ylim(0, 1.32); ax.set_yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0]); ax.set_ylabel("Score", fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(fontsize=7, frameon=False, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 1.04))
    save(fig, "fig_metrics.png")

    n_para = res["queries"]["paraphrase"]
    fig, axes = plt.subplots(1, 2, figsize=(3.45, 2.0), sharey=False)
    for ax, m, name, thr in [(axes[0], t, "TF-IDF", None), (axes[1], s, "SBERT", 0.55)]:
        top = m["top_scores"]
        para, novel = top[:n_para], top[n_para:]
        ax.scatter([0 + (i % 5 - 2) * 0.05 for i in range(len(para))], para, s=10, color=TEAL, ec=DARK, lw=0.3, label="reworded")
        ax.scatter([1 + (i % 5 - 2) * 0.05 for i in range(len(novel))], novel, s=10, color="white", ec=DARK, lw=0.6, label="new idea")
        if thr:
            ax.axhline(thr, ls="--", lw=0.7, color="#c0392b"); ax.text(1.45, thr + 0.01, "τ = 0.55", fontsize=6.5, ha="right", color="#c0392b")
        ax.set_xticks([0, 1]); ax.set_xticklabels(["reworded", "new idea"], fontsize=7)
        ax.set_xlim(-0.5, 1.5); ax.set_ylim(0, 1); ax.set_title(name, fontsize=8)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("Highest similarity", fontsize=8)
    fig.tight_layout(w_pad=1.0)
    save(fig, "fig_scores.png")


def screenshots():
    """Crop the 1.5x browser captures to their content so they read well in a column."""
    from PIL import Image
    src = HERE / "eval" / "screens"
    crops = {"03_report_original": (0, 0, 2160, 1170), "04_report_overlap": (0, 0, 2160, 1110),
             "06_review": (0, 0, 2160, 990), "07_verify": (480, 150, 1680, 840),
             "01_login": (670, 105, 1490, 690), "12_doc_report": (0, 150, 2160, 810),
             "11_doc_check": (0, 150, 2160, 960), "13_verify_doc": (480, 150, 1680, 1000), "08_search": (0, 0, 2160, 900)}
    for name, box_ in crops.items():
        p = src / f"{name}.png"
        if p.exists():
            Image.open(p).crop(box_).save(OUT / f"shot_{name}.png")


if __name__ == "__main__":
    architecture(); doc_sequence(); workflow(); results(); screenshots()
    print("figures written to", OUT)
