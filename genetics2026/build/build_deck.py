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
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE, MSO_SHAPE_TYPE
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
SPEAKER = "Dr. Stefan Münnich"
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
TOTAL = 25 * 60  # the full 25 minutes slot, no reserve


def notes(slide, label, seconds, text, alt=None):
    ELAPSED[0] += seconds
    slide.notes_slide.notes_text_frame.text = (
        f"[{label}] Target time: {fmt_time(seconds)} (cumulative {fmt_time(ELAPSED[0])} of {fmt_time(TOTAL)})\n\n"
        + text.strip()
    )
    if alt:
        set_alt(slide, alt.strip())


def set_alt(slide, descr):
    """Alt text: on the slide's picture if it has one, else on a group of its diagram shapes."""
    pics = [sh for sh in slide.shapes if sh.shape_type == MSO_SHAPE_TYPE.PICTURE]
    if pics:
        assert len(pics) == 1, [p.name for p in pics]
        pics[0]._element.nvPicPr.cNvPr.set("descr", descr)
        return
    members = [
        sh
        for sh in slide.shapes
        if not sh.is_placeholder and not sh.name.startswith("Watermark")
    ]
    group = slide.shapes.add_group_shape(members)
    group.name = "Diagram"
    group._element.nvGrpSpPr.cNvPr.set("descr", descr)


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
            "“Comparative Perspectives on Genetic Criticism in Music”",
            "International Conference of the IMS Study Group",
            "Rome, German Historical Institute, 16–18 November 2026",
        ],
    )
    notes(
        s,
        "Title",
        40,
        """
Thank you for the kind introduction, and thank you for the invitation, especially since our project, the Anton Webern Gesamtausgabe, is not a genetic edition in the strict sense. But Webern can't be edited without addressing or understanding his complex compositional processes. So, as a word of caution, the "genetic" approach I present is more a pragmatic one, not a fully fledged theory of genetic criticism – I hope it offers some insights nonetheless.
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
        90,
        """
Let me put the talk's question first.

[Pause, let the slide speak.]

As we have seen in several papers today already, compositional processes rarely form a linear sequence. Sketches overlap and are spread over sketchbooks and loose sheets; earlier stages of a work may be scattered across manuscripts, places or years. In short, the surviving sources most often form a network of relations.

However, editions in a traditional sense, following the page-based linearity of the book, had to choose some order. Digital editions set out to overcome this linearity with hypertextuality. But do they really? Don't we still tend to streamline writing layers and editorial findings into our narratives (a curated "pathway" through the edition as Kepper/Pugin called it some years ago)? Open findings, discarded, overwritten, erased attempts, ruptures or uncertainty remain a challenge for a digital environment that strives for completeness and explicitness.

So: how can a digital edition represent such non-linear processes – in other words, how do we keep open what cannot be finally described or decided, and yet hold it in a formal model? That is this talk's question. As you may have guessed from the slide, our approach to it is a graph-based one.
""",
        alt="""
Behind the slide, a pale teal image of the full op. 25 graph: hundreds of nodes and edges without labels. In a dark teal band, the research question in white.
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
        "The AWG graph combines generated data with curated editorial assertions",
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
In its online edition, the AWG adds the graph as a semantic view of these materials. In its current state, which is still in development (and unfortunately not publicly available yet), it combines two layers. One layer is automatically generated from the edition's structured data: hierarchy, sources, folios, placements, and relations that follow from the sketch sigla numbering. A curated layer holds what only editors can assert: evidence-based order, or uncertainty.

Both layers are described by one RDF ontology which together with the data can be queried with SPARQL and exported as Turtle.
""",
        alt="""
A frame labelled draft ontology v0.1, with the edition URL edition.anton-webern.ch at its top right. Inside, two stacked layers, each with a small graph: the generated layer, derived from the edition's structured data, and the curated layer, hand-modelled editorial assertions. Below: queried with SPARQL in the app, exported as Turtle. No reasoning.
""",
    )


# Graph view of op. 25 in three steps, one slide each (no live demo).
# Canvas captures at DPR 3 (Chrome "Capture node screenshot").
# (file, step, caption, crop box, red marks as (cx, cy, rx, ry, angle)),
# crop box and marks in pixels of the original capture; a mark on an edge is
# an ellipse along it (angle in degrees, clockwise) that encloses both nodes.
OP25_PANELS = [
    (
        "op25-graph-generated-canvas.png",
        "generated",
        "three “islands”, one per song",
        (66, 249, 3426, 2251),
        [(2228, 1175, 284, 81, 0)],
    ),  # Op25_SkRT without genetic relations
    (
        "op25-graph-curated-canvas.png",
        "curated",
        "one chain across the songs",
        (128, 115, 3327, 2478),
        [(803, 1358, 322, 75, 48.8), (1813, 849, 320, 75, -33.2)],
    ),  # M317 Sk4 → M321 Sk1, M321 Sk9 → M322 Sk1
    (
        "op25-graph-both-canvas.png",
        "both",
        "the difference: editorial judgment",
        (261, 161, 2845, 2567),  # bottom edge cuts off the app toolbar
        [(1266, 1307, 442, 75, -21.0)],
    ),  # M321 Sk9 → M322 Sk1
]
OP25_TITLES = [
    "Generated from the edition data alone, op. 25 falls into three “islands”",
    "The curated layer links the three songs in one chain",
    "The combined layers show where editorial judgment becomes explicit",
]
OP25_NOTES = [
    (
        35,
        """
So to give you an example upfront, this is the graph view of Webern's op. 25 (Three songs after poems by Hildegard Jone), with the catalogue numbers M 317, M 322 and M 321 standing for these three songs.

In the automatically generated layer, you can see the three "islands", one per song, ordered by numbering of their sketches. The row table is there [red mark], but without any genetic relation.
""",
        """
Screenshot of the graph view of op. 25, generated layer: three separate clusters of nodes, one per song; a red ellipse marks the row table node without genetic relations. Beside it, the three steps, step 1 highlighted: generated – three “islands”, one per song.
""",
    ),
    (
        30,
        """
In the curated layer, the editors' assertions add a connection [red marks] from M 317 Sk4 to M 321 Sk1, then M 321 Sk9 to M 322 Sk1. Webern sketched the third song of the opus, M 321, before the second, M 322 – together with the row table, which is now part of many more relations.
""",
        """
Screenshot of the graph view of op. 25, curated layer: one connected chain; red ellipses mark the links from M 317 Sk4 to M 321 Sk1 and from M 321 Sk9 to M 322 Sk1. Beside it, the three steps, step 2 highlighted: curated – one chain across the songs.
""",
    ),
    (
        30,
        """
When we combine both layers, the "islands" are still there: within each song, the numbering already gives an order. The connection across the songs [red mark] is what only the curated layer brings in. That difference is where the editorial judgment becomes explicit – and the laboratory for the rest of this talk.

[Not spoken: the screenshots come from the app's graph view, filtered with the SPARQL query in build/op25-demo-query.rq.]
""",
        """
Screenshot of the graph view of op. 25, both layers; a red ellipse marks the link from M 321 Sk9 to M 322 Sk1, against the opus order. Beside it, the three steps, step 3 highlighted: both – the difference: editorial judgment.
""",
    ),
]


def op25_slide(idx):
    file, step, caption, crop, marks = OP25_PANELS[idx]
    s = content_slide(OP25_TITLES[idx], "Graph view: op. 25", watermark=False)
    from PIL import Image

    img_dir = tempfile.mkdtemp(prefix="awg_img_")
    x0, y0, pw, ph = 0.93, 4.3, 21.6, 11.4
    sx = x0 + pw + 0.8  # steps column, same position on all three slides
    with Image.open(os.path.join(HERE, "img", file)) as im:
        im = im.convert("RGB").crop(crop)
        f = min(1.0, 2400 / max(im.size))  # at most 2400 px
        im = im.resize((round(im.width * f), round(im.height * f)), Image.LANCZOS)
        path = os.path.join(img_dir, file)
        im.save(path, optimize=True)
        iw, ih = im.size
    marks = [
        ((cx - crop[0]) * f, (cy - crop[1]) * f, rx * f, ry * f, a)
        for cx, cy, rx, ry, a in marks
    ]
    k = min(pw / iw, ph / ih)  # cm per pixel
    w, h = iw * k, ih * k
    ix, iy = x0 + (pw - w) / 2, y0 + (ph - h) / 2  # centred in its area
    pic = s.shapes.add_picture(path, Cm(ix), Cm(iy), Cm(w), Cm(h))
    pic.name = f"Screenshot: {step}"
    pic._element.nvPicPr.cNvPr.set(
        "descr", f"Graph view of op. 25, {step} layer, filtered by SPARQL"
    )
    shutil.rmtree(img_dir, ignore_errors=True)  # the picture is embedded by now
    frame = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Cm(ix), Cm(iy), Cm(w), Cm(h))
    frame.name = f"Frame: {step}"
    frame.fill.background()
    frame.line.color.theme_color = T_MINT
    frame.line.width = Pt(1)
    drop_styles(frame._element)
    for cx, cy, rx, ry, a in marks:
        m = s.shapes.add_shape(
            MSO_SHAPE.OVAL,
            Cm(ix + (cx - rx) * k),
            Cm(iy + (cy - ry) * k),
            Cm(2 * rx * k),
            Cm(2 * ry * k),
        )
        m.rotation = a
        m.name = f"Mark: {step}"
        m.fill.background()
        m.line.color.theme_color = T_RED
        m.line.width = Pt(2.25)
        drop_styles(m._element)

    # the three steps beside the screenshot; the current one highlighted
    sw = 32.93 - sx
    for j, (_, st, cap, _, _) in enumerate(OP25_PANELS):
        sy = y0 + j * 3.1
        if j == idx:
            rect(
                s,
                sx - 0.4,
                sy - 0.25,
                sw + 0.4,
                2.8,
                f"Current step: {st}",
                fill=T_MINT,
                brightness=0.6,
            )
            paras = [[("sub", f"{j + 1}  "), ("bold", st)], ("body", cap)]
        else:
            paras = [[("caption", f"{j + 1}  {st}")], ("caption", cap)]
        add_text(s, sx, sy, sw - 0.3, 1.9, paras, f"Step {j + 1}: {st}")

    add_text(
        s,
        x0,
        16.1,
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
    seconds, text, alt = OP25_NOTES[idx]
    notes(s, f"Graph view: op. 25 ({idx + 1}/3)", seconds, text, alt)


def slide_04_generated():
    op25_slide(0)


def slide_04_curated():
    op25_slide(1)


def slide_04_both():
    op25_slide(2)


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
            "title, dating, instrumentation: the categories of the source descriptions",
        ),
        (
            "row table",
            "Reihentabelle",
            "Webern's sheet of row forms",
        ),
        (
            "edition complex",
            "Editionskomplex",
            "all edition-relevant material of a composition, by opus or M number",
        ),
    ]
    x0, y0, gap, h = 0.93, 4.6, 0.4, 7.0
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

    # case row: each category as it occurs in op. 25, one box under each card
    cy, ch = 13.0, 3.3
    add_text(s, x0, cy - 0.95, 8.0, 0.7, [("sub", "in op. 25")], "Case label")
    nb = lambda t: t.replace(" ", " ").replace("–", "⁠–⁠")  # no break in "M 317", "Sk1–4"
    cases = [
        (
            "sketch",
            f"{nb('M 317 Sk1–4')}, {nb('M 321 Sk1–9')}, {nb('M 322 Sk1–4')}, with sub-sketches",
        ),
        ("version", f"{nb('M 317 TF2')}, {nb('M 322 TF1')}, {nb('M 321 TF1')}"),
        (
            "paratext",
            f"title, datings ({nb('4. VII. 34')}), paginations, instrumentations",
        ),
        ("row table", f"one sheet, written alongside {nb('M 321 Sk1–9')}"),
        (
            "edition complex",
            f"composite: {nb('M 317')}, {nb('M 322')}, {nb('M 321')} (songs {nb('I–III')})",
        ),
    ]
    for i, (term, text) in enumerate(cases):
        x = x0 + i * (w + gap)
        rect(s, x, cy, w, ch, f"Case box: {term}", line=T_MINT, line_pt=1.5)
        add_text(
            s,
            x + 0.5,
            cy,
            w - 1.0,
            ch,
            [("caption", text)],
            f"Case text: {term}",
            anchor=MSO_ANCHOR.MIDDLE,
        )
    notes(
        s,
        "Terms from the material",
        95,
        """
Before we look into Webern's sketches, let me take a few minutes for the model behind this graph: its terms, its classes, its relations, and how it relates to formal standards.

So, where do the terms of the model come from? Not from a theory of genetic criticism, but from editorial practice: they name what the editors find in Webern’s documents, as recorded in the AWG’s source descriptions.

A sketch is a unit of writing the editors identify on the page and number: Sketch 1, Sketch 2, and Sketch 2.1 for a sub-sketch. A version – the Textfassung from before – is a state of the musical text, numbered TF1, TF2. Paratexts are everything on the page that accompanies the music: title, dating, pagination, also instrumentations if not the same complex. The row table is Webern’s own sheet with the forms of the twelve-tone row – and, as the graph view showed, part of Webern's compositional process. The edition complex comprises everything relevant to an edition of a composition – single, or composite like op. 25. It is named by opus number or by M number from Hans Moldenhauer’s catalogue.

Below each term, you see how it occurs in op. 25 – the example from the graph view.
""",
        alt="""
Five cards in a row – sketch, version, paratext, row table, edition complex – each with its German term and one line on where it comes from in the documents. Below each card, under the heading "in op. 25", a framed box with the case: sketches M 317 Sk1–4, M 321 Sk1–9, M 322 Sk1–4 with sub-sketches; versions M 317 TF2, M 322 TF1, M 321 TF1; paratexts such as the title, datings (4. VII. 34), paginations, instrumentations; the row table, one sheet written alongside M 321 Sk1–9; the edition complex, composite of M 317, M 322, M 321 (songs I–III).
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
        85,
        """
In the source descriptions, these terms are used as editors use them: flexibly, and explained in prose. A graph needs more. It has to say what belongs to a category, and how the categories relate to each other. So each term becomes a class.

The first question was: what do a sketch and a paratext have in common? Both are written on a page, and both have a place in the compositional process – a title or a dating is written at some point, too. So the superclass is Inscription: everything written on a document that we can place in that process. Sketch and Paratext are its subclasses. Under Sketch, there are two more specific classes: the row table and the continuity draft.

Uncertainty is not a relation of its own. An earlier draft had a relation "concomitates unsure". Now an editorial statement carries an uncertainty tag: certainty, uncertain. Without the tag, the statement counts as certain.

Some terms of the edition have no class yet like "study composition" and "ink draft", but we are in the process of including them.
""",
        alt="""
Class diagram. Inscription is the superclass of Sketch and Paratext; Sketch has the subclasses RowTable and ContinuityDraft. On the right, a statement "A precedes B" in a dashed frame, with a red tag "certainty: uncertain" hanging from it. Footnote: study composition and ink draft are not modelled yet.
""",
    )


def slide_02_editions():
    # wording after the AWG preface (en): work / text / sketch editions,
    # versions of the musical text (Textfassungen), sketches
    s = content_slide(
        "The AWG distinguishes three forms of edition, by transmission and use",
        "The Anton Webern Gesamtausgabe",
        watermark=False,
    )
    cards = [  # (term, German term, what it presents)
        (
            "work editions",
            "Werkeditionen",
            "published or intended for print (op. 1–31)",
        ),
        ("text editions", "Texteditionen", "beyond a sketch, not concluded in print"),
        (
            "sketch editions",
            "Skizzeneditionen",
            "diplomatic transcriptions, mostly pencil",
        ),
    ]
    x0, y0, gap, h = 0.93, 4.4, 1.0, 5.0
    w = (32.0 - 2 * gap) / 3
    xs = [x0 + i * (w + gap) for i in range(3)]
    for x, (term, german, gloss) in zip(xs, cards):
        rect(s, x, y0, w, h, f"Card: {term}", fill=T_MINT, brightness=0.6)
        rect(s, x, y0, w, 0.18, f"Card bar: {term}", fill=T_MINT)
        add_text(
            s,
            x + 0.5,
            y0 + 0.6,
            w - 1.0,
            h - 1.0,
            [("sub", term), ("code_caption", german), ("body", ""), ("body", gloss)],
            f"Card text: {term}",
        )

    # what they edit: versions (work and text editions) and sketches
    ty, th = y0 + h + 2.0, 1.9
    targets = [
        (xs[0], 2 * w + gap, "versions of the musical text", "Textfassungen", True),
        (xs[2], w, "sketches", "Skizzen", False),
    ]
    for x, tw, term, german, dashed in targets:
        if dashed:
            rect(
                s,
                x,
                ty,
                tw,
                th,
                f"Target: {term}",
                line=T_DARKGREEN,
                line_pt=1.25,
                dash=True,
            )
        else:
            rect(s, x, ty, tw, th, f"Target: {term}", fill=T_MINT)
        add_text(
            s,
            x,
            ty,
            tw,
            th,
            [("sub", term), ("code_caption", german)],
            f"Target text: {term}",
            align=PP_ALIGN.CENTER,
            anchor=MSO_ANCHOR.MIDDLE,
        )
    for x, (term, _, _) in zip(xs, cards):
        cx = x + w / 2
        line(s, cx, y0 + h + 0.1, cx, ty - 0.1, f"Edge: edit ({term})", head=True)
        add_text(
            s,
            cx + 0.25,
            y0 + h + 0.7,
            2.4,
            0.5,
            [("code_caption", "edit")],
            f"Label: edit ({term})",
        )
    add_text(
        s,
        xs[0],
        ty + th + 0.3,
        2 * w + gap,
        0.6,
        [("caption", "a state of the musical text, attested by one or more sources")],
        "Caption: versions",
    )
    notes(
        s,
        "The AWG and its editions",
        80,
        """
But first, a word on the edition project itself. The Anton Webern Gesamtausgabe is a historical-critical complete edition of Anton Webern's compositions, in print and online. It distinguishes three forms of edition, depending on how the sources have come down to us and on the intended usage: work, text and sketch editions.

Work editions present the versions published in Webern's lifetime or intended for publication: op. 1 to 31, and his arrangements of other composers' works. Text editions present versions that go beyond a sketch but were not concluded in print: study compositions, fragments, earlier versions of published works. Both edit a version of the musical text – in German, a "Textfassung". A version is not a document: it is a state of the musical text, attested by one or more sources.

Sketch editions edit Webern's sketches – mostly in pencil, and most often, but not always, connected to a Textfassung.

The three forms also differ in detail and standardisation: sketch editions come close to diplomatic transcription; work editions standardise most, towards a performable score.
""",
        alt="""
Three cards in a row: work editions (Werkeditionen) – published or intended for print, op. 1–31; text editions (Texteditionen) – beyond a sketch, not concluded in print; sketch editions (Skizzeneditionen) – diplomatic transcriptions, mostly pencil. Arrows labelled "edit" lead from the first two cards to a dashed box "versions of the musical text (Textfassungen)", captioned "a state of the musical text, attested by one or more sources", and from the third card to a box "sketches (Skizzen)".
""",
    )


# Slide 19 of the talk #GraphSDE2019: Google Slides SVG export (page
# g58b40a2515_0_19), rendered at 3x with headless Edge, white margin trimmed.
M307_2019 = "graphsde2019-m307.png"


def slide_09_m307():
    s = content_slide(
        "A process Webern kept reordering, and then dropped, becomes graspable",
        "Exploring the graph: M 307",
        watermark=False,
    )
    # Vorlage p. 12: picture 3/4, text 1/4
    from PIL import Image

    with Image.open(os.path.join(HERE, "img", M307_2019)) as im:
        iw_px, ih_px = im.size
    fx, fy, fh = 0.93, 4.4, 11.6
    fw = fh * iw_px / ih_px
    pic = s.shapes.add_picture(
        os.path.join(HERE, "img", M307_2019), Cm(fx), Cm(fy), Cm(fw), Cm(fh)
    )
    pic.name = "Graph: M 307 (2019)"
    pic._element.nvPicPr.cNvPr.set(
        "descr",
        "Hand-drawn genetic graph of M 307 from 2019: sketches Sk1 to Sk8 in four groups "
        "(for 4 voices, row variants, for 3 voices, for 1 voice and piano), coloured by "
        "folio (fol. 3v, 4v, 5r), linked by precedes arrows, concomitates double arrows "
        "and dotted 'probably' lines; two datings, 7 July 1930 and 9 July 1930",
    )
    rect(s, fx, fy, fw, fh, "Frame: M 307 (2019)", line=T_MINT, line_pt=1.0)

    tx = fx + fw + 0.8
    tw = 32.93 - tx
    add_text(
        s,
        tx,
        fy,
        tw,
        fh,
        [
            ("sub", "the scoring shifts"),
            (
                "body",
                "four voices, three voices, voice and piano – row variants in between",
            ),
            ("sub", "across the pages"),
            (
                "body",
                "sketches of fol. 3v, 4v and 5r, ordered across the groups of scoring",
            ),
            ("sub", "for the editors"),
            ("body", "a way into a process that Webern finally abandoned"),
        ],
        "Text: what the graph shows",
        space_after=8,
    )
    add_text(
        s,
        0.93,
        16.45,
        32.0,
        0.6,
        [
            (
                "caption",
                "Source: Stefan Münnich/Thomas Ahrend, own graphic (2019): "
                "sketch graph of M 307",
            )
        ],
        "Source line",
    )
    notes(
        s,
        "Exploring the graph: M 307",
        85,
        """
A second example, from the beginnings of our work with the idea of graphs: a sketch graph of M 307, which we drew by hand in 2019. Here the process is even less linear than in op. 25.

Webern had not settled the scoring: He starts for four voices [top band], tries out row variants [left], changes to three voices [middle], and ends with voice and piano [bottom right]. He keeps reordering – and in the end he abandons the piece.

On paper, these sketches are spread over three pages, and their order is anything but obvious – even if you took the numbering as chronological order, it would not tell you which sketch belongs to which scoring. As a graph, the process becomes something you can place: you see which sketch leads where, across the changes of scoring, and where the order stays open.

For our editors, that was the point of drawing it: it made a process we could not yet describe in words graspable – and it showed us what a model would have to hold.
""",
        alt="""
Left, a genetic graph of M 307, drawn by hand in a slide program in 2019. Coloured boxes for the sketches Sk1 to Sk8 and their sub-sketches sit in four tinted groups: for 4 voices, row variants, for 3 voices, for 1 voice and piano. A legend gives box colours for fol. 3v, 4v and 5r, and three line types: concomitates (double arrow), precedes (arrow), probably (dotted). Two datings, 7. Juli [1930] and 9. VII[.] 1930. Right, three short points: the scoring shifts – four voices, three voices, voice and piano, row variants in between; across the pages – sketches of fol. 3v, 4v and 5r, ordered across the groups of scoring; for the editors – a way into a process that Webern finally abandoned. Below: dotted, the same two relations, held as uncertain.
""",
    )


def slide_07():
    s = content_slide(
        "Two relations link inscriptions: a sequence, or mutual influence",
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
        100,
        """
Inscriptions placed in the process need relations between them. The model has two – precedes and concomitates.

"precedes" marks a temporal order that the evidence supports: A was started before B. It says nothing about the end – overlap is allowed, because Webern often went back to an earlier sketch while working on a later one. The relation is transitive. (Cf. CIDOC CRM's P176 "starts before the start of")

"concomitates" is a different kind of statement. A and B were written alongside each other, and each shaped the other: a change in one is taken up in the other. Which came first cannot be decided – so the relation records the influence instead of marking an order. It implies overlap in time; it is symmetric, and not transitive. (Cf. CIDOC CRM's P174 "starts before the end of")

For precedes, the model can also record the kind of evidence. precedesScripture rests on the writing: position on the page, overlay, writing instruments, layers of correction. precedesContent rests on the musical content: the later inscription takes over changes made in the earlier one. In op. 25, the editors assert precedesScripture between Sketches 1 and 2 of M 317 – you will see it on the page – and precedesContent between Sketches 2 and 3. Plain precedes leaves the evidence open.
""",
        alt="""
Two timeline panels. Left, "precedes": bar A starts before bar B, the bars overlap; red dashed lines mark the two starts. Right, "concomitates": bar A lies within bar B, a red frame marks the overlap and a vertical red double arrow between the bars, labelled "mutual influence", shows that each shapes the other. Captions: precedes – an order can be shown, A begins before B, overlap allowed; concomitates – A and B influence each other, which came first cannot be decided. CRM analogies: P176, and P174 (the overlap, not the influence). Below, two labels: precedesScripture (page, overlay, writing instruments) and precedesContent (musical content).
""",
    )


# Facsimile of sketchbook 3, fol. 38v with the editors' sketch boxes, from the
# talk #AGE2020DLA (slide 3): raster embedded in its Google Slides SVG export,
# taken in its own proportions (the slide had stretched it).
M317_FACSIMILE = "m317-38v-facsimile.png"
FACSIMILE_LEGEND = (
    "Sketchbook 3, fol. 38v: sketches for op. 25/1 (M 317); markings by the AWG"
)
FACSIMILE_COPYRIGHT = "© Paul Sacher Stiftung, Basel, Sammlung Anton Webern"


LAYOUT_FULL_PICTURE = prs.slide_layouts[9]  # Bild (Vollfläche), Vorlage p. 7
SLIDE_W, SLIDE_H = 33.867, 19.05


def slide_07_page():
    # Vorlage p. 7 (full-picture layout): the facsimile over the full height,
    # centred (it is narrower than the slide, 1.3 : 1). No title or points:
    # only the legend band (bottom left, from the slide edge) and the
    # copyright, set vertically along the image's right edge.
    s = prs.slides.add_slide(LAYOUT_FULL_PICTURE)
    remove_ph(s, "pic")
    from PIL import Image

    with Image.open(os.path.join(HERE, "img", M317_FACSIMILE)) as im:
        iw_px, ih_px = im.size
    fh = SLIDE_H
    fw = fh * iw_px / ih_px
    fx, fy = (SLIDE_W - fw) / 2, 0.0
    pic = s.shapes.add_picture(
        os.path.join(HERE, "img", M317_FACSIMILE), Cm(fx), Cm(fy), Cm(fw), Cm(fh)
    )
    pic.name = "Facsimile: sketchbook 3, fol. 38v"
    pic._element.nvPicPr.cNvPr.set(
        "descr",
        "Facsimile of Webern's sketchbook 3, folio 38 verso, sixteen systems, with the "
        "sketches for M 317 boxed and labelled: Sk1 to Sk4.1; dotted boxes mark the "
        "paratexts: page number, dating, title, instrument indications",
    )

    # systems 1-3 (shown on the next slide); pixels of the facsimile
    def px(u, v):
        return fx + u / iw_px * fw, fy + v / ih_px * fh

    x0, y0 = px(150, 100)
    x1, y1 = px(1305, 262)
    rect(
        s,
        x0,
        y0,
        x1 - x0,
        y1 - y0,
        "Mark: systems 1-3 (next slide)",
        line=T_RED,
        line_pt=2.0,
        dash=True,
    )

    # legend band (Vorlage p. 7: main colour, bottom left, from the slide edge);
    # floating at about the height of system 15 (user's wish: not glued to the
    # bottom edge), nearly opaque so that it stays legible over the facsimile
    bw, by = 22.4, 16.1
    lb = rect(s, 0.0, by, bw, 0.94, "Band: legend", fill=T_MINT)
    set_alpha(lb._element.spPr, 90)
    add_text(
        s,
        0.93,
        by,
        bw - 1.3,
        0.94,
        [("body", FACSIMILE_LEGEND)],
        "Legend",
        anchor=MSO_ANCHOR.MIDDLE,
    )
    # copyright, vertical along the right edge of the image, reading upwards
    cl, ch = 12.0, 0.45
    cx, cy = fx + fw + 0.25 + ch / 2, SLIDE_H - 0.6 - cl / 2
    cr = add_text(
        s,
        cx - cl / 2,
        cy - ch / 2,
        cl,
        ch,
        [("source", FACSIMILE_COPYRIGHT)],
        "Copyright",
    )
    cr.rotation = 270
    notes(
        s,
        "Overview: fol. 38v",
        60,
        """
So much for the model – now to Webern’s sketches. This is folio 38 verso of his third sketchbook, with the first sketches for "Wie bin ich froh!" M 317, the first song of op. 25. The boxes and numbers are ours: the AWG distinguishes fifteen sketches on this one page.

They do not follow the reading order. And the page holds more than musical content, namely the paratexts, dotted here – a title, a dating, a page number. One layer of the paratexts even belongs to another work: at the top, Webern had prepared the systems for the Concerto for Nine Instruments, op. 24 – and then sketched op. 25 into them.

Let's dive into the top three systems [red dashed frame].
""",
        alt="""
Full-picture slide. In the centre, over the full height, the facsimile of sketchbook 3, folio 38 verso, sixteen systems, with boxes and labels for the sketches Sk1 to Sk4.1 and dotted boxes for the paratexts; a red dashed frame marks systems 1 to 3. In a mint band at the bottom left: sketchbook 3, fol. 38v, sketches for op. 25/1 (M 317), markings by the AWG. Vertically along the right edge of the image: © Paul Sacher Stiftung, Basel, Sammlung Anton Webern.
""",
    )


# M 317, source op. 25:A, fol. 38v, systems 1-3: Sk2, Sk1 and Sk2.1 superimposed.
# Rendered once by make_m317_excerpt.py; crop box in SVG units of the sheets.
M317_EXCERPT = "m317-38v-sk1-sk2-sk2_1.png"
M317_CROP = (138, 160, 1008, 305)


def slide_07_example():
    s = content_slide(
        "On one sketchbook page, both relations are at work",
        "Example: M 317, fol. 38v",
        watermark=False,
    )
    ix, iy, iw = 0.93, 6.25, 32.0
    cx0, cy0, cx1, cy1 = M317_CROP
    ih = iw * (cy1 - cy0) / (cx1 - cx0)

    def sx(u):  # SVG x -> slide cm
        return ix + (u - cx0) / (cx1 - cx0) * iw

    def sy(v):
        return iy + (v - cy0) / (cy1 - cy0) * ih

    pic = s.shapes.add_picture(
        os.path.join(HERE, "img", M317_EXCERPT), Cm(ix), Cm(iy), Cm(iw), Cm(ih)
    )
    pic.name = "Excerpt: M 317 Sk2, Sk1, Sk2.1"
    pic._element.nvPicPr.cNvPr.set(
        "descr",
        "Diplomatic transcription of M 317, sketchbook folio 38v, systems 1 to 3: "
        "on system 1 from left to right Sk2 (two twelve-tone rows), Sk1 (four-note figure) "
        "and Sk2.1 (melody with text 'Wie bin ich froh!'), continued on systems 2 and 3",
    )

    # brackets over the three sketches (system 1), labels on top
    by, bh, bw = 4.6, 0.8, 2.0
    regions = [  # (label, SVG x from, to)
        ("Sk2", 172, 412),
        ("Sk1", 418, 588),  # deletion bracket moved to x = 586 (make_m317_excerpt.py)
        ("Sk2.1", 602, 1005),
    ]
    centers = {}
    for lbl, u0, u1 in regions:
        x0, x1 = sx(u0), sx(u1)
        c = (x0 + x1) / 2
        centers[lbl] = c
        labelled_box(s, c - bw / 2, by, bw, bh, lbl, f"Sketch {lbl}", fill=T_MINT)
        line(s, x0, 5.85, x1, 5.85, f"Bracket: {lbl}", color=T_MINT, pt=1.25)
        for xx in (x0, x1):
            line(s, xx, 5.85, xx, 6.1, f"Bracket end: {lbl}", color=T_MINT, pt=1.25)
        line(s, c, by + bh, c, 5.85, f"Bracket stem: {lbl}", color=T_MINT, pt=1.25)

    # Sk1 -> Sk2: the order runs from right to left on the page
    line(
        s,
        centers["Sk1"] - bw / 2 - 0.1,
        by + bh / 2,
        centers["Sk2"] + bw / 2 + 0.1,
        by + bh / 2,
        "Edge: Sk1 precedesScripture Sk2",
        head=True,
    )
    add_text(
        s,
        centers["Sk2"] + bw / 2,
        by - 0.3,
        centers["Sk1"] - centers["Sk2"] - bw,
        0.5,
        [("code_caption", "precedesScripture")],
        "Label: precedesScripture",
        align=PP_ALIGN.CENTER,
    )

    # red mark: the crowded right end of Sk2
    rect(
        s,
        sx(343),
        sy(186),
        sx(416.5) - sx(343),
        sy(217) - sy(186),
        "Mark: crowded end of Sk2",
        line=T_RED,
        line_pt=2.25,
    )
    # green marks: g gives way to f sharp in both (Sk2 row B, 4th tone: f sharp
    # overwrites g, tkk sk2-003; Sk2.1 bar 2: g struck out, tkk sk2_1-003)
    for name, (u0, v0, u1, v1) in (
        ("Sk2, row B: f sharp overwrites g", (308.5, 186, 331, 207)),
        ("Sk2.1, bar 2: g struck out, then f sharp", (686, 188, 736, 213)),
    ):
        rect(
            s,
            sx(u0),
            sy(v0),
            sx(u1) - sx(u0),
            sy(v1) - sy(v0),
            f"Mark: {name}",
            line=T_DARKGREEN,
            line_pt=2.25,
        )

    # Sk2 -- Sk2.1 below the excerpt: concomitates
    ly = iy + ih + 0.55
    for lbl in ("Sk2", "Sk2.1"):
        line(
            s,
            centers[lbl],
            iy + ih + 0.15,
            centers[lbl],
            ly,
            f"Edge stem: {lbl}",
            dash=True,
        )
    line(
        s,
        centers["Sk2"],
        ly,
        centers["Sk2.1"],
        ly,
        "Edge: Sk2.1 concomitates Sk2",
        dash=True,
    )
    add_text(
        s,
        centers["Sk2"],
        ly + 0.1,
        centers["Sk2.1"] - centers["Sk2"],
        0.5,
        [("code_caption", "concomitates")],
        "Label: concomitates",
        align=PP_ALIGN.CENTER,
    )

    ty = 13.15
    for i, (a, rel, b, text) in enumerate(
        [
            (
                "Sk1 ",
                "precedesScripture",
                " Sk2",
                "The right end of Sk2 is squeezed together (red): "
                "Sk1 already took the space. An order inferred from the writing.",
            ),
            (
                "Sk2.1 ",
                "concomitates",
                " Sk2",
                "In both, g gives way to f♯ (green): Sk2.1 and row B of Sk2 "
                "shape each other. Which came first cannot be decided.",
            ),
        ]
    ):
        x = 0.93 + i * 16.4
        add_text(
            s,
            x,
            ty,
            15.6,
            3.0,
            [[("sub", a), ("sub_code", rel), ("sub", b)], ("body", text)],
            f"Evidence: {rel}",
            space_after=4,
        )
    add_text(
        s,
        0.93,
        16.45,
        32.0,
        0.6,
        [
            (
                "caption",
                "Source: AWG online edition, M 317 Sk2, Sk1, Sk2.1, source op. 25:A, fol. 38v, "
                "systems 1–3, superimposed (development version, 12 Nov 2026)",
            )
        ],
        "Source line",
    )
    notes(
        s,
        "Example: M 317",
        140,
        """
Here are the top three systems in the AWG's diplomatic transcription. Normally, the edition gives each sketch on its own sheet; here I have put three of them back on one page together.

[Point to Sk1.] In the middle, Sk1: a four-note figure, the opening of the voice part, in a first draft, deleted by a hook.

[Point to Sk2.] To its left, Sk2: a twelve-tone row, in two attempts. The first, row A, breaks off after five notes; another hook marks it as deleted. Row B completes the row. Why does Sk1 come first, although it stands to the right? Look at the right end of Sk2 [red mark]: the writing is squeezed together. Sk2 ran into the space that Sk1 already occupied. That is, in our terminology, precedesScripture: an order from the writing.

[Point to Sk2.1.] On the right, Sk2.1 turns the row of Sk2, in the rhythm of Sk1, into a melody with text. The commentary says that row B of Sk2 was written "in dynamic alignment" with Sk2.1 and its variants. You can see it in one note [green marks]: in bar 2 of Sk2.1, Webern brackets the g – a sign for its deletion – and goes on with f sharp; in row B, he writes f sharp over the g – the grey note is the overwritten one. The same decision, in both places. Each shaped the other; it cannot be decided which came first. In the model, that is concomitates.

So one page holds both: an order inferred from the writing, and an exchange that no order captures. Even the dating, 4 July 1934, is modelled this way: it concomitates with Sk1 and with Sk2, because the editors cannot say with which of the two it was written.
""",
        alt="""
The diplomatic transcription of M 317, folio 38v, systems 1 to 3, across the slide. Labels above system 1 mark three sketches from left to right: Sk2, Sk1, Sk2.1. An arrow labelled precedesScripture points from Sk1 to Sk2, that is, from right to left. A red rectangle marks the crowded right end of Sk2. Two green rectangles mark where g gives way to f sharp: in row B of Sk2 (f sharp written over a grey g) and in bar 2 of Sk2.1 (g struck out, followed by f sharp). Below the excerpt, a dashed line labelled concomitates connects Sk2.1 and Sk2. Two text blocks: Sk1 precedesScripture Sk2 – the right end of Sk2 is squeezed together, Sk1 already took the space, an order inferred from the writing; Sk2.1 concomitates Sk2 – in both, g gives way to f sharp (green), Sk2.1 and row B of Sk2 shape each other, which came first cannot be decided.
""",
    )


def slide_09():
    s = content_slide(
        "The model could transfer; the pipeline cannot",
        "What transfers",
        watermark=False,
    )
    y0, cw, gap, ih, ig = 4.4, 15.6, 0.8, 1.15, 0.3
    columns = [
        (
            "portable",
            0.0,
            [
                ("code", "Inscription", "what is written and ordered"),
                ("code", "Document", "the physical object"),
                ("code", "Folio", "one leaf (recto and verso)"),
                ("code", "Placement", "where on recto or verso: staves, measures"),
                ("code", "precedes", "temporal sequence, overlap allowed"),
                ("code", "concomitates", "mutual influence, no order"),
            ],
        ),
        (
            "tied to the AWG",
            0.6,
            [
                ("bold", "the pipeline", "the generator reads the AWG's own data"),
                ("bold", "the Moldenhauer catalogue", "M numbers name the complexes"),
                (
                    "bold",
                    "the numbering conventions",
                    "Sk1 before Sk2 is read as precedes, without evidence type",
                ),
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
        90,
        """
What of this would transfer to other editions? Domain-specific does not mean Webern-specific. I would separate two things.

Ideally, the core is portable. Inscription, Document, Folio and Placement describe what is written where: on which object, which leaf and which side, which staves and measures. Placement is a node of its own, so that one sketch can run across several pages and keep its place on each. And the two relations link inscriptions – with branches and parallels, not one sequence. Editions of sketches and drafts will likely come back to these distinctions in one way or another.

Tied to the AWG is the pipeline. The generator reads the edition’s own data: source descriptions, sheet IDs, and M numbers from Moldenhauer’s work catalogue. And it reads numbering as process: Sketch 1 precedes Sketch 2, Sketch 2.1 concomitates with Sketch 2. That is often right – but it remains our convention, and a claim without explicitly modelled evidence type. Relations across complexes come only from curation.

So, as the bottom line says: transfer is plausible, but untested. I would be very interested to hear whether these classes fit the material you work on.
""",
        alt="""
Two columns. Left, "portable": Inscription, Document, Folio, Placement, precedes and concomitates, each with a short gloss. Right, "tied to the AWG": the pipeline, the Moldenhauer catalogue, and the numbering conventions – Sk1 before Sk2 is read as precedes, without evidence type. Bottom line: transfer to other repertoires is plausible but untested.
""",
    )


# Curated statements of the op. 25 graph around the first sketches of M 317.
# node: (centre x, centre y in cm, label, kind)
EXPLORE_NODES = {
    "date": (4.55, 4.85, "4. VII. 34", "para"),
    "Sk1": (2.5, 6.6, "Sk1", "main"),
    "Sk2": (6.6, 6.6, "Sk2", "main"),
    "Sk3": (10.7, 6.6, "Sk3", "main"),
    "Sk4": (14.4, 6.6, "Sk4", "main"),
    "M321": (18.0, 6.6, "M 321 Sk1", "main"),
    "Sk3.1": (13.6, 9.2, "Sk3.1", "sub"),
    "Sk2.1": (6.6, 9.2, "Sk2.1", "sub"),
    "Sk2.1.1": (2.5, 11.8, "Sk2.1.1", "sub"),
    "Sk2.1.2": (6.6, 11.8, "Sk2.1.2", "sub"),
    "Sk2.1.3": (10.7, 11.8, "Sk2.1.3", "sub"),
    "Sk2.1.2.1": (6.6, 14.2, "Sk2.1.2.1", "sub"),
}
NODE_W, NODE_H = 2.7, 0.8
EXPLORE_EDGES = [  # (from, to, kind): arrow = precedes (or subproperty), dash = concomitates
    ("Sk1", "Sk2", "arrow"),
    ("Sk2", "Sk3", "arrow"),
    ("Sk3", "Sk4", "arrow"),
    ("Sk4", "M321", "arrow"),
    ("date", "Sk1", "dash"),
    ("date", "Sk2", "dash"),
    ("Sk2.1", "Sk2", "dash"),
    ("Sk3.1", "Sk3", "dash"),
    ("Sk2.1.1", "Sk2.1", "dash"),
    ("Sk2.1.2", "Sk2.1", "dash"),
    ("Sk2.1.3", "Sk2.1", "dash"),
    ("Sk2.1.2.1", "Sk2.1.2", "dash"),
    ("Sk2.1.1", "Sk2.1.2", "red_arrow"),  # "presumably" in the commentary, no tag
    ("Sk1", "Sk2.1", "missing"),  # in the commentary, not in the graph
]


def node_w(kind):
    return 3.6 if kind == "para" else NODE_W


def border_point(cx, cy, tx, ty, w=NODE_W, gap=0.1):
    """Where the line from a node centre towards (tx, ty) leaves the node box."""
    dx, dy = tx - cx, ty - cy
    hw, hh = w / 2 + gap, NODE_H / 2 + gap
    k = min(hw / abs(dx) if dx else 1e9, hh / abs(dy) if dy else 1e9)
    return cx + dx * k, cy + dy * k


def slide_09_explore():
    s = content_slide(
        "The graph shows patterns the commentary spreads out – and gaps it hides",
        "Exploring the graph: M 317",
        watermark=False,
    )
    # cluster: Sk2.1 with its variants
    cl = rect(
        s,
        1.0,
        8.45,
        11.2,
        6.45,
        "Cluster: Sk2.1 and its variants",
        fill=T_MINT,
        shape=MSO_SHAPE.ROUNDED_RECTANGLE,
    )
    set_alpha(cl._element.spPr, 30)
    add_text(
        s,
        8.0,
        13.75,
        4.0,
        1.0,
        [("caption", "one work phase,"), ("caption", "five entries")],
        "Caption: cluster",
        align=PP_ALIGN.RIGHT,
    )

    pos = {k: (x, y, node_w(kind)) for k, (x, y, _, kind) in EXPLORE_NODES.items()}
    for a, b, kind in EXPLORE_EDGES:
        (xa, ya, wa), (xb, yb, wb) = pos[a], pos[b]
        x1, y1 = border_point(xa, ya, xb, yb, wa)
        x2, y2 = border_point(xb, yb, xa, ya, wb)
        if kind == "missing":
            c = line(s, x1, y1, x2, y2, f"Missing edge: {a} – {b}", color=T_RED, pt=2.0)
            c.line.dash_style = MSO_LINE.ROUND_DOT
            add_text(
                s,
                (x1 + x2) / 2 - 1.0,
                (y1 + y2) / 2 - 0.35,
                0.6,
                0.6,
                [("red_caption", "?")],
                "Label: missing edge",
            )
        elif kind == "red_arrow":
            line(
                s,
                x1,
                y1,
                x2,
                y2,
                f"Edge: {a} precedes {b}",
                color=T_RED,
                pt=2.0,
                head=True,
            )
        else:
            line(
                s,
                x1,
                y1,
                x2,
                y2,
                f"Edge: {a} – {b}",
                head=kind == "arrow",
                dash=kind == "dash",
            )
    for key, (x, y, label, kind) in EXPLORE_NODES.items():
        kw = {
            "main": dict(fill=T_MINT),
            "sub": dict(fill=T_MINT, brightness=0.6),
            "para": dict(line=T_DARKGREEN, line_pt=1.0, dash=True),
        }[kind]
        labelled_box(
            s,
            x - node_w(kind) / 2,
            y - NODE_H / 2,
            node_w(kind),
            NODE_H,
            label,
            f"Node {key}",
            style="code_caption",
            **kw,
        )
    add_text(
        s,
        1.2,
        12.4,
        3.9,
        1.0,
        [("red_caption", "“presumably”,"), ("red_caption", "no tag")],
        "Label: untagged statement",
    )

    # legend
    lg_y = 15.35
    items = [
        ("precedes", dict(head=True), None),
        ("concomitates", dict(dash=True), None),
        (
            "in the commentary, not in the graph",
            dict(color=T_RED, pt=2.0),
            MSO_LINE.ROUND_DOT,
        ),
    ]
    x = 1.0
    for text, kw, dash_style in items:
        c = line(s, x, lg_y + 0.25, x + 1.2, lg_y + 0.25, f"Legend: {text}", **kw)
        if dash_style is not None:
            c.line.dash_style = dash_style
        w = 0.25 * len(text) + 0.4
        add_text(s, x + 1.4, lg_y, w, 0.5, [("caption", text)], f"Legend text: {text}")
        x += 1.4 + w + 0.5

    # right panel (Vorlage p. 3: light panel with arrow list)
    px, py, pw, ph = 20.6, 4.4, 12.33, 11.75
    panel = rect(s, px, py, pw, ph, "Panel: what the graph shows", fill=T_MINT)
    set_alpha(panel._element.spPr, 50)
    points = [
        (
            "Clusters",
            "Sk2.1 and its variants: one work phase at a glance.",
        ),
        (
            "Paths",
            "From Sk1 to Sk4 and on into M 321: the work leaves the song.",
        ),
        (
            "Gaps",
            "Sk2.1 builds on Sk1, but no edge says so. A “presumably” has no tag.",
        ),
    ]
    paras = []
    for head, text in points:
        paras += [("sub", f"→ {head}"), ("body", text)]
    add_text(s, px + 0.7, py + 0.7, pw - 1.4, 8.0, paras, "Points", space_after=6)
    add_text(
        s,
        px + 0.7,
        py + ph - 2.1,
        pw - 1.4,
        1.6,
        [
            (
                "bold",
                "The graph does not discover. It makes commentary and data comparable.",
            )
        ],
        "Point: conclusion",
        anchor=MSO_ANCHOR.BOTTOM,
    )
    add_text(
        s,
        0.93,
        16.45,
        32.0,
        0.6,
        [
            (
                "caption",
                "Selection from the curated layer of the op. 25 graph (M 317), "
                "drawn from the data (development version, 12 Nov 2026)",
            )
        ],
        "Source line",
    )
    notes(
        s,
        "Exploring the graph: M 317",
        110,
        """
What does the graph add to the critical commentary? Not new facts – everything here was asserted by the editors. But it shows them differently. Three things, back on the first sketches of M 317.

Clusters. Sk2.1 and its variants all concomitate – with Sk2.1, and through it with Sk2. In the commentary, that is five separate entries, each saying "in dynamic alignment with". In the graph it is one cluster [point to the shaded area]: a compositional work phase at a glance.

Paths. The precedes chain runs from Sk1 through Sk4 – and on into M 321, the third song, as in the graph of op. 25. You follow a path instead of reassembling it from page references.

Gaps. Here the graph and the commentary disagree. The commentary says – as we just saw – that Sk2.1 builds on the rhythm of Sk1 – but there is no edge between them yet [red dotted line]; Sk2.1 hangs on Sk1 only by way of Sk2. And Sk2.1.2 is "presumably" the continuation of Sk2.1.1 – but the statement carries no uncertainty tag, so it counts as certain. Reading entry by entry, you see neither. In the graph, a missing relation is visible, and untagged statements can be listed and checked against the commentary.

So the graph does not discover anything by itself. It makes commentary and data comparable – which brings us to the frictions.
""",
        alt="""
Left, a graph of the first sketches of M 317 drawn from the curated data. Top row, linked by precedes arrows: Sk1, Sk2, Sk3, Sk4, M 321 Sk1. Above Sk1 and Sk2, the dating "4. VII. 34", linked to both by dashed lines. Below Sk2, a shaded cluster: Sk2.1 with its variants Sk2.1.1, Sk2.1.2, Sk2.1.3 and Sk2.1.2.1, linked by dashed concomitates lines; caption "one work phase, five entries". Below Sk3, Sk3.1, dashed. In red: an arrow from Sk2.1.1 to Sk2.1.2, labelled "presumably, no tag", and a dotted line with a question mark from Sk1 to Sk2.1, marked in the legend as "in the commentary, not in the graph". Right, a light panel with three points: Clusters – Sk2.1 and its variants, one work phase at a glance; Paths – from Sk1 to Sk4 and on into M 321, the work leaves the song; Gaps – Sk2.1 builds on Sk1, but no edge says so, a "presumably" has no tag. At the bottom of the panel: The graph does not discover. It makes commentary and data comparable.
""",
    )


def slide_10():
    s = content_slide(
        "Where model and data diverge, each gap is information",
        "Frictions: model vs. data",
        watermark=False,
    )
    y0, cw, ih, ig = 4.4, 14.2, 1.9, 0.3
    columns = [
        (
            "model lags data",
            0.93,
            [
                ("staves", "own notation: “1c–3c”", None),
                ("measures", "own notation: “{1A}, {1B}, 1–2, 3A”", None),
                ("writing instruments", "missing: pencil, ink, crayon", None),
            ],
        ),
        (
            "data lags model",
            32.93 - cw,
            [
                ("sketchbooks", "per complex: sketchbook 3 as two excerpts", None),
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
        [("sub", "Some gaps are ours to close; others belong to the evidence.")],
        "Bottom line",
        anchor=MSO_ANCHOR.MIDDLE,
    )
    notes(
        s,
        "Frictions: model vs. data",
        135,
        """
These frictions are of another kind than the gaps we just saw: not between commentary and graph, but between model and data. They run in two directions [point to the two columns].

Where the model lags behind the data, claims stay in prose. The source descriptions record on which staves a sketch stands and which measures it covers – but in their own notation: “1c to 3c”, or labels like 1A and 1B for discarded attempts. The graph carries these as strings, so a query cannot see them; to change that, the model needs terms for parts of a staff and for discarded measures. Writing instruments – pencil, ink, crayon – are not in the model yet either, although precedesScripture rests on them. These gaps we can and will close.

Where the data lag behind the model, the decision lies with the editors, not with the model. Sketchbook 3 is described twice, as two excerpts, because each complex describes only its own pages. That needs alignment in the data at some point. 29 sketches are still placeholders, “Sk##”: their number awaits an editorial decision. And some datings have no year – “M. am 30. IX.“. Webern left it open. The model keeps the paratext as it stands, and the year would come in as the editors’ own claim – tagged as uncertain, not stored as fact.

The generator reports such cases instead of closing them silently: twelve warning rules, placeholder and incompleteDate among them.

So each gap is information – about the model, or about the evidence. A string shows where the model still lacks terms; a placeholder, where a decision is pending; a warning, where the graph refuses to claim more than the evidence allows.
""",
        alt="""
Two columns joined by a double arrow. Left, "model lags data": staves and measures in their own notation, stored as strings, writing instruments missing. Right, "data lags model": sketchbooks described per complex, Sk## placeholders (warning: placeholder), incomplete dates (warning: incompleteDate). Bottom line: some gaps are ours to close; others belong to the evidence.
""",
    )


def slide_11():
    s = content_slide(
        "For now, the model is domain-specific, with links to standards",
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
            "single terms: parts, concept schemes, attribution, statements",
            "used directly",
        ),
        ("MEI", "not integrated yet 😢", "–"),
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
                (
                    "band_bold",
                    "Relating sketches draws on content and page together",
                ),
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
        75,
        """
How does this relate to standards? For now, the model is domain-specific: built for Webern’s sources and the AWG’s needs. Where existing models offer related concepts, we point to them – LRMoo for work, expression and item, CIDOC CRM for the temporal reading of the two relations you just saw. The connections to those standards are links, rdfs:seeAlso, not subclasses: a subclass would commit us to all the semantics the standard implies which do not always fit. Where single terms fit exactly, we use them directly: from Dublin Core for parts and wholes, from SKOS for concept schemes, from PROV for attribution. MEI is not integrated yet.

One example shows why we keep the distance for now. LRMoo separates content and object, the expression and the item that carries it. For a sketch, that cut runs right through the argument: relating sketches draws on what they contain and on how they stand on the page – both at once, as you will see shortly.
""",
        alt="""
At the top, in a dark teal band: relating sketches draws on content and page together, which LRMoo separates (F2 Expression vs. F5 Item). Below, a table with three columns – standard, in the AWG model, link. LRMoo: edition complex about F1 Work, version and sketch about F2 Expression, document about F5 Item (rdfs:seeAlso). CIDOC CRM: temporal reading, precedes about P176, concomitates about P174 (rdfs:seeAlso). Dublin Core terms, SKOS, PROV, rdf:Statement: single terms (used directly). MEI: not integrated.
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
        [("statement", "Layers show where editorial judgment becomes explicit.")],
        [("statement", "Warnings show where the data are open or disagree.")],
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
        115,
        """
Back to the opening question: can the graph keep open what cannot be decided, and yet hold it in a formal model? Partly. The model has means for openness: concomitates instead of an invented order, plain precedes where the evidence is not specified, an uncertainty tag on a statement. Where it has none yet, openness survives as strings and gaps – readable, but not queryable. And where the generator reads numbering as process, it closes more than the editors claimed. Three conclusions follow.

First: layers show where editorial judgment becomes explicit. The generated layer already rests on editorial decisions – the numbering, the source descriptions – but leaves them implicit; the curated layer states what editors assert. In op. 25, the difference is the chain across the songs: the editors' argument, made visible.

Second: warnings show where the data are open or disagree. The generator reports instead of silently repairing.

Third: model and data are written side by side – concomitant, in the sense of our own relation. The model was revised wherever the data resisted, and the data will be revised wherever the model shows gaps. In that sense, “compositional processes as graph“ also means: the graph itself is in process.

Next steps: the editorial statements will move into named graphs, so that, for example, the ink and pencil layers of a sketch can be kept apart – one of the gaps we saw. And persons and archives, so far only open questions, will become part of the model.
""",
        alt="""
Left, a pale teal detail of the op. 25 graph with node labels. Right, a mint panel with three conclusions: layers show where editorial judgment becomes explicit; warnings show where the data are open or disagree; model and data are written side by side – concomitant. Below: next steps, named graphs for ink and pencil layers, persons, archives.
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
        [
            (
                "closing_light",
                "Whose process does the graph show – Webern's or ours?"  # break after the dash,
            )
        ],
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
                "How much of (Webern's) compositional processes survives translation "
                "into formal models?",
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

If model and data shape each other – if they are, in our own term, concomitant – then the graph does not simply reflect Webern's compositional processes, read off the documents. It is also our construction: our numbering, our evidence types, our decisions about what counts as a relation. So: whose process does the graph show – Webern's, or ours?

The second question looks outward. Every formal model is a kind of translation. We have seen it in this talk: editorial terms into classes, observations into edges etc. Each step keeps something, and loses something. So: how much of (Webern’s) compositional processes survives translation into formal models?

I look forward to your answers – and to your material. Thank you.

[Stage: stay on this slide during the discussion; go to the next slide (contact) only at the very end.]
""",
        alt="""
Behind the slide, a pale image of another region of the full op. 25 graph. In a dark teal band, in white: whose process does the graph show – Webern's or ours? Below, smaller: how much of (Webern's) compositional processes survives translation into formal models?
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
[Stage: show only after the discussion, or when the chair closes the session; no spoken text. The closing question (previous slide) stays up during the Q&A.]
""",
    )


SECTIONS = (
    ["Introduction"] * 7
    + ["Terminology"] * 3
    + ["Beyond the AWG"] * 2
    + ["The model at work"] * 5
    + ["Conclusion"] * 3
)

for build_slide in (
    slide_01,
    slide_02,
    slide_02_editions,
    slide_03,
    slide_04_generated,
    slide_04_curated,
    slide_04_both,
    slide_05,
    slide_06,
    slide_07,
    slide_11,
    slide_09,
    slide_07_page,
    slide_07_example,
    slide_09_m307,
    slide_09_explore,
    slide_10,
    slide_12,
    slide_13,
    slide_14,
):
    build_slide()
assert ELAPSED[0] == TOTAL, ELAPSED[0]

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
if os.path.exists(SOFFICE):
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
else:  # no LibreOffice: export with PowerPoint (Windows, COM)
    src = os.path.abspath(OUT).replace("'", "''")
    dst = os.path.join(work, os.path.basename(PDF)).replace("'", "''")
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "$pp = New-Object -ComObject PowerPoint.Application; "
            f"$d = $pp.Presentations.Open('{src}', $true, $false, $false); "
            f"$d.SaveAs('{dst}', 32); $d.Close(); $pp.Quit()",
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
    if pdftoppm is not None:
        subprocess.run(
            [pdftoppm, "-jpeg", "-r", str(dpi), pdf, os.path.join(work, "page")],
            check=True,
            timeout=300,
        )
    else:
        try:
            import pymupdf
        except ImportError:
            print("grid skipped: neither pdftoppm nor pymupdf found")
            return
        with pymupdf.open(pdf) as doc:
            for i, page in enumerate(doc):
                page.get_pixmap(dpi=dpi).save(
                    os.path.join(work, f"page-{i + 1:02d}.jpg")
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
