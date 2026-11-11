"""Build the AWG talk deck on the Uni Basel template.

Usage: python build/build_deck.py [template.pptx] [out.pptx]

Defaults: build/Vorlage_Slides_Uni-CI.pptx and AWG-Graph-Talk.pptx in the
folder above build/. Writes out.pptx and, via LibreOffice, a PDF of the same
name next to it.
Template source: https://tales.nmc.unibas.ch/media/poster-slides-und-handouts/Vorlage_Slides_Blindtext_Uni-CI_kQGJoRy.pptx
The build copy is reduced to its master, theme and all layouts plus two sample
slides (1 = title, 2 = content, originally slides 1 and 4); the other sample
slides and their media were removed.
"""

import copy
import os
import shutil
import subprocess
import sys
import tempfile
import uuid

from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_LINE, MSO_THEME_COLOR
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Cm, Pt

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = (
    sys.argv[1]
    if len(sys.argv) > 1
    else os.path.join(HERE, "Vorlage_Slides_Uni-CI.pptx")
)
OUT = (
    sys.argv[2]
    if len(sys.argv) > 2
    else os.path.join(os.path.dirname(HERE), "AWG-Graph-Talk.pptx")
)

DECK_FOOTER = "Compositional Processes as Graph · AWG"
SPEAKER = "Stefan Münnich"
EDITION_URL = "https://edition.anton-webern.ch"
EMAIL = "stefan.muennich@unibas.ch"

# Theme colours of the template (ppt/theme/theme1.xml)
T_BLACK = MSO_THEME_COLOR.TEXT_1  # 000000
T_DARKGREEN = MSO_THEME_COLOR.TEXT_2  # 006E6E (subheadings)
T_MINT = MSO_THEME_COLOR.ACCENT_1  # A5D7D2 (main colour)
T_GREEN = MSO_THEME_COLOR.ACCENT_2  # 1EA5A5 (highlighted terms)
T_GREY = MSO_THEME_COLOR.ACCENT_3  # 2D373C (body text)
T_RED = MSO_THEME_COLOR.ACCENT_5  # D20537 (the only accent)
T_WHITE = MSO_THEME_COLOR.BACKGROUND_1  # FFFFFF (text on dark bands)

MINT = RGBColor(0xA5, 0xD7, 0xD2)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
MONO = "Consolas"

prs = Presentation(TEMPLATE)
src_title_slide = prs.slides[0]
src_content_slide = prs.slides[1]
LAYOUT_TITLE = prs.slide_layouts[0]  # Titelfolie
LAYOUT_TITLE_ONLY = prs.slide_layouts[10]  # Nur Titel
LAYOUT_PICTURE_CAPTION = prs.slide_layouts[5]  # Bild mit Legende


# ================================================================ XML helpers
def ph_by_type(slide, ph_type):
    for sp in slide.shapes._spTree.iter(qn("p:sp")):
        ph = sp.find(".//" + qn("p:ph"))
        if ph is not None and ph.get("type") == ph_type:
            return sp
    return None


def remove_ph(slide, ph_type):
    sp = ph_by_type(slide, ph_type)
    if sp is not None:
        sp.getparent().remove(sp)


# Deep copies of template elements, taken before the template slides go.
TPL_CTR_TITLE = copy.deepcopy(ph_by_type(src_title_slide, "ctrTitle"))
TPL_SUBTITLE = copy.deepcopy(ph_by_type(src_title_slide, "subTitle"))
TPL_TITLE = copy.deepcopy(ph_by_type(src_content_slide, "title"))
TPL_FOOTERS = [
    copy.deepcopy(ph_by_type(src_content_slide, t)) for t in ("dt", "ftr", "sldNum")
]


def next_id(slide):
    ids = [int(e.get("id")) for e in slide.shapes._spTree.iter(qn("p:cNvPr"))]
    return max(ids + [1]) + 1


def put(slide, element):
    """Replace the slide's placeholder of the same type by element, or append it."""
    element = copy.deepcopy(element)
    for ext in element.iter(qn("a:extLst")):
        ext.getparent().remove(ext)  # drop creationIds copied from the template
    ph_type = element.find(".//" + qn("p:ph")).get("type")
    old = ph_by_type(slide, ph_type)
    tree = slide.shapes._spTree
    if old is not None:
        tree.replace(old, element)
    else:
        tree.append(element)
    element.find(".//" + qn("p:cNvPr")).set("id", str(next_id(slide)))
    return element


def set_runs(sp, texts):
    """Write texts into the existing runs of sp, in order.

    Surplus runs are dropped with their breaks; missing ones are cloned from the
    last run, each after a line break.
    """
    runs = list(sp.iter(qn("a:r")))
    while len(runs) < len(texts):
        last = runs[-1]
        br = etree.Element(qn("a:br"))
        new = copy.deepcopy(last)
        last.addnext(br)
        br.addnext(new)
        runs.append(new)
    for run, text in zip(runs, texts):
        run.find(qn("a:t")).text = text
    for run in runs[len(texts) :]:
        prev = run.getprevious()
        if prev is not None and prev.tag == qn("a:br"):
            prev.getparent().remove(prev)
        run.getparent().remove(run)
    return runs[: len(texts)]


def link_run(slide, run_el, url):
    r_id = slide.part.relate_to(
        url,
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
        is_external=True,
    )
    rpr = run_el.find(qn("a:rPr"))
    link = etree.SubElement(rpr, qn("a:hlinkClick"))
    link.set(qn("r:id"), r_id)


def set_alpha(fill_parent, alpha):
    clr = fill_parent.find(".//" + qn("a:srgbClr"))
    if clr is None:
        clr = fill_parent.find(".//" + qn("a:schemeClr"))
    a = etree.SubElement(clr, qn("a:alpha"))
    a.set("val", str(int(alpha * 1000)))


def drop_styles(element):
    """Drop the theme style references python-pptx adds (grey effects, theme fonts)."""
    for style in list(element.iter(qn("p:style"))):
        style.getparent().remove(style)


# ================================================================ typography
# Uni Basel CI: body Arial 17/22 dark grey; subheading Arial 17 bold dark green;
# term Arial 17 green; caption Arial 14; code monospace 17.
STYLES = {
    "body": dict(font="Arial", size=17, color=T_GREY),
    "bold": dict(font="Arial", size=17, color=T_GREY, bold=True),
    "sub": dict(font="Arial", size=17, color=T_DARKGREEN, bold=True),
    "sub_code": dict(font=MONO, size=17, color=T_DARKGREEN, bold=True),
    "term": dict(font="Arial", size=17, color=T_GREEN),
    "code": dict(font=MONO, size=17, color=T_GREY),
    "caption": dict(font="Arial", size=14, color=T_GREY),
    "question": dict(font="Georgia", size=30, color=T_BLACK),
    "code_caption": dict(font=MONO, size=14, color=T_GREY),
    "red_caption": dict(font="Arial", size=14, color=T_RED, bold=True),
    "statement": dict(font="Georgia", size=23, color=T_BLACK),
    "statement_term": dict(font="Georgia", size=23, color=T_GREEN),
    "closing": dict(font="Georgia", size=34, color=T_BLACK, bold=True),
    "closing_sub": dict(font="Georgia", size=20, color=T_BLACK),
    "question_light": dict(font="Georgia", size=30, color=T_WHITE),
    "band_bold": dict(font="Arial", size=17, color=T_WHITE, bold=True),
    "band_body": dict(font="Arial", size=17, color=T_WHITE),
    "source": dict(font="Arial", size=10, color=T_GREY),
    "source_light": dict(font="Arial", size=10, color=T_WHITE),
    "closing_light": dict(font="Georgia", size=30, color=T_WHITE, bold=True),
    "closing_sub_light": dict(font="Georgia", size=20, color=T_WHITE),
}
LINE = {
    "body": 22,
    "bold": 22,
    "sub": 22,
    "sub_code": 22,
    "term": 22,
    "code": 22,
    "caption": 18,
    "question": 40,
    "code_caption": 18,
    "red_caption": 18,
    "statement": 30,
    "statement_term": 30,
    "closing": 42,
    "closing_sub": 27,
    "question_light": 40,
    "band_bold": 22,
    "band_body": 22,
    "source": 12,
    "source_light": 12,
    "closing_light": 38,
    "closing_sub_light": 27,
}


def add_text(
    slide,
    x,
    y,
    w,
    h,
    paragraphs,
    name,
    align=PP_ALIGN.LEFT,
    anchor=MSO_ANCHOR.TOP,
    space_after=0,
):
    """paragraphs: list of paragraphs, each a list of (style, text) runs (or one (style, text))."""
    box = slide.shapes.add_textbox(Cm(x), Cm(y), Cm(w), Cm(h))
    box.name = name
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    for i, para in enumerate(paragraphs):
        if isinstance(para, tuple):
            para = [para]
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = Pt(LINE[para[0][0]])
        p.space_after = Pt(space_after)
        for style, text in para:
            st = STYLES[style]
            r = p.add_run()
            r.text = text
            f = r.font
            f.name = st["font"]
            f.size = Pt(st["size"])
            f.bold = st.get("bold", False)
            f.color.theme_color = st["color"]
    return box


# ================================================================ diagram helpers
def rect(
    slide,
    x,
    y,
    w,
    h,
    name,
    fill=None,
    brightness=0.0,
    line=None,
    line_pt=1.0,
    dash=False,
    shape=MSO_SHAPE.RECTANGLE,
):
    """Rectangle in cm; fill and line are theme colours (None = none)."""
    r = slide.shapes.add_shape(shape, Cm(x), Cm(y), Cm(w), Cm(h))
    r.name = name
    if fill is None:
        r.fill.background()
    else:
        r.fill.solid()
        r.fill.fore_color.theme_color = fill
        r.fill.fore_color.brightness = brightness
    if line is None:
        r.line.fill.background()
    else:
        r.line.color.theme_color = line
        r.line.width = Pt(line_pt)
        if dash:
            r.line.dash_style = MSO_LINE.DASH
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        r.adjustments[0] = min(0.5, 0.25 / min(w, h))  # corner radius about 0.25 cm
    drop_styles(r._element)
    return r


def labelled_box(slide, x, y, w, h, text, name, style="code", **kw):
    """Box with one centred line of text (class names, tags)."""
    rect(slide, x, y, w, h, f"Box: {name}", **kw)
    return add_text(
        slide,
        x,
        y,
        w,
        h,
        [(style, text)],
        f"Text: {name}",
        align=PP_ALIGN.CENTER,
        anchor=MSO_ANCHOR.MIDDLE,
    )


def line(
    slide,
    x1,
    y1,
    x2,
    y2,
    name,
    color=T_DARKGREEN,
    pt=1.5,
    head=False,
    both=False,
    dash=False,
):
    """Straight line in cm; head puts a filled triangle at (x2, y2), both also at (x1, y1)."""
    c = slide.shapes.add_connector(
        MSO_CONNECTOR.STRAIGHT, Cm(x1), Cm(y1), Cm(x2), Cm(y2)
    )
    c.name = name
    c.line.color.theme_color = color
    c.line.width = Pt(pt)
    if dash:
        c.line.dash_style = MSO_LINE.DASH
    ln = c.line._get_or_add_ln()
    for end, on in (("a:headEnd", both), ("a:tailEnd", head or both)):
        if on:
            e = etree.SubElement(ln, qn(end))
            e.set("type", "triangle")
            e.set("w", "med")
            e.set("len", "med")
    drop_styles(c._element)
    return c


def tree(slide, parent_cx, parent_bottom, child_cxs, child_top, name):
    """Subclass tree: one trunk with a triangle at the parent, a bar, a stem to each child."""
    bar_y = (parent_bottom + child_top) / 2
    line(slide, parent_cx, bar_y, parent_cx, parent_bottom, f"{name}: trunk", head=True)
    xs = child_cxs + [parent_cx]
    if min(xs) < max(xs):
        line(slide, min(xs), bar_y, max(xs), bar_y, f"{name}: bar")
    for cx in child_cxs:
        line(slide, cx, bar_y, cx, child_top, f"{name}: stem")


# Template bands (Vorlage p. 2, 8, 11): from the left slide edge to the right
# margin; dark = tx2 at 82 % with white text, light = accent1 at 50 %.
BAND_X, BAND_W = 0.0, 32.94
BAND_TOP, BAND_BOTTOM = 14.9, 2.0  # bottom band on slides 9 and 10 (y, h)


def band(slide, y, h, name, dark=False):
    r = rect(slide, BAND_X, y, BAND_W, h, name, fill=T_DARKGREEN if dark else T_MINT)
    set_alpha(r._element.spPr, 82 if dark else 50)
    return r


def to_back(slide, shape):
    tree = slide.shapes._spTree  # right after nvGrpSpPr and grpSpPr
    tree.remove(shape._element)
    tree.insert(2, shape._element)


def washed_picture(slide, file, crop, x, y, w, h, keep, name, descr):
    """Graph capture in the app's own colours (teal, dark red), blended towards white.

    crop is in pixels of the original capture and is cut further, centred, to
    the aspect ratio of the w x h box (cm).
    """
    from PIL import Image

    with Image.open(os.path.join(HERE, "img", file)) as im:
        im = im.convert("RGB").crop(crop)
    cw, ch = im.size
    if cw / ch > w / h:
        nw = round(ch * w / h)
        im = im.crop(((cw - nw) // 2, 0, (cw - nw) // 2 + nw, ch))
    else:
        nh = round(cw * h / w)
        im = im.crop((0, (ch - nh) // 2, cw, (ch - nh) // 2 + nh))
    f = min(1.0, 2400 / max(im.size))
    im = im.resize((round(im.width * f), round(im.height * f)), Image.LANCZOS)
    im = Image.blend(Image.new("RGB", im.size, "white"), im, keep)
    img_dir = tempfile.mkdtemp(prefix="awg_img_")
    path = os.path.join(img_dir, os.path.splitext(file)[0] + ".jpg")
    im.save(path, quality=88)
    pic = slide.shapes.add_picture(path, Cm(x), Cm(y), Cm(w), Cm(h))
    shutil.rmtree(img_dir, ignore_errors=True)
    pic.name = name
    pic._element.nvPicPr.cNvPr.set("descr", descr)
    return pic


GRAPH_SOURCE = (
    "Source: AWG online edition, op. 25, graph view of all triples "
    "(development version, screenshot 11 Nov 2026)"
)


# ================================================================ watermark
# A stylised genesis graph: edition complex -> versions, sketches in a
# precedes chain (solid arrows), sub-sketches concomitating (dashed).
NODES = {
    "C": (8.0, 0.6, 0.55),
    "V1": (2.6, 2.4, 0.42),
    "V2": (9.6, 4.4, 0.42),
    "P": (5.6, 4.0, 0.26),
    "S1": (0.6, 6.0, 0.32),
    "S2": (3.6, 7.0, 0.32),
    "S21": (2.6, 9.6, 0.24),
    "S3": (6.8, 7.8, 0.32),
    "S31": (7.6, 10.4, 0.24),
    "S4": (10.4, 8.6, 0.32),
}
EDGES = [  # (from, to, kind)
    ("C", "V1", "plain"),
    ("C", "V2", "plain"),
    ("C", "P", "plain"),
    ("V1", "V2", "arrow"),
    ("V1", "S1", "plain"),
    ("S1", "S2", "arrow"),
    ("S2", "S3", "arrow"),
    ("S3", "S4", "arrow"),
    ("S4", "V2", "arrow"),
    ("P", "S2", "plain"),
    ("S2", "S21", "dash"),
    ("S3", "S31", "dash"),
]


def draw_graph(
    shapes,
    nodes,
    edges,
    x0,
    y0,
    scale,
    color,
    node_alpha=None,
    edge_alpha=None,
    line_pt=1.5,
    theme_color=None,
):
    """Draw nodes and edges into shapes (a slide's or a group's). Colour: rgb with alpha, or theme colour."""
    pos = {
        k: (x0 + x * scale, y0 + y * scale, r * scale) for k, (x, y, r) in nodes.items()
    }

    def paint(color_format):
        if theme_color is not None:
            color_format.theme_color = theme_color
        else:
            color_format.rgb = color

    for a, b, kind in edges:
        (xa, ya, ra), (xb, yb, rb) = pos[a], pos[b]
        dx, dy = xb - xa, yb - ya
        d = (dx * dx + dy * dy) ** 0.5
        ux, uy = dx / d, dy / d
        gap = 0.12
        c = shapes.add_connector(
            MSO_CONNECTOR.STRAIGHT,
            Cm(xa + ux * (ra + gap)),
            Cm(ya + uy * (ra + gap)),
            Cm(xb - ux * (rb + gap)),
            Cm(yb - uy * (rb + gap)),
        )
        paint(c.line.color)
        c.line.width = Pt(line_pt)
        ln = c.line._get_or_add_ln()
        if edge_alpha is not None:
            set_alpha(ln, edge_alpha)
        if kind == "dash":
            c.line.dash_style = MSO_LINE.DASH
        if kind == "arrow":
            tail = etree.SubElement(ln, qn("a:tailEnd"))
            tail.set("type", "triangle")
            tail.set("w", "med")
            tail.set("len", "med")
        drop_styles(c._element)
    for x, y, r in pos.values():
        n = shapes.add_shape(MSO_SHAPE.OVAL, Cm(x - r), Cm(y - r), Cm(2 * r), Cm(2 * r))
        n.fill.solid()
        paint(n.fill.fore_color)
        if node_alpha is not None:
            set_alpha(n._element.spPr, node_alpha)
        n.line.fill.background()
        drop_styles(n._element)


def add_watermark(slide, x0, y0, scale, color, node_alpha, edge_alpha):
    group = slide.shapes.add_group_shape()
    group.name = "Watermark (graph)"
    draw_graph(group.shapes, NODES, EDGES, x0, y0, scale, color, node_alpha, edge_alpha)
    tree = slide.shapes._spTree  # send to back: right after nvGrpSpPr and grpSpPr
    tree.remove(group._element)
    tree.insert(2, group._element)
    for e in group._element.iter(qn("p:cNvPr")):
        e.set("id", str(next_id(slide)))
    return group


# ================================================================ slide frames
def fmt_time(sec):
    return f"{sec // 60}:{sec % 60:02d}"


ELAPSED = [0]


def notes(slide, label, seconds, text):
    ELAPSED[0] += seconds
    slide.notes_slide.notes_text_frame.text = (
        f"[{label}] Target time: {fmt_time(seconds)} (cumulative {fmt_time(ELAPSED[0])} of 20:00)\n\n"
        + text.strip()
    )


def title_slide(title, subtitle_lines):
    s = prs.slides.add_slide(LAYOUT_TITLE)
    t = put(s, TPL_CTR_TITLE)
    set_runs(t, title)
    sub = put(s, TPL_SUBTITLE)
    set_runs(sub, subtitle_lines)
    t.find(".//" + qn("a:off")).set("y", str(Cm(3.2)))
    t.find(".//" + qn("a:ext")).set("cx", str(Cm(23.0)))
    t.find(".//" + qn("a:ext")).set("cy", str(Cm(4.0)))
    sub_xfrm = etree.SubElement(sub.find(qn("p:spPr")), qn("a:xfrm"))
    etree.SubElement(sub_xfrm, qn("a:off"), x=str(Cm(2.33)), y=str(Cm(9.0)))
    etree.SubElement(sub_xfrm, qn("a:ext"), cx=str(Cm(22.0)), cy=str(Cm(4.6)))
    add_watermark(s, 25.0, 3.0, 0.7, WHITE, 55, 65)
    return s


def content_slide(title, label, layout=None, watermark=True):
    s = prs.slides.add_slide(layout or LAYOUT_TITLE_ONLY)
    t = put(s, TPL_TITLE)
    set_runs(t, [title, label])
    p = t.find(".//" + qn("a:p"))  # master: exact 25 pt, too tight for title + label
    ppr = p.find(qn("a:pPr"))
    if ppr is None:
        ppr = etree.Element(qn("a:pPr"))
        p.insert(0, ppr)
    ln = etree.SubElement(ppr, qn("a:lnSpc"))
    etree.SubElement(ln, qn("a:spcPts"), val="2800")
    for f in TPL_FOOTERS:
        put(s, f)
    set_runs(ph_by_type(s, "dt"), [DECK_FOOTER])
    set_runs(ph_by_type(s, "ftr"), [SPEAKER])
    for t in ("dt", "ftr", "sldNum"):  # master: 6 pt, name bold -> 8 pt regular
        sp = ph_by_type(s, t)
        for rpr in list(sp.iter(qn("a:rPr"))) + list(sp.iter(qn("a:endParaRPr"))):
            rpr.set("sz", "800")
            rpr.set("b", "0")
    if watermark:
        add_watermark(s, 21.2, 5.0, 1.0, MINT, 35, 45)
    return s


# ================================================================ slides
def slide_01():
    s = title_slide(
        [
            "Compositional Processes as Graph",
            "Semantic Modelling and Terminology in the Anton Webern Gesamtausgabe (AWG)",
        ],
        [
            f"{SPEAKER} · Anton Webern Gesamtausgabe, University of Basel",
            "Comparative Perspectives on Genetic Criticism in Music",
            "International Conference of the IMS Study Group",
            "Rome, German Historical Institute, 16–18 November 2026",
        ],
    )
    notes(
        s,
        "Title",
        15,
        """
Thank you for having me. My talk is about the graph of the Anton Webern Gesamtausgabe: where its terms come from, and what happens to them when we encode them as classes and relations.
""",
    )


def slide_02():
    s = content_slide(
        "The sources show a network; a printed edition needs an explicit order",
        "Research problem",
        watermark=False,
    )
    # Vorlage p. 2: full-bleed image, dark band with the key text.
    pic = washed_picture(
        s,
        "op25-graph-full.png",
        (0, 200, 2808, 2740),  # bottom edge cuts off the app toolbar
        0.0,
        0.0,
        33.87,
        19.05,
        0.6,
        "Background: op. 25 graph",
        "Graph view of op. 25 with all triples, without labels: a dense network of nodes and edges",
    )
    to_back(s, pic)
    band(s, 11.6, 5.0, "Band: research question", dark=True)
    add_text(
        s,
        0.93,
        11.6,
        28.5,
        4.2,
        [
            (
                "question_light",
                "How can a digital edition represent non-linear compositional processes "
                "– and keep philological claims as open as the evidence demands?",
            )
        ],
        "Research question",
        anchor=MSO_ANCHOR.MIDDLE,
    )
    add_text(
        s,
        0.93,
        15.85,
        31.5,
        0.5,
        [("source_light", GRAPH_SOURCE)],
        "Source line",
        align=PP_ALIGN.RIGHT,
    )
    notes(
        s,
        "Research problem",
        45,
        """
Let me start with the question behind this talk.

[Pause, let the slide speak.]

Webern's sketches do not form a simple sequence. They overlap and are spread over sketchbooks and loose sheets. A printed edition has to choose one order. That digital editions overcome the linearity of the book is common sense in our community. How to get there is not – and a network model of the process is still rare.

The harder part is the second half. A graph forces every relation to be explicit: an edge is there, or it is not. Philological claims are often more open than that – "presumably", "alongside", "not decidable". How can the graph keep them that open? That is this talk's question.

ALT TEXT: Behind the slide, a pale teal image of the full op. 25 graph: hundreds of nodes and edges without labels. In a dark teal band, the research question in white.
""",
    )


# Mini-graphs for the layer diagram (local cm coordinates, radius)
GEN_NODES = {
    "a": (1.2, 0.2, 0.22),
    "b": (0.0, 1.8, 0.18),
    "c": (1.2, 1.8, 0.18),
    "d": (2.4, 1.8, 0.18),
}
GEN_EDGES = [("a", "b", "plain"), ("a", "c", "plain"), ("a", "d", "plain")]
CUR_NODES = {
    "a": (0.0, 0.4, 0.18),
    "b": (1.2, 1.4, 0.18),
    "c": (2.4, 0.4, 0.18),
    "d": (1.2, -0.4, 0.14),
}
CUR_EDGES = [("a", "b", "arrow"), ("b", "c", "arrow"), ("b", "d", "dash")]


def slide_03():
    s = content_slide(
        "The AWG graph separates what the data imply from what editors assert",
        "The AWG and its graph",
        watermark=False,
    )
    fx, fy, fw, fh = 4.4, 4.5, 25.1, 10.9  # outer frame: draft ontology
    frame = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Cm(fx), Cm(fy), Cm(fw), Cm(fh))
    frame.name = "Frame: draft ontology"
    frame.fill.background()
    frame.line.color.theme_color = T_DARKGREEN
    frame.line.width = Pt(1.25)
    drop_styles(frame._element)
    add_text(
        s,
        fx + 0.8,
        fy + 0.6,
        12,
        0.8,
        [("sub", "draft ontology v0.1")],
        "Label: draft ontology",
    )
    link = add_text(
        s,
        fx + fw - 0.8 - 10,
        fy + 0.7,
        10,
        0.6,
        [("caption", EDITION_URL.removeprefix("https://"))],
        "Link: edition",
        align=PP_ALIGN.RIGHT,
    )
    link_run(s, link.text_frame.paragraphs[0].runs[0]._r, EDITION_URL)

    layers = [  # (name, description, brightness, mini graph)
        (
            "generated layer",
            "derived from the edition's structured data",
            0.6,
            (GEN_NODES, GEN_EDGES),
        ),
        (
            "curated layer",
            "hand-modelled editorial assertions",
            0.0,
            (CUR_NODES, CUR_EDGES),
        ),
    ]
    lx, lw, lh, gap = fx + 0.8, fw - 1.6, 3.6, 0.5
    ly = fy + 1.9
    for name, desc, brightness, (gn, ge) in layers:
        box = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Cm(lx), Cm(ly), Cm(lw), Cm(lh))
        box.name = f"Layer: {name}"
        box.fill.solid()
        box.fill.fore_color.theme_color = T_MINT
        box.fill.fore_color.brightness = brightness
        box.line.fill.background()
        drop_styles(box._element)
        add_text(
            s,
            lx + 0.8,
            ly,
            15.5,
            lh,
            [("bold", name), ("body", desc)],
            f"Text: {name}",
            anchor=MSO_ANCHOR.MIDDLE,
        )
        draw_graph(
            s.shapes,
            gn,
            ge,
            lx + lw - 4.4,
            ly + 0.9,
            1.0,
            None,
            line_pt=1.25,
            theme_color=T_DARKGREEN,
        )
        ly += lh + gap
    add_text(
        s,
        fx,
        fy + fh + 0.4,
        fw,
        0.6,
        [
            (
                "caption",
                "Queried with SPARQL in the app, exported as Turtle. No reasoning.",
            )
        ],
        "Caption: access",
    )
    notes(
        s,
        "The AWG and its graph",
        45,
        """
The AWG is a hybrid edition, in print and online. Online, it provides an RDF graph as a semantic view of its materials.

The graph has two layers. The generated layer is derived from the edition's structured data: hierarchy, sources, folios, placements, and relations that follow from the numbering. The curated layer holds what only editors can assert: continuity drafts, evidence-based order, and uncertainty.

Both are described by one draft ontology, version 0.1. You can query it with SPARQL and export it as Turtle. There is no reasoning: everything was either generated or asserted.
""",
    )


def slide_04():
    s = content_slide(
        "In op. 25, the layers show where editorial judgment begins",
        "Live demo: op. 25",
        watermark=False,
    )
    # Canvas captures at DPR 3 (Chrome "Capture node screenshot").
    # (file, step, caption, crop box, red marks as (cx, cy, rx, ry)),
    # crop box and marks in pixels of the original capture.
    panels = [
        (
            "op25-graph-generated-canvas.png",
            "generated",
            "three islands, one per song",
            (66, 249, 3426, 2251),
            [(2224, 1175, 287, 81)],
        ),  # Op25_SkRT without genetic relations
        (
            "op25-graph-curated-canvas.png",
            "curated",
            "one chain across the songs",
            (128, 115, 3327, 2478),
            [(803, 1358, 143, 126), (1813, 848, 161, 99)],
        ),  # M317 Sk4 → M321 Sk1, M321 Sk9 → M322 Sk1
        (
            "op25-graph-both-canvas.png",
            "both",
            "the chain crosses the opus order",
            (261, 161, 2845, 2567),  # bottom edge cuts off the app toolbar
            [(1264, 1309, 165, 90)],
        ),  # M321 Sk9 → M322 Sk1
    ]
    from PIL import Image

    img_dir = tempfile.mkdtemp(prefix="awg_img_")
    x0, y0, gap, pw, ph = 0.93, 4.3, 0.5, (32.0 - 2 * 0.5) / 3, 8.9
    for i, (file, step, caption, crop, marks) in enumerate(panels):
        x = x0 + i * (pw + gap)
        with Image.open(os.path.join(HERE, "img", file)) as im:
            im = im.convert("RGB").crop(crop)
            f = min(1.0, 2400 / max(im.size))  # at most 2400 px, about 590 dpi
            im = im.resize((round(im.width * f), round(im.height * f)), Image.LANCZOS)
            path = os.path.join(img_dir, file)
            im.save(path, optimize=True)
            iw, ih = im.size
        marks = [
            ((cx - crop[0]) * f, (cy - crop[1]) * f, rx * f, ry * f)
            for cx, cy, rx, ry in marks
        ]
        k = min(pw / iw, ph / ih)  # cm per pixel
        w, h = iw * k, ih * k
        ix, iy = x + (pw - w) / 2, y0 + (ph - h) / 2
        pic = s.shapes.add_picture(path, Cm(ix), Cm(iy), Cm(w), Cm(h))
        pic.name = f"Screenshot: {step}"
        pic._element.nvPicPr.cNvPr.set(
            "descr", f"Graph view of op. 25, {step} layer, filtered by SPARQL"
        )
        frame = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Cm(x), Cm(y0), Cm(pw), Cm(ph))
        frame.name = f"Panel frame: {step}"
        frame.fill.background()
        frame.line.color.theme_color = T_MINT
        frame.line.width = Pt(1)
        drop_styles(frame._element)
        for cx, cy, rx, ry in marks:
            m = s.shapes.add_shape(
                MSO_SHAPE.OVAL,
                Cm(ix + (cx - rx) * k),
                Cm(iy + (cy - ry) * k),
                Cm(2 * rx * k),
                Cm(2 * ry * k),
            )
            m.name = f"Mark: {step}"
            m.fill.background()
            m.line.color.theme_color = T_RED
            m.line.width = Pt(2.25)
            drop_styles(m._element)
        add_text(
            s,
            x,
            y0 + ph + 0.35,
            pw,
            1.6,
            [[("sub", f"{i + 1}  "), ("bold", step)], ("body", caption)],
            f"Step {i + 1}: {step}",
        )
    shutil.rmtree(img_dir, ignore_errors=True)  # pictures are embedded by now

    add_text(
        s,
        x0,
        16.45,
        32.0,
        0.6,
        [
            (
                "caption",
                "Source: AWG online edition, op. 25, graph view filtered by SPARQL "
                "(development version, screenshots 11 Nov 2026)",
            )
        ],
        "Source line",
    )
    notes(
        s,
        "Live demo: op. 25",
        75,
        """
DEMO SCRIPT (before the talk: open the graph view of op. 25, paste the query from build/op25-demo-query.rq into the SPARQL editor, zoom about 125 %)

This is the graph of op. 25, filtered to the edition complexes and the main sketches. In the AWG, op. 25 is a composite edition complex: M 317, M 322 and M 321, in the order of the opus.

Step 1 – generated: This is what follows from the edition data alone. Three islands, one per song, ordered by numbering. The row table is there, but without any genetic relation.

Step 2 – curated: These are the editors' assertions. Look at the chain: M 317, then M 321, then M 322. Webern sketched the third song before the second – together with the row table.

Step 3 – both: Together, the chain cuts across the opus order. That is where editorial judgment begins – and the laboratory for the rest of this talk.

FALLBACK (if the live demo fails)
- Do not troubleshoot on stage. Say: "Let me show you the same thing as screenshots."
- Walk through the three panels on this slide with the same three steps.
- Before the talk: open the tab with the query, test the venue network, keep this deck locally.
""",
    )


def slide_05():
    s = content_slide(
        "The categories come from Webern's documents, not from theory",
        "Terms from the material",
        watermark=False,
    )
    cards = [  # (term, German term, where it comes from)
        (
            "sketch",
            "Skizze",
            "Sk1, Sk2, Sk2.1: the editors' numbering in the source descriptions",
        ),
        (
            "version",
            "Textfassung",
            "TF1, TF2: recognisable states of a song in the sources",
        ),
        (
            "paratext",
            "Paratext",
            "title, dating, instruments: the categories of the source descriptions",
        ),
        (
            "row table",
            "Reihentabelle",
            "Webern's sheet of row forms, a source of its own in op. 25",
        ),
        (
            "edition complex",
            "Editionskomplex",
            "what is edited together, named by opus or M number",
        ),
    ]
    x0, y0, gap, h = 0.93, 4.6, 0.4, 7.4
    w = (32.0 - 4 * gap) / 5
    for i, (term, german, origin) in enumerate(cards):
        x = x0 + i * (w + gap)
        rect(s, x, y0, w, h, f"Card: {term}", fill=T_MINT, brightness=0.6)
        rect(s, x, y0, w, 0.18, f"Card bar: {term}", fill=T_MINT)
        add_text(
            s,
            x + 0.5,
            y0 + 0.6,
            w - 1.0,
            h - 1.0,
            [("sub", term), ("code_caption", german), ("body", ""), ("body", origin)],
            f"Card text: {term}",
        )

    # strip: op. 25 as composite edition complex, parts in opus order
    sy, sh = 13.2, 1.5
    add_text(
        s,
        x0,
        sy,
        4.2,
        sh,
        [("sub", "op. 25 =")],
        "Strip label",
        anchor=MSO_ANCHOR.MIDDLE,
    )
    for i, (m, song) in enumerate([("M 317", "I"), ("M 322", "II"), ("M 321", "III")]):
        bx = x0 + 3.6 + i * 5.6
        labelled_box(s, bx, sy, 5.0, sh, m, f"Strip: {m}", style="bold", fill=T_MINT)
        add_text(
            s,
            bx,
            sy + sh + 0.25,
            5.0,
            0.6,
            [("caption", f"song {song}")],
            f"Strip caption: {m}",
            align=PP_ALIGN.CENTER,
        )
    add_text(
        s,
        x0 + 3.6 + 3 * 5.6 + 0.4,
        sy,
        10.0,
        sh,
        [
            ("caption", "a composite edition complex:"),
            ("caption", "parts in the order of the opus"),
        ],
        "Strip note",
        anchor=MSO_ANCHOR.MIDDLE,
    )
    notes(
        s,
        "Terms from the material",
        90,
        """
Where do the terms of the model come from? Not from a theory of genetic criticism, but from the documents themselves: Webern's manuscripts and the source descriptions of the AWG.

A sketch is what the editors number in the source description: Sketch 1, Sketch 2, and Sketch 2.1 for a sub-sketch. A version – in German "Textfassung" – is a recognisable state of a song, numbered TF1, TF2. Paratexts are everything on the page that accompanies the music: title, dating, pagination, instrument indications – again the categories of the source descriptions. The row table is Webern's own sheet with the forms of the twelve-tone row; in op. 25 it is a source of its own. And the edition complex is the unit the AWG edits together, named after an opus or an M number from Moldenhauer's catalogue.

Op. 25 shows how these units nest: one composite complex with three parts, M 317, M 322 and M 321, in the order of the opus. As the demo showed, the sketches follow another order.

ALT TEXT: Five cards in a row – sketch, version, paratext, row table, edition complex – each with its German term and one line on where it comes from in the documents. Below, a strip: op. 25 equals M 317, M 322, M 321, songs I to III.
""",
    )


def slide_06():
    s = content_slide(
        "Editorial terms become classes; uncertainty becomes a tag",
        "From term to class",
        watermark=False,
    )
    y0 = 4.4
    add_text(s, 0.93, y0, 18, 0.6, [("sub", "classes")], "Heading: classes")
    bh = 1.3
    # Inscription and its subclasses
    labelled_box(s, 4.4, y0 + 1.0, 6.0, bh, "Inscription", "Inscription", fill=T_MINT)
    labelled_box(s, 0.93, y0 + 4.4, 5.0, bh, "Sketch", "Sketch", fill=T_MINT)
    labelled_box(s, 8.9, y0 + 4.4, 5.0, bh, "Paratext", "Paratext", fill=T_MINT)
    tree(s, 7.4, y0 + 1.0 + bh, [3.43, 11.4], y0 + 4.4, "Tree: Inscription")
    labelled_box(
        s, 0.93, y0 + 7.8, 3.6, bh, "RowTable", "RowTable", fill=T_MINT, brightness=0.6
    )
    labelled_box(
        s,
        5.0,
        y0 + 7.8,
        6.0,
        bh,
        "ContinuityDraft",
        "ContinuityDraft",
        fill=T_MINT,
        brightness=0.6,
    )
    tree(s, 3.43, y0 + 4.4 + bh, [2.73, 8.0], y0 + 7.8, "Tree: Sketch")
    # TextVersion beside the hierarchy
    labelled_box(
        s,
        13.4,
        y0 + 1.0,
        5.4,
        bh,
        "TextVersion",
        "TextVersion",
        line=T_DARKGREEN,
        line_pt=1.25,
        dash=True,
    )
    add_text(
        s,
        13.4,
        y0 + 1.0 + bh + 0.25,
        6.6,
        1.2,
        [("caption", "abstract, not the edited sheet")],
        "Caption: TextVersion",
    )

    # uncertainty: a tag on a statement
    rx = 20.9
    add_text(s, rx, y0, 12, 0.6, [("sub", "uncertainty")], "Heading: uncertainty")
    fy, fh = y0 + 1.0, 3.4
    rect(
        s,
        rx,
        fy,
        12.0,
        fh,
        "Frame: statement",
        line=T_DARKGREEN,
        line_pt=1.0,
        dash=True,
        shape=MSO_SHAPE.ROUNDED_RECTANGLE,
    )
    add_text(
        s,
        rx + 0.4,
        fy + 0.2,
        8,
        0.5,
        [("code_caption", "EditorialStatement")],
        "Label: statement",
    )
    ny = fy + 1.3
    labelled_box(s, rx + 0.6, ny, 2.4, bh, "A", "A", style="bold", fill=T_MINT)
    labelled_box(s, rx + 9.0, ny, 2.4, bh, "B", "B", style="bold", fill=T_MINT)
    line(s, rx + 3.1, ny + bh / 2, rx + 8.9, ny + bh / 2, "Edge: precedes", head=True)
    add_text(
        s,
        rx + 3.1,
        ny - 0.15,
        5.8,
        0.6,
        [("code_caption", "precedes")],
        "Label: precedes",
        align=PP_ALIGN.CENTER,
    )
    ty = fy + fh + 1.2
    line(s, rx + 6.0, fy + fh, rx + 6.0, ty, "Tag string", color=T_RED, pt=1.5)
    labelled_box(
        s,
        rx + 2.6,
        ty,
        6.8,
        1.0,
        "certainty: uncertain",
        "Tag: certainty",
        style="code_caption",
        line=T_RED,
        line_pt=2.0,
        shape=MSO_SHAPE.ROUNDED_RECTANGLE,
    )
    add_text(
        s,
        rx,
        ty + 1.4,
        12.0,
        1.4,
        [
            ("caption", "a tag on the statement, not a relation of its own;"),
            ("caption", "without a tag, the statement counts as certain"),
        ],
        "Caption: uncertainty",
    )

    add_text(
        s,
        0.93,
        15.7,
        32.0,
        0.6,
        [
            [
                ("caption", "Classes of the draft ontology v0.1, prefix "),
                ("code_caption", "awg:"),
                ("caption", " omitted.  "),
                ("red_caption", "Not modelled yet: "),
                ("caption", "“study composition”, “ink draft”."),
            ]
        ],
        "Footnote",
    )
    notes(
        s,
        "From term to class",
        75,
        """
The next step turns these terms into classes. The superclass is Inscription: everything written on a document that we place in a genetic order. Sketch and Paratext are its subclasses – so a dating can stand in a genetic chain just like a sketch. Under Sketch there are two more specific classes: the row table and the continuity draft.

Beside this hierarchy stands TextVersion. It is abstract: not the edited sheet you see in the app, but the state of a song that sources transmit and editions edit.

Uncertainty is not a relation of its own. An earlier draft had a relation "concomitates unsure". Now an editorial statement carries a small tag: certainty uncertain. Without the tag, the statement counts as certain.

And some terms of the edition have no class yet: "study composition" and "ink draft".

ALT TEXT: Class diagram. Inscription is the superclass of Sketch and Paratext; Sketch has the subclasses RowTable and ContinuityDraft. Beside it, a dashed box TextVersion, labelled "abstract, not the edited sheet". On the right, a statement "A precedes B" in a dashed frame, with a red tag "certainty: uncertain" hanging from it. Footnote: study composition and ink draft are not modelled yet.
""",
    )


def slide_07():
    s = content_slide(
        "Two relations carry the genetic order: a sequence, or mutual influence",
        "Genetic relations",
        watermark=False,
    )
    py, ph, pw = 4.6, 8.8, 15.6
    panels = [  # (relation, start/end of A and B in panel cm, text, CRM analogy)
        (
            "precedes",
            (1.0, 9.0),
            (5.0, 14.2),
            "an order can be shown: A begins before B starts (overlap allowed)",
            "cf. CIDOC CRM P176 “starts before the start of”",
        ),
        (
            "concomitates",
            (4.4, 10.8),
            (1.0, 14.2),
            "A and B influence each other; which came first cannot be decided",
            "cf. CIDOC CRM P174 “starts before the end of” (the overlap, not the influence)",
        ),
    ]
    for i, (rel, (a0, a1), (b0, b1), text, crm) in enumerate(panels):
        x = 0.93 + i * (pw + 0.8)
        rect(s, x, py, pw, ph, f"Panel: {rel}", line=T_MINT, line_pt=1.0)
        add_text(
            s, x + 0.6, py + 0.4, pw - 1.2, 0.6, [("code", rel)], f"Heading: {rel}"
        )
        ay, by, axy, bh = py + 1.6, py + 2.9, py + 4.6, 1.0
        for lbl, (u0, u1), yy, br in (
            ("A", (a0, a1), ay, 0.0),
            ("B", (b0, b1), by, 0.4),
        ):
            rect(
                s,
                x + u0,
                yy,
                u1 - u0,
                bh,
                f"Bar {lbl}: {rel}",
                fill=T_MINT,
                brightness=br,
            )
            add_text(
                s,
                x + u0 + 0.3,
                yy,
                2,
                bh,
                [("bold", lbl)],
                f"Bar label {lbl}: {rel}",
                anchor=MSO_ANCHOR.MIDDLE,
            )
        line(
            s,
            x + 0.6,
            axy,
            x + pw - 0.6,
            axy,
            f"Time axis: {rel}",
            color=T_GREY,
            pt=1.0,
            head=True,
        )
        add_text(
            s,
            x + pw - 3.1,
            axy + 0.1,
            2.5,
            0.5,
            [("caption", "time")],
            f"Axis label: {rel}",
            align=PP_ALIGN.RIGHT,
        )
        if rel == "precedes":  # red marks: the two starts
            for u in (a0, b0):
                line(
                    s,
                    x + u,
                    ay - 0.2,
                    x + u,
                    axy,
                    f"Mark: start {u}",
                    color=T_RED,
                    pt=2.0,
                    dash=True,
                )
        else:  # red mark: the overlap, no order
            o0, o1 = max(a0, b0), min(a1, b1)
            rect(
                s,
                x + o0,
                ay - 0.15,
                o1 - o0,
                by + bh - ay + 0.3,
                "Mark: overlap",
                line=T_RED,
                line_pt=2.0,
            )
            cx = x + (o0 + o1) / 2
            line(
                s,
                cx,
                ay + bh / 2,
                cx,
                by + bh / 2,
                "Mark: mutual influence",
                color=T_RED,
                pt=2.0,
                both=True,
            )
            add_text(
                s,
                x + o1 + 0.35,
                ay,
                pw - o1 - 0.5,
                bh,
                [("red_caption", "mutual influence")],
                "Label: mutual influence",
                anchor=MSO_ANCHOR.MIDDLE,
            )
        add_text(
            s, x + 0.6, axy + 0.95, pw - 1.2, 1.6, [("body", text)], f"Text: {rel}"
        )
        add_text(
            s, x + 0.6, axy + 2.75, pw - 1.2, 1.2, [("caption", crm)], f"CRM: {rel}"
        )

    # evidence: subproperties of precedes
    ey = py + ph + 0.6
    add_text(
        s,
        0.93,
        ey,
        15,
        0.8,
        [[("sub", "evidence: subproperties of "), ("sub_code", "precedes")]],
        "Heading: evidence",
    )
    for i, (prop, basis) in enumerate(
        [
            ("precedesScripture", "page, overlay, writing instruments"),
            ("precedesContent", "musical content"),
        ]
    ):
        x = 0.93 + i * 8.0
        labelled_box(s, x, ey + 0.9, 7.6, 1.0, prop, prop, fill=T_MINT, brightness=0.6)
        add_text(s, x, ey + 2.1, 7.6, 0.6, [("caption", basis)], f"Caption: {prop}")
    notes(
        s,
        "Genetic relations",
        105,
        """
Two relations carry the genetic order.

"precedes" marks an order that can be ascribed: the evidence shows that A was begun before B. It says nothing about the end – overlap is allowed. This is deliberate: Webern often went back to an earlier sketch while he was working on a later one. The relation is transitive.

"concomitates" is a different kind of statement. The source shows that A and B were written side by side and shaped each other – a change in one is taken up in the other, and back again. Which of the two came first cannot be decided, and the relation does not pretend otherwise. So it records the mutual influence instead of inventing an order. That it is symmetric follows from this; it is not a claim about timing. And it is not transitive.

For precedes, the model can also record the kind of evidence. precedesScripture rests on the writing: position on the page, overlay, writing instruments, layers of correction. precedesContent rests on the music: the later inscription takes over changes made in the earlier one. In op. 25, the editors assert precedesScripture between Sketches 1 and 2 of M 317, and precedesContent between Sketches 2 and 3. Plain precedes leaves the evidence open.

For those who know CIDOC CRM: precedes is close to P176, "starts before the start of". For concomitates, P174, "starts before the end of", captures the overlap – but not the influence, which is the point of the relation. So these are analogies, linked with seeAlso, not equivalences – more on that later.

ALT TEXT: Two timeline panels. Left, "precedes": bar A starts before bar B, the bars overlap; red dashed lines mark the two starts. Right, "concomitates": bar A lies within bar B, a red frame marks the overlap and a vertical red double arrow between the bars, labelled "mutual influence", shows that each shapes the other. Captions: precedes – an order can be shown, A begins before B, overlap allowed; concomitates – A and B influence each other, which came first cannot be decided. CRM analogies: P176, and P174 (the overlap, not the influence). Below, two labels: precedesScripture (page, overlay, writing instruments) and precedesContent (musical content).
""",
    )


def slide_08():
    s = content_slide(
        "The model makes explicit what editorial practice leaves implicit",
        "Semantic shifts",
        watermark=False,
    )
    y0, bw, bh = 4.4, 2.4, 1.3
    # left: numbering becomes process
    add_text(
        s,
        0.93,
        y0,
        13.5,
        0.6,
        [("sub", "numbering becomes process")],
        "Heading: left",
    )
    xs = [1.3, 6.0, 10.7]
    labels = ["Sk1", "Sk2", "Sk2.1"]
    add_text(
        s,
        1.3,
        y0 + 1.1,
        12,
        0.5,
        [("caption", "source description: labels")],
        "Caption: labels",
    )
    ny, gy = y0 + 1.9, y0 + 6.4
    for x, lbl in zip(xs, labels):
        labelled_box(s, x, ny, bw, bh, lbl, f"Label {lbl}", line=T_MINT, line_pt=1.25)
        line(
            s,
            x + bw / 2,
            ny + bh + 0.1,
            x + bw / 2,
            gy - 0.1,
            f"Reading: {lbl}",
            color=T_MINT,
            pt=1.25,
            head=True,
        )
        labelled_box(s, x, gy, bw, bh, lbl, f"Node {lbl}", fill=T_MINT)
    add_text(
        s,
        xs[0] + bw / 2 + 0.3,
        ny + bh + 0.6,
        4,
        0.5,
        [("caption", "read as")],
        "Caption: read as",
    )
    line(
        s,
        xs[0] + bw + 0.1,
        gy + bh / 2,
        xs[1] - 0.1,
        gy + bh / 2,
        "Edge: precedes",
        head=True,
    )
    line(
        s,
        xs[1] + bw + 0.1,
        gy + bh / 2,
        xs[2] - 0.1,
        gy + bh / 2,
        "Edge: concomitates",
        dash=True,
    )
    for (xa, xb), rel in (
        ((xs[0], xs[1]), "precedes"),
        ((xs[1], xs[2]), "concomitates"),
    ):
        mid = (xa + bw + xb) / 2
        add_text(
            s,
            mid - 2.2,
            gy + bh + 0.25,
            4.4,
            0.5,
            [("code_caption", rel)],
            f"Label: {rel}",
            align=PP_ALIGN.CENTER,
        )
    add_text(
        s,
        1.3,
        gy + bh + 1.1,
        12,
        0.5,
        [("caption", "graph: genetic relations")],
        "Caption: graph",
    )

    # right: three editions, one superclass
    rx = 16.6
    add_text(
        s,
        rx,
        y0,
        16.3,
        0.6,
        [("sub", "three editions, one superclass")],
        "Heading: right",
    )
    cw, cg = 5.0, 0.5
    cxs = [rx + i * (cw + cg) for i in range(3)]
    ccs = [x + cw / 2 for x in cxs]
    labelled_box(
        s,
        ccs[1] - 3.3,
        y0 + 1.1,
        6.6,
        bh,
        "EditedMusicText",
        "EditedMusicText",
        fill=T_MINT,
    )
    sy = y0 + 4.4
    tree(s, ccs[1], y0 + 1.1 + bh, ccs, sy, "Tree: EditedMusicText")
    for x, cls in zip(cxs, ["WorkEdition", "TextEdition", "SketchEdition"]):
        labelled_box(s, x, sy, cw, bh, cls, cls, fill=T_MINT, brightness=0.6)
    ty = sy + 4.2
    labelled_box(
        s,
        cxs[0],
        ty,
        2 * cw + cg,
        bh,
        "TextVersion",
        "Target: TextVersion",
        line=T_DARKGREEN,
        line_pt=1.25,
        dash=True,
    )
    labelled_box(s, cxs[2], ty, cw, bh, "Sketch", "Target: Sketch", fill=T_MINT)
    for cc, cls in zip(ccs, ["WorkEdition", "TextEdition", "SketchEdition"]):
        line(s, cc, sy + bh + 0.1, cc, ty - 0.1, f"Edge: edits ({cls})", head=True)
        add_text(
            s,
            cc + 0.25,
            sy + bh + 1.2,
            2.4,
            0.5,
            [("code_caption", "edits")],
            f"Label: edits ({cls})",
        )
    add_text(
        s,
        rx,
        ty + bh + 0.5,
        16.3,
        0.5,
        [("caption", "what the edition makes, linked to what it edits")],
        "Caption: edits",
    )
    notes(
        s,
        "Semantic shifts",
        90,
        """
Modelling makes explicit what editorial practice leaves implicit. Two examples.

Left: in the source description, Sk1, Sk2 and Sk2.1 are labels – a numbering. The generator reads this numbering as a genetic process: Sketch 1 precedes Sketch 2, and the sub-sketch 2.1 concomitates with Sketch 2. A label becomes a genetic claim. Often that is right, because editors number in genetic order – but it is a claim all the same, without any evidence type. Here the graph closes what the numbering left open. And the generator never relates sketches across complexes – which is exactly where op. 25 becomes interesting.

Right: the AWG has three forms of edition – work editions, text editions and sketch editions. In the model they are subclasses of EditedMusicText: what the edition produces. Each is linked by "edits" to what it edits: work and text editions to a TextVersion, sketch editions to a Sketch. So the edited sheet and its object are kept apart.

ALT TEXT: Two panels. Left, "numbering becomes process": the labels Sk1, Sk2, Sk2.1 are read as graph nodes; Sk1 precedes Sk2 (solid arrow), Sk2.1 concomitates with Sk2 (dashed line). Right: EditedMusicText is the superclass of WorkEdition, TextEdition and SketchEdition; arrows labelled "edits" lead from the first two to TextVersion and from SketchEdition to Sketch.
""",
    )


def slide_09():
    s = content_slide(
        "The model transfers, the pipeline does not", "What transfers", watermark=False
    )
    y0, cw, gap, ih, ig = 4.4, 15.6, 0.8, 1.15, 0.3
    columns = [
        (
            "portable",
            0.0,
            [
                ("code", "Inscription", "what is written and ordered"),
                ("code", "Document", "the physical object"),
                ("code", "Folio", "one page side"),
                ("code", "Placement", "where on the page: staves, measures"),
                ("code", "precedes", "genetic order, overlap allowed"),
                ("code", "concomitates", "mutual influence, no order"),
            ],
        ),
        (
            "tied to the AWG",
            0.6,
            [
                ("bold", "the pipeline", "the generator reads the AWG's own data"),
                ("bold", "the Moldenhauer catalogue", "M numbers name the complexes"),
            ],
        ),
    ]
    for i, (head, br, items) in enumerate(columns):
        x = 0.93 + i * (cw + gap)
        labelled_box(
            s,
            x,
            y0,
            cw,
            1.2,
            head,
            f"Column: {head}",
            style="sub",
            fill=T_MINT,
            brightness=br,
        )
        h = ih if i == 0 else 2 * ih + ig  # tied items: name above gloss
        for j, (style, name, desc) in enumerate(items):
            y = y0 + 1.6 + j * (h + ig)
            rect(s, x, y, cw, h, f"Item: {name}", line=T_MINT, line_pt=1.0)
            if i == 0:
                add_text(
                    s,
                    x + 0.5,
                    y,
                    4.6,
                    h,
                    [(style, name)],
                    f"Item name: {name}",
                    anchor=MSO_ANCHOR.MIDDLE,
                )
                add_text(
                    s,
                    x + 5.2,
                    y,
                    cw - 5.6,
                    h,
                    [("caption", desc)],
                    f"Item text: {name}",
                    anchor=MSO_ANCHOR.MIDDLE,
                )
            else:
                add_text(
                    s,
                    x + 0.5,
                    y,
                    cw - 1.0,
                    h,
                    [(style, name), ("caption", desc)],
                    f"Item text: {name}",
                    anchor=MSO_ANCHOR.MIDDLE,
                )
    band(s, BAND_TOP, BAND_BOTTOM, "Band: bottom line")
    add_text(
        s,
        0.93,
        BAND_TOP,
        32.0,
        BAND_BOTTOM,
        [("bold", "Transfer to other repertoires is plausible but untested.")],
        "Bottom line",
        anchor=MSO_ANCHOR.MIDDLE,
    )
    notes(
        s,
        "What transfers",
        120,
        """
What of this model would transfer to other editions? I would separate two things.

Portable is the core of the model. Inscription, Document, Folio and Placement describe what is written where: on which object, on which page side, on which staves and measures. And the two genetic relations describe order without forcing a single line: precedes, with its two subproperties, for sequence, and concomitates for inscriptions written side by side. None of this is specific to Webern. Any edition of sketches and drafts needs the same distinctions. Placement, for instance, is a node of its own between an inscription and a page side: it records staves and measures for each page, so that one sketch can run across several pages without losing its place on any of them.

Tied to the AWG is the pipeline. The generator reads the edition's own data: its source descriptions, its sheet IDs, its numbering conventions. Another edition would need its own generator, or would have to bring its data into the same shape. The same holds for the Moldenhauer catalogue. M numbers name our edition complexes. That works for Webern because Moldenhauer catalogued the estate, including the unfinished pieces. Other repertoires have other catalogues, or none. And the numbering conventions are an even deeper tie: the generator derives precedes from "Sketch 1 before Sketch 2" – a convention of the AWG's editors, not of genetic criticism in general. Even within the AWG, the pipeline knows nothing about relations across complexes; those come only from curation.

So the honest statement is the one at the bottom: transfer to other repertoires is plausible, but untested. We have not yet modelled another composer's sketches. I would be very interested to hear whether these classes fit the material you work on.

ALT TEXT: Two columns. Left, "portable": Inscription, Document, Folio, Placement, precedes and concomitates, each with a short gloss. Right, "tied to the AWG": the pipeline and the Moldenhauer catalogue. Bottom line: transfer to other repertoires is plausible but untested.
""",
    )


def slide_10():
    s = content_slide(
        "Where claims stay open, the graph pays in queryability",
        "Frictions: model vs. data",
        watermark=False,
    )
    y0, cw, ih, ig = 4.4, 14.2, 1.9, 0.3
    columns = [
        (
            "model lags data",
            0.93,
            [
                ("staves", "free text: “1c–3c”", None),
                ("measures", "free text: “{1A}, {1B}, 1–2, 3A”", None),
                ("writing instruments", "missing: pencil, ink, crayon", None),
            ],
        ),
        (
            "data lags model",
            32.93 - cw,
            [
                ("sketchbooks", "per complex: SB3 as two excerpts", None),
                (
                    [("code", "Sk##"), ("bold", " placeholders")],
                    "29 sketches without stable identifier",
                    "placeholder",
                ),
                ("incomplete dates", "“M. am 30. IX. …”, no year", "incompleteDate"),
            ],
        ),
    ]
    for head, x, items in columns:
        labelled_box(
            s,
            x,
            y0,
            cw,
            1.2,
            head,
            f"Column: {head}",
            style="sub",
            fill=T_MINT,
            brightness=0.6,
        )
        for j, (name, desc, warning) in enumerate(items):
            runs = [("bold", name)] if isinstance(name, str) else name
            name = "".join(t for _, t in runs)
            y = y0 + 1.6 + j * (ih + ig)
            rect(s, x, y, cw, ih, f"Item: {name}", line=T_MINT, line_pt=1.0)
            add_text(
                s,
                x + 0.5,
                y,
                cw - 1.0,
                ih,
                [runs, ("caption", desc)],
                f"Item text: {name}",
                anchor=MSO_ANCHOR.MIDDLE,
            )
            if warning:
                add_text(
                    s,
                    x + cw - 7.4,
                    y + 0.3,
                    7.0,
                    0.6,
                    [("code_caption", f"warning: {warning}")],
                    f"Warning: {warning}",
                    align=PP_ALIGN.RIGHT,
                )
    mid_y = y0 + 1.6 + 1.5 * (ih + ig) - ig / 2
    line(
        s,
        0.93 + cw + 0.6,
        mid_y,
        32.93 - cw - 0.6,
        mid_y,
        "Double arrow",
        pt=2.5,
        both=True,
    )
    band(s, BAND_TOP, BAND_BOTTOM, "Band: bottom line")
    add_text(
        s,
        0.93,
        BAND_TOP,
        32.0,
        BAND_BOTTOM,
        [("sub", "Each gap is information.")],
        "Bottom line",
        anchor=MSO_ANCHOR.MIDDLE,
    )
    notes(
        s,
        "Frictions: model vs. data",
        180,
        """
Where does the model keep claims open – and what does that cost? Building the graph meant reading model and data against each other, and the open places run in both directions.

First, where the model has no form for a claim, the claim stays in prose. The source descriptions say on which staves a sketch stands – "1c to 3c", where the letters mark sections within one staff – and which measures it covers, with labels like 1A and 1B for discarded attempts. In the graph these are strings. Nothing is lost for the reader, and nothing is forced into a structure the editors did not intend. But a query cannot see them. Writing instruments – pencil, ink, coloured crayon – are described in the edition, but they are not in the model at all. Yet they are exactly what precedesScripture rests on.

Second, where the data are open themselves, the model has to leave room. The data describe sketchbook 3 twice, as two excerpts, because each edition complex describes only its own pages; the model would want one document. 29 sketches are known only as "Sk##": their number is not yet decided, so their identifiers stay unstable. And some datings have no year, such as "M. am 30. IX." – Webern left it open, and the model cannot store it as a date without inventing one. Where a dating is complete, such as the two datings that frame M 317, the model stores it – but as the date the paratext states, not as the creation date of a sketch. That, too, keeps a claim open.

The generator does not close these gaps silently. It has twelve warning rules – placeholder and incompleteDate among them, but also folioConflict, labelConflict and unresolvedReference – and reports every case, complex by complex.

So each gap is information. A free-text field shows where an open claim is kept, at the price of queryability. A placeholder shows where an editorial decision is still pending. A warning is not an error to suppress; it marks the places where the graph refuses to claim more than the evidence demands.

ALT TEXT: Two columns joined by a double arrow. Left, "model lags data": staves and measures as free text, writing instruments missing. Right, "data lags model": sketchbooks described per complex, Sk## placeholders (warning: placeholder), incomplete dates (warning: incompleteDate). Bottom line: each gap is information.
""",
    )


def slide_11():
    s = content_slide(
        "Standards serve as alignments, not as the model",
        "Standards and alignments",
        watermark=False,
    )
    cols = [
        (0.93, 7.0),
        (8.33, 17.8),
        (26.53, 6.4),
    ]  # (x, w): standard, in the model, link
    rows = [
        (
            "LRMoo",
            "edition complex ≈ F1 Work · version, sketch ≈ F2 Expression · document ≈ F5 Item",
            "rdfs:seeAlso",
        ),
        (
            "CIDOC CRM",
            "temporal reading: precedes ≈ P176, concomitates ≈ P174",
            "rdfs:seeAlso",
        ),
        (
            [("bold", "Dublin Core terms, SKOS, PROV, "), ("code", "rdf:Statement")],
            "reused outright: parts, concept schemes, attribution, statements",
            "used directly",
        ),
        ("MEI", "not integrated yet", "–"),
    ]
    # Vorlage p. 11: the dark band on top carries the slide's key statement.
    band(s, 4.2, 1.8, "Band: key statement", dark=True)
    add_text(
        s,
        0.93,
        4.2,
        32.0,
        1.8,
        [
            [
                ("band_bold", "The sketch is content and object at once"),
                ("band_body", " – which LRMoo separates (F2 Expression vs. F5 Item)."),
            ]
        ],
        "Key statement",
        anchor=MSO_ANCHOR.MIDDLE,
    )
    y, hh, rh = 6.7, 0.9, 1.75
    for (x, w), head in zip(cols, ["standard", "in the AWG model", "link"]):
        add_text(
            s,
            x + 0.3,
            y,
            w - 0.6,
            hh,
            [("sub", head)],
            f"Header: {head}",
            anchor=MSO_ANCHOR.MIDDLE,
        )
    line(s, 0.93, y + hh, 32.93, y + hh, "Header rule", pt=1.5)
    y += hh
    for i, (std, model, link) in enumerate(rows):
        rh = 2.4 if i == 2 else 1.75  # row 3: three lines in the first column
        std_runs = [("bold", std)] if isinstance(std, str) else std
        std = "".join(t for _, t in std_runs)
        if i % 2 == 0:
            rect(s, 0.93, y, 32.0, rh, f"Row band: {std}", fill=T_MINT, brightness=0.75)
        for (x, w), runs in zip(cols, [std_runs, [("body", model)], [("code", link)]]):
            text = "".join(t for _, t in runs)
            add_text(
                s,
                x + 0.3,
                y,
                w - 0.6,
                rh,
                [runs],
                f"Cell: {std} / {text[:20]}",
                anchor=MSO_ANCHOR.MIDDLE,
            )
        y += rh
    line(s, 0.93, y, 32.93, y, "Table rule", pt=1.0)
    notes(
        s,
        "Standards and alignments",
        180,
        """
How does this relate to standards? In short: standards serve as alignments, not as the model.

LRMoo, the successor of FRBRoo, offers the obvious mapping. An edition complex is close to F1 Work, a version and a sketch to F2 Expression, a document to F5 Item. CIDOC CRM gives the temporal reading of our two relations: precedes corresponds to P176, "starts before the start of", concomitates to P174, "starts before the end of" – strictly speaking between the creation events, not between the sketches themselves.

All of these links are rdfs:seeAlso, not subClassOf. They say: here is a related concept. They do not let a reasoner conclude anything. That is a deliberate choice for version 0.1. A subclass claim would commit us to everything the standard implies: if a Sketch were an F2 Expression, every inference about expressions would apply to it – including the cut between expression and item that I come to in a moment. And because the CRM relations hold between temporal entities, the ontology points to F28 Expression Creation as the event behind both of our relations.

Other vocabularies we reuse outright, because their meaning fits exactly: Dublin Core terms for parts and wholes; SKOS for our concept schemes – paratext types, certainty, catalogue types; PROV for attributing editorial statements to editors; and rdf:Statement as the superclass of these statements. For the statements themselves, CRMinf would be the natural partner: an editorial statement is close to I2 Belief, the argumentation behind it to I1. That, too, is noted as seeAlso.

MEI is not integrated. Our edited music texts are SVG sheets, not MEI encodings; linking graph nodes to MEI elements is a later step.

And here – the statement at the top of the slide – is where the standard does not fit. LRMoo separates content and object: the expression on the one hand, the item that carries it on the other. For a printed edition that is a clean cut. For a sketch it is not. A sketch is content and object at once: its position on the page, its overlay with other inscriptions, the writing instrument – these physical facts are the evidence for its genetic place. Split it into F2 and F5, and you split the argument. So the AWG keeps Sketch as one class and only points to LRMoo.

ALT TEXT: At the top, in a dark teal band: the sketch is content and object at once, which LRMoo separates (F2 Expression vs. F5 Item). Below, a table with three columns – standard, in the AWG model, link. LRMoo: edition complex about F1 Work, version and sketch about F2 Expression, document about F5 Item (rdfs:seeAlso). CIDOC CRM: temporal reading, precedes about P176, concomitates about P174 (rdfs:seeAlso). Dublin Core terms, SKOS, PROV, rdf:Statement: reused outright (used directly). MEI: not integrated.
""",
    )


def slide_12():
    s = content_slide(
        "The mismatch between model and data is the analytical gain",
        "Conclusion and outlook",
        watermark=False,
    )
    # Vorlage p. 3: image on the left, mint panel with the key points on the right.
    top, h, iw = 4.22, 11.9, 15.8
    px = 0.93 + iw + 0.4
    washed_picture(
        s,
        "op25-graph-full-labels.png",
        (500, 700, 2100, 1900),  # close enough for legible labels
        0.93,
        top,
        iw,
        h,
        0.75,
        "Image: op. 25 graph, detail",
        "Detail of the op. 25 graph view with node labels such as M 321 Sk5 and awg:Sketch",
    )
    add_text(s, 0.93, top + h + 0.2, iw, 0.9, [("source", GRAPH_SOURCE)], "Source line")
    band_panel = rect(s, px, top, 32.93 - px, h, "Panel: conclusions", fill=T_MINT)
    set_alpha(band_panel._element.spPr, 50)
    statements = [
        [("statement", "Layers show where editorial judgment begins.")],
        [("statement", "Warnings show where the data disagree.")],
        [
            ("statement", "Model and data are written side by side: "),
            ("statement_term", "concomitant"),
            ("statement", "."),
        ],
    ]
    tx, tw = px + 0.8, 32.93 - px - 1.6
    y = top + 0.7
    for i, st in enumerate(statements):
        rect(s, px + 0.8, y, 0.2, 2.2, f"Statement bar {i + 1}", fill=T_DARKGREEN)
        add_text(
            s,
            tx + 0.6,
            y,
            tw - 0.6,
            2.2,
            [st],
            f"Statement {i + 1}",
            anchor=MSO_ANCHOR.MIDDLE,
        )
        y += 2.65
    add_text(
        s,
        tx + 0.6,
        y + 0.3,
        tw - 0.6,
        1.8,
        [
            [
                ("sub", "Next steps: "),
                ("body", "named graphs for ink and pencil layers, persons, archives"),
            ]
        ],
        "Next steps",
    )
    notes(
        s,
        "Conclusion and outlook",
        120,
        """
Back to the opening question: can the graph keep claims as open as the evidence demands? Partly. The model has means for openness: concomitates instead of an invented order, plain precedes where the evidence is not specified, a certainty tag on a statement. Where it has none, openness survives as free text and gaps – readable, but not queryable. And where the generator reads numbering as process, it closes more than the editors claimed. Three conclusions follow.

First: layers show where editorial judgment begins. The generated layer says what follows from the data; the curated layer says what editors assert. In op. 25, the difference is the chain across the songs: the editors' argument, made visible.

Second: warnings show where the data disagree. The generator does not silently repair the data. Every placeholder, every incomplete date, every conflict between folio and label is reported.

Third: model and data are written side by side – concomitant, in the sense of our own relation. Neither came first. The model was revised wherever the data resisted, and the data will be revised wherever the model shows gaps. Their relation is not an order, but mutual influence. In that sense, "compositional processes as graph" also means: the graph itself is in process.

Next steps: the editorial statements will move into named graphs, so that, for example, the ink and pencil layers of a sketch can be kept apart. Today about 116 curated edges are reified as statements; then statement nodes remain only where uncertainty or a justification needs them. And persons and archives, so far only open questions, will become part of the model.

ALT TEXT: Left, a pale teal detail of the op. 25 graph with node labels. Right, a mint panel with three conclusions: layers show where editorial judgment begins; warnings show where the data disagree; model and data are written side by side – concomitant. Below: next steps, named graphs for ink and pencil layers, persons, archives.
""",
    )


def slide_13():
    # Bookend to slide 2: same frame, another region of the same graph.
    s = content_slide(
        "If model and data shape each other, the graph is also our construction",
        "Closing question",
        watermark=False,
    )
    pic = washed_picture(
        s,
        "op25-graph-full.png",
        (0, 1100, 2808, 2740),  # lower half; bottom edge cuts off the app toolbar
        0.0,
        0.0,
        33.87,
        19.05,
        0.6,
        "Background: op. 25 graph",
        "Graph view of op. 25 with all triples, without labels: a dense network of nodes and edges",
    )
    to_back(s, pic)
    band(s, 10.8, 5.8, "Band: closing question", dark=True)
    add_text(
        s,
        0.93,
        11.2,
        28.5,
        2.9,
        [("closing_light", "Whose genetic order does the graph show – Webern's or ours?")],
        "Question",
    )
    add_text(
        s,
        0.93,
        14.1,
        28.5,
        1.8,
        [
            (
                "closing_sub_light",
                "How much of Webern's compositional process survives translation "
                "into shared standards?",
            )
        ],
        "Second question",
    )
    add_text(
        s,
        0.93,
        16.0,
        31.5,
        0.5,
        [("source_light", GRAPH_SOURCE)],
        "Source line",
        align=PP_ALIGN.RIGHT,
    )
    notes(
        s,
        "Closing question",
        60,
        """
I would like to end with a question rather than a result.

If model and data shape each other – if they are, in our own term, concomitant – then the graph is not simply Webern's process, read off the documents. It is also our construction: our numbering, our evidence types, our decisions about what counts as a relation. So: whose genetic order does the graph show – Webern's, or ours?

The second question looks outward. A sketch whose page is its argument is exactly what a shared standard tends to split. So: how much of Webern's compositional process survives translation into shared standards?

I look forward to your answers – and to your material. Thank you.

STAGE: Stay on this slide during the discussion; go to slide 14 (contact) only at the very end.

ALT TEXT: Behind the slide, a pale image of another region of the full op. 25 graph. In a dark teal band, in white: whose genetic order does the graph show – Webern's or ours? Below, smaller: how much of Webern's compositional process survives translation into shared standards?
""",
    )


def slide_14():
    s = prs.slides.add_slide(LAYOUT_TITLE)
    for t in ("ctrTitle", "subTitle"):
        remove_ph(s, t)
    add_text(s, 2.33, 3.6, 21.5, 1.6, [("closing", "Thank you")], "Thank you")
    add_text(
        s,
        2.33,
        6.0,
        21.5,
        0.8,
        [("sub", f"{SPEAKER} · Anton Webern Gesamtausgabe, University of Basel")],
        "Speaker",
    )
    contact = add_text(
        s,
        2.33,
        7.2,
        21.5,
        1.6,
        [("body", EMAIL), ("body", EDITION_URL.removeprefix("https://"))],
        "Contact",
    )
    runs = list(contact._element.iter(qn("a:r")))
    link_run(s, runs[0], f"mailto:{EMAIL}")
    link_run(s, runs[1], EDITION_URL)
    add_watermark(s, 25.0, 3.0, 0.7, WHITE, 55, 65)
    notes(
        s,
        "Contact",
        0,
        """
STAGE: Show only after the discussion (or when the chair closes the session); no spoken text. Slide 13 stays up during the Q&A.
""",
    )


SECTIONS = (
    ["Introduction"] * 4
    + ["Terminology"] * 4
    + ["Transferability"] * 2
    + ["Standards"]
    + ["Conclusion"] * 3
)

for build_slide in (
    slide_01,
    slide_02,
    slide_03,
    slide_04,
    slide_05,
    slide_06,
    slide_07,
    slide_08,
    slide_09,
    slide_10,
    slide_11,
    slide_12,
    slide_13,
    slide_14,
):
    build_slide()
assert ELAPSED[0] == 20 * 60, ELAPSED[0]

# ================================================================ drop template slides
sld_id_lst = prs.slides._sldIdLst
n_template = len(sld_id_lst) - len(SECTIONS)
for sld_id in list(sld_id_lst)[:n_template]:
    prs.part.drop_rel(sld_id.get(qn("r:id")))
    sld_id_lst.remove(sld_id)
prs.part.rename_slide_parts([s.get(qn("r:id")) for s in sld_id_lst])

# ================================================================ sections
P14 = "http://schemas.microsoft.com/office/powerpoint/2010/main"
pres_el = prs.part._element
ext_lst = pres_el.find(qn("p:extLst"))
if ext_lst is None:
    ext_lst = etree.SubElement(pres_el, qn("p:extLst"))
ext = etree.Element(qn("p:ext"), uri="{521415D9-36F7-43E2-AB2F-B90AF26B5E84}")
sec_lst = etree.SubElement(ext, f"{{{P14}}}sectionLst", nsmap={"p14": P14})
current = None
for sld_id, section in zip(sld_id_lst, SECTIONS):
    if section != current:
        sec = etree.SubElement(
            sec_lst,
            f"{{{P14}}}section",
            name=section,
            id="{" + str(uuid.uuid4()).upper() + "}",
        )
        ids = etree.SubElement(sec, f"{{{P14}}}sldIdLst")
        current = section
    etree.SubElement(ids, f"{{{P14}}}sldId", id=sld_id.get("id"))
ext_lst.insert(0, ext)

prs.core_properties.title = "Compositional Processes as Graph"
prs.save(OUT)
print("saved", OUT, len(prs.slides), "slides")

# ================================================================ PDF
SOFFICE = shutil.which("soffice") or r"C:\Program Files\LibreOffice\program\soffice.exe"
PDF = os.path.splitext(os.path.abspath(OUT))[0] + ".pdf"
work = tempfile.mkdtemp(prefix="lo_awg_")
subprocess.run(
    [
        SOFFICE,
        f"-env:UserInstallation=file:///{work.replace(os.sep, '/')}/profile",
        "--headless",
        "--convert-to",
        "pdf",
        "--outdir",
        work,
        OUT,
    ],
    check=True,
    timeout=300,
    capture_output=True,
)
try:
    shutil.copyfile(os.path.join(work, os.path.basename(PDF)), PDF)
    print("saved", PDF)
except PermissionError:
    shutil.rmtree(work, ignore_errors=True)
    sys.exit(
        f"PDF not updated: {PDF} is locked (open in a viewer?). Close it and run again."
    )


# ================================================================ overview grid
def make_grid(pdf, out_jpg, cols=3, dpi=50, gap=12):
    """Render every page of pdf and tile them, numbered, into out_jpg."""
    from PIL import Image, ImageDraw, ImageFont

    pdftoppm = shutil.which("pdftoppm")
    if pdftoppm is None:
        print("grid skipped: pdftoppm not found")
        return
    subprocess.run(
        [pdftoppm, "-jpeg", "-r", str(dpi), pdf, os.path.join(work, "page")],
        check=True,
        timeout=300,
    )
    pages = sorted(
        f for f in os.listdir(work) if f.startswith("page") and f.endswith(".jpg")
    )
    images = [Image.open(os.path.join(work, f)) for f in pages]
    w, h = images[0].size
    rows = -(-len(images) // cols)
    grid = Image.new(
        "RGB",
        (cols * w + (cols + 1) * gap, rows * h + (rows + 1) * gap),
        (140, 145, 150),
    )
    draw = ImageDraw.Draw(grid)
    try:
        font = ImageFont.truetype("arialbd.ttf", 18)
    except OSError:
        font = ImageFont.load_default()
    for i, im in enumerate(images):
        x, y = gap + (i % cols) * (w + gap), gap + (i // cols) * (h + gap)
        grid.paste(im, (x, y))
        draw.rectangle([x, y, x + 30, y + 26], fill=(210, 5, 55))
        draw.text((x + 6, y + 3), str(i + 1), fill="white", font=font)
        im.close()
    grid.save(out_jpg, quality=85)
    print("saved", out_jpg)


try:
    make_grid(PDF, os.path.join(HERE, "grid.jpg"))
finally:
    shutil.rmtree(work, ignore_errors=True)
