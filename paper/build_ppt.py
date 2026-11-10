"""Update the review PPT with the portal, iThenticate integration and real results,
keeping the original template, layouts, fonts and colours.

Run from the repository root (after portal/figures.py):
    python paper/build_ppt.py
Input : paper/MP_TG10_Review_PPT_original.pptx (untouched copy of the team's deck)
Output: paper/MP_TG10_Review_PPT_Updated.pptx

Typography rule: every bullet slide uses the same body size (BODY_PT), 100% line
spacing and BODY_AFTER points after each paragraph, with no autofit shrinking, so
original and new slides look the same.
"""
import copy
import json
import re
import sys
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.text.text import _Paragraph
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parent.parent
FIG = ROOT / "portal" / "eval" / "figures"
SHOTS = ROOT / "portal" / "eval" / "screens"
SRC = ROOT / "paper" / "MP_TG10_Review_PPT_original.pptx"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "paper" / "MP_TG10_Review_PPT_Updated.pptx"
CROPS = ROOT / "paper" / "ppt_assets"
CROPS.mkdir(exist_ok=True)

R = json.loads((ROOT / "portal" / "eval" / "results.json").read_text())
T, S55, LAT = R["tfidf"], R["sbert_at_portal_threshold"], R["check_latency_ms"]

BODY_PT = 24       # body text on every bullet slide
BODY_AFTER = 8     # points after each paragraph (as on the original Introduction/Objectives slides)
CAPTION_PT = 18
REF_PT = 16

A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
prs = Presentation(SRC)
LAYOUT = prs.slide_layouts.get_by_name("Title and Content")
orig = list(prs.slides)  # original slides, 0-based
BODY_FRAME = (Emu(129396), Emu(828136), Emu(11766430), Emu(5769752))  # body frame used by the original slides


# ------------------------------------------------------------------ helpers
def body_of(slide):
    for sh in slide.placeholders:
        if sh.placeholder_format.idx == 1:
            return sh
    return [sh for sh in slide.shapes if sh.has_text_frame][1]


def add_runs(paragraph, text):
    """Append text to a paragraph; **bold** spans become bold runs."""
    for part in re.split(r"(\*\*[^*]+\*\*)", text):
        if not part:
            continue
        r = paragraph.add_run()
        bold = part.startswith("**")
        r.text = part[2:-2] if bold else part
        r.font.bold = True if bold else None
    end = paragraph._p.find(A + "endParaRPr")
    if end is not None:  # schema: endParaRPr is the paragraph's last child
        paragraph._p.remove(end)
        paragraph._p.append(end)


def clear_runs(paragraph):
    for child in list(paragraph._p):
        if child.tag in (A + "r", A + "br", A + "fld"):
            paragraph._p.remove(child)


def append_like(template, text):
    """New last paragraph with the template's paragraph properties."""
    p_el = copy.deepcopy(template._p)
    template._p.getparent().append(p_el)
    para = _Paragraph(p_el, template._parent)
    clear_runs(para)
    add_runs(para, text)
    return para


def set_text(paragraph, text):
    clear_runs(paragraph)
    add_runs(paragraph, text)


def normalise(shape, size=BODY_PT, after=BODY_AFTER, line=1.0):
    """One size and one spacing for the whole text box; no autofit shrinking."""
    tf = shape.text_frame
    bp = tf._txBody.bodyPr
    for child in list(bp):
        if child.tag in (A + "normAutofit", A + "spAutoFit", A + "noAutofit"):
            bp.remove(child)
    bp.append(bp.makeelement(A + "normAutofit", {}))
    bp.set("anchor", "t")
    paras = list(tf.paragraphs)
    while len(paras) > 1 and not paras[-1].text.strip():  # trailing empty lines add height
        paras[-1]._p.getparent().remove(paras[-1]._p)
        paras.pop()
    for para in paras:
        para.line_spacing = line
        para.space_before = Pt(0)
        para.space_after = Pt(after)
        for r in para.runs:
            r.font.size = Pt(size)
        end = para._p.find(A + "endParaRPr")
        if end is not None:
            end.set("sz", str(size * 100))


def new_slide(title, bullets=None, body_width=None):
    s = prs.slides.add_slide(LAYOUT)
    s.shapes.title.text = title
    body = body_of(s)
    if bullets is None:
        body._element.getparent().remove(body._element)
        return s
    body.left, body.top, body.width, body.height = BODY_FRAME
    if body_width:
        body.width = Inches(body_width)
    tf = body.text_frame
    tf.clear()
    for i, item in enumerate(bullets):
        add_runs(tf.paragraphs[0] if i == 0 else tf.add_paragraph(), item)
    normalise(body)
    return s


def move(slide, index):
    lst = prs.slides._sldIdLst
    el = [e for e in lst if prs.slides.part.related_part(e.rId) is slide.part][0]
    lst.remove(el)
    lst.insert(index, el)


def picture_fit(slide, path, left, top, max_w, max_h):
    w, h = Image.open(path).size
    scale = min(max_w / w, max_h / h)
    pw, ph = w * scale, h * scale
    pic = slide.shapes.add_picture(str(path), Inches(left + (max_w - pw) / 2), Inches(top), Inches(pw), Inches(ph))
    pic.line.color.rgb = RGBColor(0xBF, 0xBF, 0xBF)
    pic.line.width = Pt(0.75)
    return pic


def caption(slide, text, left, top, width):
    tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(0.6))
    tf = tb.text_frame
    tf.word_wrap = True
    para = tf.paragraphs[0]
    para.alignment = PP_ALIGN.CENTER
    add_runs(para, text)
    for r in para.runs:
        r.font.name = "Times New Roman"
        r.font.size = Pt(CAPTION_PT)
        r.font.italic = True
    return tb


def crop(name, box, out):
    p = CROPS / out
    Image.open(SHOTS / f"{name}.png").crop(box).save(p)
    return p


# ---------------------------------------------------- edits to existing slides
# Slide 2: contents, two columns
contents = ["Introduction", "SIH-2026 Mapping ID", "SDGs of the project", "Abstract", "Literature Survey",
            "Research gaps identified", "Problem Statement", "Objectives", "Existing and proposed system",
            "Proposed methodology", "System architecture", "Google sign-in and verification",
            "Self-service plagiarism check", "Requirements from the college", "Implementation and screenshots",
            "Results and graphs", "Future enhancements", "Conclusion", "References"]
body = body_of(orig[1])
paras = list(body.text_frame.paragraphs)
for para in paras[1:]:
    para._p.getparent().remove(para._p)
set_text(paras[0], contents[0])
for item in contents[1:]:
    append_like(paras[0], item)
normalise(body)
body.text_frame._txBody.bodyPr.set("numCol", "2")

# Slide 6: abstract
body = body_of(orig[5])
append_like(body.text_frame.paragraphs[-1],
            "Students **sign in with Google** and run **iThenticate plagiarism checks themselves**, without going "
            "to faculty for every draft; each result has a **verifiable report code**.")

# Slide 8: research gaps
body = body_of(orig[7])
append_like(body.text_frame.paragraphs[-1], "Students must **go to faculty for every plagiarism check**.")

# Slide 9: problem statement
body = body_of(orig[8])
append_like(body.text_frame.paragraphs[-1],
            "Students depend on faculty for every **iThenticate plagiarism check**, causing **repeated visits**.")

# Slide 10: objectives
body = body_of(orig[9])
append_like(body.text_frame.paragraphs[-1],
            "To let students **sign in with Google** and run **self-service iThenticate checks** with "
            "**verifiable report codes**.")

# Slide 11: existing and proposed system
body = body_of(orig[10])
append_like(body.text_frame.paragraphs[-1],
            "**Google sign-in** and **self-service iThenticate checks** with verifiable report codes.")

# Slide 13: expected outcomes (original bullets on this slide are not bold)
body = body_of(orig[12])
append_like(body.text_frame.paragraphs[-1],
            "Fewer Faculty Visits: Students run iThenticate checks on their own drafts.")
append_like(body.text_frame.paragraphs[-1],
            f"Measured Results: Sentence-BERT found 16/16 reworded projects (TF-IDF {round(T['hit@1'] * 16)}/16); "
            f"precision {S55['precision']:.2f}, recall {S55['recall']:.2f}; {LAT['mean']:.0f} ms per check.")

# Slide 14: graphs -> measured results
s14 = orig[13]
mapping = {
    "Graph 1: Target Performance Metrics": "Graph 1: TF-IDF vs Sentence-BERT (measured)",
    "Illustrative targets — not actual experimental results":
        "Benchmark of 96 projects (8 domains) and 32 test proposals; 16 reworded, 16 new ideas",
    "Graph 2: Expected Reduction in Failures": "Graph 2: Highest similarity per test proposal (measured)",
    "Illustrative comparison per 100 project submissions.":
        "Filled = reworded existing project, hollow = new idea; dashed line = 0.55 threshold.",
}
for para in s14.shapes.title.text_frame.paragraphs:
    for r in para.runs:
        for old, new in mapping.items():
            if r.text.strip() == old.strip():
                r.text = new
graph_slots = [sh for sh in s14.placeholders if sh.placeholder_format.idx in (1, 2)]
for sh, fig in zip(sorted(graph_slots, key=lambda x: x.left), ("fig_metrics.png", "fig_scores.png")):
    left, top, w, h = Emu(sh.left).inches, Emu(sh.top).inches, Emu(sh.width).inches, Emu(sh.height).inches
    sh._element.getparent().remove(sh._element)
    picture_fit(s14, FIG / fig, left, top + 0.1, w, h)

# Slide 15: future enhancements (original bullets on this slide are not bold)
body = body_of(orig[14])
for para in body.text_frame.paragraphs:
    if para.text.startswith("Semantic Models:"):
        set_text(para, "Live iThenticate Key: Connect the college's API key and pilot with one batch.")
    elif para.text.startswith("Plagiarism Checks:"):
        set_text(para, "Plagiarism Checks: Extend the self-check to assignments and internship reports.")
append_like(body.text_frame.paragraphs[-1], "Real Records: Load past MLRIT projects and recalibrate thresholds.")

# Slide 16: conclusion
body = body_of(orig[15])
set_text(body.text_frame.paragraphs[0],
         "The AI-Powered Student Project Repository & Similarity Detection Portal lets students do on their own "
         "what they previously had to request from faculty. They sign in with their college Google account, check "
         "whether their idea already exists using Sentence-BERT similarity against all past projects, and check "
         "their report for plagiarism through the college's iThenticate licence. Every result carries a signed code "
         "that faculty and auditors can verify, and the final approval stays with faculty. On our benchmark, "
         "semantic matching found every reworded project that keyword matching missed, in about 18 ms per check.")

# Slide 17: references
body = body_of(orig[16])
for ref in ["Wang, W., et al. (2020). MiniLM: Deep Self-Attention Distillation for Task-Agnostic Compression of "
            "Pre-Trained Transformers. NeurIPS.",
            "Turnitin. Turnitin Core API (iThenticate v2 API) documentation. https://developers.turnitin.com",
            "Sakimura, N., et al. (2014). OpenID Connect Core 1.0. OpenID Foundation."]:
    append_like(body.text_frame.paragraphs[-1], ref)
normalise(body, size=REF_PT, after=4)

# Same body size and spacing on every original bullet slide
for idx in (2, 3, 4, 5, 7, 8, 9, 10, 12, 14, 15):
    normalise(body_of(orig[idx]))

# ------------------------------------------------------------- new slides
TOP, LEFT, FULL_W, FULL_H = 0.95, 0.35, 12.6, 5.75
new = []

s = new_slide("System Architecture")
picture_fit(s, FIG / "fig_architecture.png", LEFT, TOP + 0.05, FULL_W, FULL_H)
new.append(s)

s = new_slide("Google Sign-In and Report Verification", [
    "Sign in with the **college Google account**; no new passwords.",
    "Only **verified @mlrit.ac.in** accounts are allowed.",
    "**Student** role by default; **faculty** role from an admin list.",
    "Every result gets a **signed report code** (OR- idea, DC- document).",
    "Anyone can **verify a code** online; edited records show as altered.",
], body_width=6.7)
picture_fit(s, FIG / "shot_01_login.png", 7.05, TOP + 0.05, 5.9, 2.75)
picture_fit(s, crop("13_verify_doc", (480, 150, 1680, 1020), "verify_doc.png"), 7.05, TOP + 3.0, 5.9, 3.0)
new.append(s)

s = new_slide("Self-Service Plagiarism Check (iThenticate)", [
    "**Today:** every draft goes to faculty for an iThenticate check.",
    "**Portal:** the student uploads; the server calls the **iThenticate v2 API** and shows the "
    "**similarity %**.",
    "Checks the **internet, journals and submitted work**.",
    "**API key stays on the server**; no faculty login is shared.",
    "Drafts are **not stored** in iThenticate's repository.",
    "**3 checks per student per week** protect the licence.",
], body_width=7.7)
picture_fit(s, FIG / "fig_doc_sequence.png", 8.2, TOP + 0.05, 4.8, 5.7)
new.append(s)

s = new_slide("Requirements from the College", [
    "**iThenticate administrator:** enable API access, create an **API key** (test key first) and share the "
    "**tenant URL**.",
    "**Quota:** number of checks each student may run per week.",
    "**Written approval** from HOD / library to use the licence through the portal.",
    "**Google Workspace admin:** allow the portal's sign-in for @mlrit.ac.in accounts.",
    "**Past project records** (title, abstract, domain, year) as an Excel sheet.",
    "**Not needed:** any faculty username or password.",
])
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
    caption(s, cap, LEFT, Emu(pic.top + pic.height).inches + 0.08, FULL_W)
    new.append(s)

for k, sl in enumerate(new):
    move(sl, 12 + k)  # after "Proposed Methodology" (slide 12)

prs.save(OUT)
print("saved", OUT, "slides:", len(prs.slides))
