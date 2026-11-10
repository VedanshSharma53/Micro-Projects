"""Update the review PPT with the portal, iThenticate integration and real results,
keeping the original template, layouts, fonts and colours.

Run from the repository root (after portal/figures.py):
    python paper/build_ppt.py
Input : paper/MP_TG10_Review_PPT_original.pptx (untouched copy of the team's deck)
Output: paper/MP_TG10_Review_PPT_Updated.pptx
"""
import copy
import json
import re
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parent.parent
FIG = ROOT / "portal" / "eval" / "figures"
SHOTS = ROOT / "portal" / "eval" / "screens"
SRC = ROOT / "paper" / "MP_TG10_Review_PPT_original.pptx"
OUT = ROOT / "paper" / "MP_TG10_Review_PPT_Updated.pptx"
CROPS = ROOT / "paper" / "ppt_assets"
CROPS.mkdir(exist_ok=True)

R = json.loads((ROOT / "portal" / "eval" / "results.json").read_text())
T, S, S55, LAT = R["tfidf"], R["sbert"], R["sbert_at_portal_threshold"], R["check_latency_ms"]

A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
prs = Presentation(SRC)
LAYOUT = prs.slide_layouts.get_by_name("Title and Content")
orig = list(prs.slides)  # original slides, 0-based


# ------------------------------------------------------------------ helpers
def body_of(slide):
    for sh in slide.placeholders:
        if sh.placeholder_format.idx == 1:
            return sh
    return [sh for sh in slide.shapes if sh.has_text_frame][1]


def add_runs(paragraph, text, size=None):
    """Add text to a paragraph; **bold** spans become bold runs."""
    for part in re.split(r"(\*\*[^*]+\*\*)", text):
        if not part:
            continue
        r = paragraph.add_run()
        bold = part.startswith("**")
        r.text = part[2:-2] if bold else part
        r.font.bold = bold or None
        if size:
            r.font.size = Pt(size)
    end = paragraph._p.find(A + "endParaRPr")
    if end is not None:  # schema: endParaRPr must be the paragraph's last child
        paragraph._p.remove(end)
        paragraph._p.append(end)


def clone_para(template, text, size=None):
    """New paragraph after the last one, copying the template's paragraph properties."""
    p_el = copy.deepcopy(template._p)
    for child in list(p_el):
        if child.tag in (A + "r", A + "br", A + "fld"):
            p_el.remove(child)
    template._p.getparent().append(p_el)
    from pptx.text.text import _Paragraph
    para = _Paragraph(p_el, template._parent)
    add_runs(para, text, size)
    end = p_el.find(A + "endParaRPr")
    if end is not None:  # endParaRPr must stay last
        p_el.remove(end)
        p_el.append(end)
    return para


def set_autofit_scale(shape, scale=None, spacing=None):
    bp = shape.text_frame._txBody.bodyPr
    na = bp.find(A + "normAutofit")
    if na is None:
        na = bp.makeelement(A + "normAutofit", {})
        bp.append(na)
    for k in ("fontScale", "lnSpcReduction"):
        if k in na.attrib:
            del na.attrib[k]
    if scale:
        na.set("fontScale", str(int(scale * 100000)))
    if spacing:
        na.set("lnSpcReduction", str(int(spacing * 100000)))


def set_sizes(shape, size):
    for para in shape.text_frame.paragraphs:
        for r in para.runs:
            r.font.size = Pt(size)


def new_slide(title, bullets=None, size=22, body_width=None):
    s = prs.slides.add_slide(LAYOUT)
    s.shapes.title.text = title
    body = body_of(s)
    if bullets is None:
        body._element.getparent().remove(body._element)
        return s
    tf = body.text_frame
    tf.clear()
    for i, item in enumerate(bullets):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.space_after = Pt(4)
        add_runs(para, item, size)
    # Give the body an explicit frame matching the original slides (setting only the width
    # would create a transform at the slide origin).
    body.left, body.top = Emu(129396), Emu(828136)
    body.width, body.height = Inches(body_width) if body_width else Emu(11766430), Emu(5769752)
    return s


def move(slide, index):
    lst = prs.slides._sldIdLst
    el = [e for e in lst if prs.slides.part.related_part(e.rId) is slide.part][0]
    lst.remove(el)
    lst.insert(index, el)


def picture_fit(slide, path, left, top, max_w, max_h, center=True):
    w, h = Image.open(path).size
    scale = min(max_w / w, max_h / h)
    pw, ph = w * scale, h * scale
    x = left + (max_w - pw) / 2 if center else left
    pic = slide.shapes.add_picture(str(path), Inches(x), Inches(top), Inches(pw), Inches(ph))
    pic.line.color.rgb = __import__("pptx.dml.color", fromlist=["RGBColor"]).RGBColor(0xBF, 0xBF, 0xBF)
    pic.line.width = Pt(0.75)
    return pic


def caption(slide, text, left, top, width, size=14):
    tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(0.5))
    tf = tb.text_frame
    tf.word_wrap = True
    para = tf.paragraphs[0]
    para.alignment = 2  # center
    add_runs(para, text, size)
    for r in para.runs:
        r.font.name = "Times New Roman"
        r.font.italic = True
    return tb


def crop(name, box, out):
    p = CROPS / out
    Image.open(SHOTS / f"{name}.png").crop(box).save(p)
    return p


# ---------------------------------------------------- edits to existing slides
# Slide 2: contents
contents = ["Introduction", "SIH-2026 Mapping ID", "SDGs of the project", "Abstract", "Literature Survey",
            "Research gaps identified", "Problem Statement", "Objectives", "Existing and proposed system",
            "Proposed methodology", "System architecture", "Google sign-in and report verification",
            "Self-service plagiarism check (iThenticate)", "Requirements from the college",
            "Implementation and screenshots", "Results and graphs", "Future enhancements", "Conclusion",
            "References"]
body = body_of(orig[1])
paras = body.text_frame.paragraphs
template = paras[0]
for para in paras[1:]:
    para._p.getparent().remove(para._p)
for r in list(template.runs):
    r._r.getparent().remove(r._r)
add_runs(template, contents[0], 20)
for item in contents[1:]:
    clone_para(template, item, 20)
set_autofit_scale(body)
body.text_frame._txBody.bodyPr.set("numCol", "2")

# Slide 6: abstract
body = body_of(orig[5])
last = body.text_frame.paragraphs[-1]
clone_para(last, "Students **sign in with their college Google account** and check the plagiarism of their reports "
                 "**themselves** through the college's **iThenticate licence** (API), instead of going to faculty "
                 "for every draft.")
clone_para(last, "Every idea check and document check gets a **signed report code** that faculty or NAAC auditors "
                 "can **verify** online.")
set_sizes(body, 22)

# Slide 8: research gaps
body = body_of(orig[7])
clone_para(body.text_frame.paragraphs[-1],
           "Students must **go to faculty for every plagiarism check**; the licensed checker is not available to them.")
set_sizes(body, 22)

# Slide 9: problem statement
body = body_of(orig[8])
clone_para(body.text_frame.paragraphs[-1],
           "Students depend on faculty for every **iThenticate plagiarism check** of their reports, causing "
           "**repeated visits and delays**.")

# Slide 10: objectives
body = body_of(orig[9])
clone_para(body.text_frame.paragraphs[-1],
           "To let students **sign in with Google** and run **self-service iThenticate plagiarism checks** through "
           "the college licence, with **verifiable report codes**.")
set_sizes(body, 22)

# Slide 11: existing and proposed system
body = body_of(orig[10])
last = body.text_frame.paragraphs[-1]
clone_para(last, "Students check plagiarism **themselves** via the college's **iThenticate API**; no faculty visit "
                 "needed for every draft.", 26)
clone_para(last, "**Google sign-in** (@mlrit.ac.in only) and **signed, verifiable** report codes.", 26)
set_autofit_scale(body, 0.85, 0.1)

# Slide 13: expected outcomes -> add measured results
body = body_of(orig[12])
last = body.text_frame.paragraphs[-1]
clone_para(last, "**Fewer Faculty Visits:** Students run iThenticate plagiarism checks on their own drafts.")
clone_para(last, f"**Measured (prototype):** Sentence-BERT found **16/16** reworded projects (TF-IDF "
                 f"{round(T['hit@1'] * 16)}/16); precision **{S55['precision']:.2f}**, recall "
                 f"**{S55['recall']:.2f}** at threshold 0.55; **{LAT['mean']:.0f} ms** per check.")
set_sizes(body, 22)

# Slide 14: graphs -> real results
s14 = orig[13]
title14 = s14.shapes.title
mapping = {
    "Graph 1: Target Performance Metrics": "Graph 1: TF-IDF vs Sentence-BERT (measured)",
    "Illustrative targets — not actual experimental results":
        "Benchmark of 96 projects (8 domains) and 32 test proposals; 16 reworded, 16 new ideas",
    "Graph 2: Expected Reduction in Failures": "Graph 2: Highest similarity per test proposal (measured)",
    "Illustrative comparison per 100 project submissions.":
        "Filled = reworded existing project, hollow = new idea; dashed line = 0.55 threshold.",
}
for para in title14.text_frame.paragraphs:
    for r in para.runs:
        for old, new in mapping.items():
            if r.text.strip() == old.strip():
                r.text = new
            elif r.text == "." and "Illustrative" not in para.text:
                r.text = ""
graph_slots = [sh for sh in s14.placeholders if sh.placeholder_format.idx in (1, 2)]
for sh, fig in zip(sorted(graph_slots, key=lambda x: x.left), ("fig_metrics.png", "fig_scores.png")):
    left, top, w, h = Emu(sh.left).inches, Emu(sh.top).inches, Emu(sh.width).inches, Emu(sh.height).inches
    sh._element.getparent().remove(sh._element)
    picture_fit(s14, FIG / fig, left, top + 0.1, w, h)

# Slide 15: future enhancements
body = body_of(orig[14])
replace15 = {
    "Semantic Models:": "**Live iThenticate Key:** Connect the college's API key and pilot the document check "
                        "with one batch.",
    "Plagiarism Checks:": "**Plagiarism Checks:** Extend the iThenticate self-check to assignments and internship "
                          "reports.",
}
for para in body.text_frame.paragraphs:
    for key, new in replace15.items():
        if para.text.startswith(key):
            for r in list(para.runs):
                r._r.getparent().remove(r._r)
            add_runs(para, new)
clone_para(body.text_frame.paragraphs[-1], "**Real Records:** Load past MLRIT project records and recalibrate the "
                                           "similarity thresholds.")
set_sizes(body, 22)
set_autofit_scale(body)

# Slide 16: conclusion
body = body_of(orig[15])
para = body.text_frame.paragraphs[0]
for r in list(para.runs):
    r._r.getparent().remove(r._r)
add_runs(para, "The AI-Powered Student Project Repository & Similarity Detection Portal lets students do on their "
               "own what they previously had to request from faculty. They sign in with their college Google "
               "account, check whether their idea already exists using Sentence-BERT similarity against all past "
               "projects, and check their report for plagiarism through the college's iThenticate licence. Every "
               "result carries a signed code that faculty and auditors can verify, and the final approval stays "
               "with faculty. On our benchmark, semantic matching found every reworded project that keyword "
               "matching missed, in about 18 ms per check.", 24)

# Slide 17: references
body = body_of(orig[16])
last = body.text_frame.paragraphs[-1]
for ref in ["Wang, W., et al. (2020). *MiniLM: Deep Self-Attention Distillation for Task-Agnostic Compression of "
            "Pre-Trained Transformers*. NeurIPS.",
            "Turnitin. *Turnitin Core API (iThenticate v2 API) documentation*. https://developers.turnitin.com",
            "Sakimura, N., et al. (2014). *OpenID Connect Core 1.0*. OpenID Foundation."]:
    clone_para(last, ref.replace("*", ""), 31)
set_autofit_scale(body, 0.6, 0.2)

# ------------------------------------------------------------- new slides
TOP, LEFT, FULL_W, FULL_H = 0.95, 0.35, 12.6, 5.75
new = []

s = new_slide("System Architecture")
picture_fit(s, FIG / "fig_architecture.png", LEFT, TOP + 0.05, FULL_W, FULL_H)
new.append(s)

s = new_slide("Google Sign-In and Report Verification", [
    "Students and faculty sign in with their **college Google account** (OpenID Connect); no new passwords.",
    "Only **verified @mlrit.ac.in** accounts are accepted; the server checks Google's ID token.",
    "**Student** role by default; **faculty** role from an admin list.",
    "Every result gets a **report code** (OR- idea check, DC- document check) signed with **HMAC-SHA256**.",
    "Guides, placement cell or NAAC auditors can **verify a code** online; edited records show as altered.",
], size=20, body_width=6.7)
picture_fit(s, FIG / "shot_01_login.png", 7.05, TOP + 0.05, 5.9, 2.75)
picture_fit(s, crop("13_verify_doc", (480, 150, 1680, 1020), "verify_doc.png"), 7.05, TOP + 3.0, 5.9, 3.0)
new.append(s)

s = new_slide("Self-Service Plagiarism Check (iThenticate)", [
    "**Today:** students take every draft to faculty, who run it on the college's iThenticate account.",
    "**Proposed:** student uploads the report on the portal; the server calls the **iThenticate v2 API** with "
    "the college's key and shows the **similarity %** to the student.",
    "Searches the **internet, journals (Crossref) and submitted work**; quotes and bibliography excluded.",
    "**API key stays on the server**; no faculty login is shared.",
    "Drafts are **not added to the repository**, so the final report won't match the student's own drafts.",
    "**3 checks per student per week** protect the licence; only the file fingerprint and score are stored.",
], size=19, body_width=7.7)
picture_fit(s, FIG / "fig_doc_sequence.png", 8.2, TOP + 0.05, 4.8, 5.7)
new.append(s)

s = new_slide("Requirements from the College", [
    "**iThenticate administrator:** confirm API access in the licence, create an **API key** (test key first) "
    "and share the **tenant URL**.",
    "**Quota agreement:** how many checks each student may run per week.",
    "**Written approval** from HOD / library to use the licence through the portal.",
    "**Google Workspace admin:** allow the portal's sign-in app for @mlrit.ac.in accounts.",
    "**Past project records** (title, abstract, domain, year) as an Excel sheet for the repository.",
    "**Not needed:** any faculty username or password.",
], size=22)
new.append(s)

shots = [
    ("Implementation: Idea Check Report", crop("04_report_overlap", (0, 0, 2160, 1110), "idea_report.png"),
     "Student report: 78% similar in meaning to an existing project but only 20% word overlap, so it is flagged as "
     "**High overlap** (22% original)."),
    ("Implementation: Faculty Review", crop("06_review", (0, 0, 2160, 1050), "faculty_review.png"),
     "Faculty review: closest projects, the student's iThenticate document checks, and Approve / Revise / Reject."),
    ("Implementation: Document Check Upload", crop("11_doc_check", (0, 0, 2160, 960), "doc_upload.png"),
     "Upload page: the student accepts the iThenticate agreement; the weekly quota is shown."),
    ("Implementation: Document Check Result", crop("12_doc_report", (0, 0, 2160, 810), "doc_result.png"),
     "Result: similarity %, report code, file fingerprint and link to the full iThenticate report. "
     "**Demo mode: score simulated until the college's API key is configured.**"),
]
for title, img, cap in shots:
    s = new_slide(title)
    pic = picture_fit(s, img, LEFT, TOP + 0.1, FULL_W, FULL_H - 0.75)
    caption(s, cap, LEFT, Emu(pic.top + pic.height).inches + 0.08, FULL_W, size=18)
    new.append(s)

for k, sl in enumerate(new):
    move(sl, 12 + k)  # after "Proposed Methodology" (slide 12)

prs.save(OUT)
print("saved", OUT, "slides:", len(prs.slides))
