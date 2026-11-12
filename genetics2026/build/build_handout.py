"""Build the two-page handout AWG-Graph-Handout.docx (+ PDF) for the genetics2026 talk.

The handout follows the order of the slides and carries the reference detail
the slides only speak: the forms of edition, terms and classes, relation
properties, standards with link types, what transfers, the M 317 example,
the generator's warning rules and the conclusions.

Styles, footer and numbering come from build/handout-template.docx (the first
handout version); word/document.xml is generated here, and the music example
(build/img/handout-m317-38v.png) is drawn with Pillow from the M 317 excerpt
that build/make_m317_excerpt.py renders for the deck, with the deck's markings.

Inline markup in text: `code` -> Consolas, **bold** -> bold.

PDF: LibreOffice if installed, else Word (Windows, COM). Run from PowerShell;
needs Pillow.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "handout-template.docx")
OUT = os.path.join(os.path.dirname(HERE), "AWG-Graph-Handout.docx")

EMAIL = "stefan.muennich@unibas.ch"
URL = "https://edition.anton-webern.ch"

TEAL = "006E6E"
MINT = "A5D7D2"
GREEN = "1EA5A5"
RED = "D20537"
GREY = "F2F2F2"
WIDTH = 10206  # text width in dxa (A4, 1.5 cm margins)
EMU_PER_DXA = 635


# ------------------------------------------------------------ runs
def rpr(bold=False, mono=False, color=None, size=None, georgia=False, italic=False):
    out = ""
    if mono or georgia:
        f = "Consolas" if mono else "Georgia"
        out += f'<w:rFonts w:ascii="{f}" w:cs="{f}" w:eastAsia="{f}" w:hAnsi="{f}"/>'
    if bold:
        out += "<w:b/><w:bCs/>"
    if italic:
        out += "<w:i/><w:iCs/>"
    if color:
        out += f'<w:color w:val="{color}"/>'
    if size:
        out += f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>'
    return f"<w:rPr>{out}</w:rPr>" if out else ""


def run(text, **kw):
    return f'<w:r>{rpr(**kw)}<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'


def runs(text, size=None, color=None, bold=False):
    """Inline markup: `code` and **bold**."""
    out = []
    for part in re.split(r"(`[^`]+`|\*\*[^*]+\*\*)", text):
        if not part:
            continue
        if part.startswith("`"):
            out.append(run(part[1:-1], mono=True, size=size, color=color, bold=bold))
        elif part.startswith("**"):
            out.append(runs(part[2:-2], size=size, color=color, bold=True))
        else:
            out.append(run(part, size=size, color=color, bold=bold))
    return "".join(out)


# ------------------------------------------------------------ paragraphs
def para(content, after=60, before=None, extra=""):
    sp = f'<w:spacing w:after="{after}"' + (f' w:before="{before}"' if before is not None else "") + "/>"
    return f"<w:p><w:pPr>{extra}{sp}</w:pPr>{content}</w:p>"


def p(text, size=None, after=60, keep=False):
    return para(runs(text, size=size), after=after, extra="<w:keepNext/>" if keep else "")


def bullet(text, size=None):
    return (
        '<w:p><w:pPr><w:pStyle w:val="ListParagraph"/><w:numPr><w:ilvl w:val="0"/>'
        '<w:numId w:val="2"/></w:numPr><w:spacing w:after="40"/></w:pPr>'
        f"{runs(text, size=size)}</w:p>"
    )


def heading(text, new_page=False):
    return para(
        run(text, bold=True, color=TEAL, size=22),
        after=110,
        before=280,
        extra=("<w:keepNext/><w:pageBreakBefore/>" if new_page else "<w:keepNext/>")
        + f'<w:pBdr><w:bottom w:val="single" w:color="{GREEN}" w:sz="6" w:space="1"/></w:pBdr>',
    )


# ------------------------------------------------------------ tables
NOBORDER = (
    '<w:tcBorders><w:top w:val="none" w:color="FFFFFF" w:sz="0"/><w:left w:val="{left}" w:color="{lc}" w:sz="{lsz}"/>'
    '<w:bottom w:val="none" w:color="FFFFFF" w:sz="0"/><w:right w:val="none" w:color="FFFFFF" w:sz="0"/></w:tcBorders>'
)
GRIDBORDER = (
    '<w:tcBorders><w:top w:val="single" w:color="BFBFBF" w:sz="4"/><w:left w:val="single" w:color="BFBFBF" w:sz="4"/>'
    '<w:bottom w:val="single" w:color="BFBFBF" w:sz="4"/><w:right w:val="single" w:color="BFBFBF" w:sz="4"/></w:tcBorders>'
)
PLAIN = NOBORDER.format(left="none", lc="FFFFFF", lsz=0)


def tbl(widths, rows_xml):
    grid = "".join(f'<w:gridCol w:w="{w}"/>' for w in widths)
    return (
        f'<w:tbl><w:tblPr><w:tblW w:type="dxa" w:w="{sum(widths)}"/><w:tblLayout w:type="fixed"/></w:tblPr>'
        f"<w:tblGrid>{grid}</w:tblGrid>{rows_xml}</w:tbl>"
    )


def cell(width, body, borders, fill=None, mar=(70, 110)):
    shd = f'<w:shd w:fill="{fill}" w:color="auto" w:val="clear"/>' if fill else ""
    v, h = mar
    return (
        f'<w:tc><w:tcPr><w:tcW w:type="dxa" w:w="{width}"/>{borders}{shd}'
        f'<w:tcMar><w:top w:type="dxa" w:w="{v}"/><w:left w:type="dxa" w:w="{h}"/>'
        f'<w:bottom w:type="dxa" w:w="{v}"/><w:right w:type="dxa" w:w="{h}"/></w:tcMar></w:tcPr>{body}</w:tc>'
    )


def grid_table(widths, header, rows, keep=True, size=17):
    """Teal header row, grey grid; cells are text with inline markup.
    keep=True keeps the whole table on one page."""
    kn = "<w:keepNext/>" if keep else ""
    head = "".join(
        cell(w, para(run(t, bold=True, color="FFFFFF", size=size), after=0, extra=kn), GRIDBORDER, fill=TEAL)
        for w, t in zip(widths, header)
    )
    out = f"<w:tr><w:trPr><w:tblHeader/></w:trPr>{head}</w:tr>"
    for n, r in enumerate(rows):
        k = kn if n < len(rows) - 1 else ""
        cells = "".join(cell(w, para(runs(t, size=size), after=0, extra=k), GRIDBORDER) for w, t in zip(widths, r))
        out += f"<w:tr><w:trPr><w:cantSplit/></w:trPr>{cells}</w:tr>"
    return tbl(widths, out)


def mint_box(paras_xml):
    """Mint box with a red bar on the left (question, discussion)."""
    b = NOBORDER.format(left="single", lc=RED, lsz=24)
    return tbl([WIDTH], f"<w:tr><w:trPr><w:cantSplit/></w:trPr>{cell(WIDTH, paras_xml, b, fill=MINT, mar=(110, 170))}</w:tr>")


def grey_columns(columns, size=17):
    """Grey side-by-side boxes; each column = (title, [bullets] or text)."""
    w = WIDTH // len(columns)
    cells = ""
    for title, items in columns:
        body = para(runs(title, bold=True, color=TEAL, size=size + 1), after=50)
        if isinstance(items, str):
            body += para(runs(items, size=size), after=0)
        else:
            body += "".join(bullet(i, size=size) for i in items)
        cells += cell(w, body, PLAIN, fill=GREY, mar=(110, 150))
    # keep the box together with the note line below it
    # (schema order: pStyle before keepNext)
    cells = re.sub(r'<w:pPr>(<w:pStyle w:val="[^"]+"/>)?', r"<w:pPr>\1<w:keepNext/>", cells)
    return tbl([w] * len(columns), f"<w:tr><w:trPr><w:cantSplit/></w:trPr>{cells}</w:tr>")


def text_columns(columns, size=17):
    """Plain side-by-side text; each column = (teal title, text), inline markup."""
    w = WIDTH // len(columns)
    cells = ""
    for n, (title, text) in enumerate(columns):
        body = para(runs(title, size=size + 1, color=TEAL, bold=True), after=20) + para(runs(text, size=size), after=0)
        cells += cell(w, body, PLAIN, mar=(40, 0 if n == 0 else 120))
    return tbl([w] * len(columns), f"<w:tr><w:trPr><w:cantSplit/></w:trPr>{cells}</w:tr>")


def note(text, after=0):
    """Small grey line below a block."""
    return para(runs(text, size=15, color="595959"), after=after, before=80)


def chain(items):
    """Boxes joined by red arrows, e.g. the op. 25 chain."""
    box, arrow = 2600, 700
    centre = '<w:jc w:val="center"/><w:keepNext/>'
    cells, widths = "", []
    for n, item in enumerate(items):
        if n:
            cells += cell(arrow, para(run("→", bold=True, color=RED, size=26), after=0, extra=centre), PLAIN, mar=(60, 0))
            widths.append(arrow)
        cells += cell(box, para(run(item, bold=True, color=TEAL, size=18), after=0, extra=centre), PLAIN, fill=MINT, mar=(60, 80))
        widths.append(box)
    return tbl(widths, f"<w:tr>{cells}</w:tr>")


def spacer(after=0):
    return para("", after=after, extra='<w:rPr><w:sz w:val="8"/></w:rPr>')


# ------------------------------------------------------------ images
IMAGES = []  # (rId, media name, source path)


def image(path, descr, width_dxa=WIDTH, keep=True):
    """Inline picture over the text width."""
    with Image.open(path) as im:
        w_px, h_px = im.size
    cx = width_dxa * EMU_PER_DXA
    cy = round(cx * h_px / w_px)
    n = len(IMAGES) + 1
    rid, name = f"rIdImg{n}", f"image{n}.png"
    IMAGES.append((rid, name, path))
    a = "http://schemas.openxmlformats.org/drawingml/2006/main"
    pic = "http://schemas.openxmlformats.org/drawingml/2006/picture"
    drawing = (
        f'<w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0">'
        f'<wp:extent cx="{cx}" cy="{cy}"/><wp:docPr id="{100 + n}" name="{name}" descr="{escape(descr, {chr(34): "&quot;"})}"/>'
        f'<wp:cNvGraphicFramePr><a:graphicFrameLocks xmlns:a="{a}" noChangeAspect="1"/></wp:cNvGraphicFramePr>'
        f'<a:graphic xmlns:a="{a}"><a:graphicData uri="{pic}"><pic:pic xmlns:pic="{pic}">'
        f'<pic:nvPicPr><pic:cNvPr id="{100 + n}" name="{name}"/><pic:cNvPicPr/></pic:nvPicPr>'
        f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
        f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic>'
        f"</wp:inline></w:drawing></w:r>"
    )
    return para(drawing, after=0, before=40, extra="<w:keepNext/>" if keep else "")


# ------------------------------------------------------------ music example
EXCERPT = os.path.join(HERE, "img", "m317-38v-sk1-sk2-sk2_1.png")
FIGURE = os.path.join(HERE, "img", "handout-m317-38v.png")
CROP = (138, 160, 1008, 305)  # SVG units of the excerpt (make_m317_excerpt.py)
DPR = 4  # excerpt pixels per SVG unit
FONTS = r"C:\Windows\Fonts"


def rgb(hex_):
    return tuple(int(hex_[i : i + 2], 16) for i in (0, 2, 4))


def make_figure():
    """The M 317 excerpt with the deck's markings (slide 'Example: M 317')."""
    exc = Image.open(EXCERPT).convert("RGB")
    W, H = exc.size
    TOP, BOTTOM = 262, 150
    img = Image.new("RGB", (W, TOP + H + BOTTOM), "white")
    img.paste(exc, (0, TOP))
    d = ImageDraw.Draw(img)
    mono = ImageFont.truetype(os.path.join(FONTS, "consolab.ttf"), 54)
    mono_s = ImageFont.truetype(os.path.join(FONTS, "consola.ttf"), 50)
    teal, mint, red = rgb(TEAL), rgb(MINT), rgb(RED)

    def X(u):
        return (u - CROP[0]) * DPR

    def Y(v):
        return TOP + (v - CROP[1]) * DPR

    def dashed(x0, y0, x1, y1, width=6, dash=26, gap=16):
        length = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
        pos = 0.0
        while pos < length:
            e = min(pos + dash, length)
            d.line(
                [(x0 + (x1 - x0) * pos / length, y0 + (y1 - y0) * pos / length),
                 (x0 + (x1 - x0) * e / length, y0 + (y1 - y0) * e / length)],
                fill=teal, width=width,
            )
            pos = e + gap

    # brackets with labels over the three sketches
    box_w, box_h, box_y, br_y = 250, 84, 80, 220
    centres = {}
    for lbl, u0, u1 in (("Sk2", 172, 412), ("Sk1", 418, 588), ("Sk2.1", 602, 1005)):
        x0, x1 = X(u0), X(u1)
        c = (x0 + x1) / 2
        centres[lbl] = c
        d.line([(x0, br_y), (x1, br_y)], fill=mint, width=8)
        for xx in (x0, x1):
            d.line([(xx, br_y), (xx, br_y + 34)], fill=mint, width=8)
        d.line([(c, box_y + box_h), (c, br_y)], fill=mint, width=8)
        d.rectangle([c - box_w / 2, box_y, c + box_w / 2, box_y + box_h], fill=mint)
        d.text((c, box_y + box_h / 2), lbl, font=mono, fill=teal, anchor="mm")

    # Sk1 -> Sk2: precedesScripture, right to left on the page
    ay = box_y + box_h / 2
    xa, xb = centres["Sk1"] - box_w / 2 - 14, centres["Sk2"] + box_w / 2 + 14
    d.line([(xa, ay), (xb + 30, ay)], fill=teal, width=7)
    d.polygon([(xb, ay), (xb + 40, ay - 20), (xb + 40, ay + 20)], fill=teal)
    d.text(((xa + xb) / 2, ay - 18), "precedesScripture", font=mono_s, fill=teal, anchor="md")

    # red: the crowded right end of Sk2; teal: g gives way to f sharp
    def mark(u0, v0, u1, v1, colour):
        d.rectangle([X(u0), Y(v0), X(u1), Y(v1)], outline=colour, width=10)

    mark(343, 186, 416.5, 217, red)
    mark(308.5, 186, 331, 207, teal)  # Sk2, row B: f sharp written over g
    mark(686, 188, 736, 213, teal)  # Sk2.1, bar 2: g struck out, then f sharp

    # Sk2.1 -- Sk2: concomitates, below the excerpt
    ly = TOP + H + 55
    for lbl in ("Sk2", "Sk2.1"):
        dashed(centres[lbl], TOP + H + 12, centres[lbl], ly)
    dashed(centres["Sk2"], ly, centres["Sk2.1"], ly)
    d.text(((centres["Sk2"] + centres["Sk2.1"]) / 2, ly + 16), "concomitates", font=mono_s, fill=teal, anchor="mt")

    img.save(FIGURE, optimize=True)
    print("saved", FIGURE, img.size)
    return FIGURE


# ================================================================ content
B = []


def content():
    # --- header
    B.append(para(run("Compositional Processes as Graph", georgia=True, bold=True, color="000000", size=34), after=30))
    B.append(para(run("Semantic Modelling and Terminology in the Anton Webern Gesamtausgabe (AWG)", georgia=True, color="000000", size=22), after=60))
    B.append(para(run("Dr. Stefan Münnich · Anton Webern Gesamtausgabe, University of Basel · ", color="595959", size=16)
                  + run(EMAIL, color=TEAL, size=16) + run(" · ", color="595959", size=16)
                  + run(URL.split("//")[1], color=TEAL, size=16), after=10))
    B.append(para(run("Comparative Perspectives on Genetic Criticism in Music · IMS Study Group · Rome, German Historical Institute, 16–18 November 2026",
                      color="595959", size=16), after=180))

    # --- question
    B.append(mint_box(
        para(runs("**Question.** How can a digital edition represent non-linear compositional processes – and keep philological claims as open as the evidence demands?", size=18), after=60)
        + para(runs("**Answer: partly.** `concomitates`, plain `precedes` and a certainty tag keep claims open. Elsewhere openness survives only as free text – readable, not queryable.", size=18), after=0)
    ))

    # --- 1 the AWG and its graph
    B.append(heading("1  The AWG: three forms of edition, one graph in two layers"))
    B.append(grid_table([3000, 5406, 1800], ["Form of edition", "Presents", "Edits"], [
        ["work edition · Werkedition", "versions published or meant for print", "`TextVersion`"],
        ["text edition · Textedition", "versions beyond a sketch, not printed", "`TextVersion`"],
        ["sketch edition · Skizzenedition", "diplomatic transcriptions of sketches", "`Sketch`"],
    ]))
    B.append(spacer(after=120))
    B.append(grey_columns([
        ("Generated layer", "derived from the edition data"),
        ("Curated layer", "asserted by the editors"),
    ]))
    B.append(note("Draft ontology v0.1 · SPARQL in the app · Turtle export · no reasoning"))

    # --- 2 op. 25
    B.append(heading("2  Op. 25: the sketches cross the opus order"))
    B.append(p("Op. 25 = M 317 (song I) · M 322 (song II) · M 321 (song III). The curated chain:", size=18, keep=True, after=100))
    B.append(chain(["M 317 Sk4", "M 321 Sk1–9", "M 322 Sk1"]))
    B.append(note("Song III was sketched before song II. The generated layer shows three separate “islands”."))

    # --- 3 terms and classes
    B.append(heading("3  Terms from the material become classes"))
    B.append(grid_table([3300, 3500, 3406], ["Term", "In the documents", "Class"], [
        ["sketch · Skizze", "Sk1, Sk2, Sk2.1", "`Sketch` ⊂ `Inscription`"],
        ["row table · Reihentabelle", "Webern’s sheet of row forms", "`RowTable` ⊂ `Sketch`"],
        ["paratext · Paratext", "title, dating, instruments", "`Paratext` ⊂ `Inscription`"],
        ["version · Textfassung", "TF1, TF2", "`TextVersion`"],
        ["edition complex · Editionskomplex", "opus or M number", "`EditionComplex`"],
        ["uncertainty", "“presumably”", "tag `certainty: uncertain`"],
    ]))
    B.append(note("Not modelled yet: “study composition”, “ink draft”."))

    # --- 4 relations
    B.append(heading("4  Two relations carry the genetic order"))
    B.append(grid_table([2600, 4406, 3200], ["Relation", "Meaning", "cf. CIDOC CRM"], [
        ["`precedes`", "A begun before B, overlap allowed", "P176 “starts before the start of”"],
        ["`concomitates`", "A and B shape each other, no order", "P174 “starts before the end of”"],
        ["`precedesScripture`", "evidence: the writing", ""],
        ["`precedesContent`", "evidence: the musical content", ""],
    ]))
    B.append(note("`precedes` is transitive; `concomitates` is symmetric, not transitive."))

    # --- 5 standards
    B.append(heading("5  Standards serve as alignments, not as the model", new_page=True))
    B.append(p("**A sketch’s genetic place rests on content and material traces together** – which LRMoo separates (F2 Expression vs. F5 Item).",
               size=17, keep=True, after=120))
    B.append(grid_table([3000, 5306, 1900], ["Standard", "In the AWG model", "Link"], [
        ["LRMoo", "edition complex ≈ F1 · version, sketch ≈ F2 · document ≈ F5", "`rdfs:seeAlso`"],
        ["CIDOC CRM", "temporal reading: `precedes` ≈ P176 · `concomitates` ≈ P174", "`rdfs:seeAlso`"],
        ["DC terms, SKOS, PROV, `rdf:Statement`", "parts · concept schemes · attribution · statements", "used directly"],
        ["MEI", "not integrated yet", "–"],
    ]))

    # --- 6 what transfers
    B.append(heading("6  The model could transfer; the pipeline cannot"))
    B.append(grey_columns([
        ("Portable", ["`Inscription` · `Document` · `Folio` · `Placement`", "`precedes` · `concomitates`"]),
        ("Tied to the AWG", ["the generator reads the AWG’s own data", "Sk1 before Sk2 is read as `precedes`"]),
    ]))

    # --- 7 music example
    B.append(heading("7  Example: M 317, sketchbook 3, fol. 38v"))
    B.append(image(make_figure(),
                   "Diplomatic transcription of M 317, fol. 38v, systems 1 to 3, with the sketches Sk2, Sk1 and Sk2.1 "
                   "marked from left to right. An arrow labelled precedesScripture points from Sk1 to Sk2, right to left. "
                   "A red box marks the crowded right end of Sk2; two green boxes mark where g gives way to f sharp, in row B "
                   "of Sk2 and in bar 2 of Sk2.1. A dashed line below, labelled concomitates, joins Sk2 and Sk2.1."))
    B.append(spacer(after=60))
    B.append(text_columns([
        ("Sk1 `precedesScripture` Sk2", "The end of Sk2 is squeezed (red): Sk1 was there first."),
        ("Sk2.1 `concomitates` Sk2", "In both, g gives way to f♯ (green): neither comes first."),
    ]))
    B.append(note("Source: AWG online edition, M 317 Sk2, Sk1, Sk2.1, superimposed (development version, 12 Nov 2026)."))

    # --- 8 exploring
    B.append(heading("8  What the graph shows"))
    B.append(grey_columns([
        ("→ Clusters", "Sk2.1 and its variants: one work phase at a glance"),
        ("→ Paths", "Sk1 → Sk4 → M 321: the work leaves the song"),
        ("→ Gaps", "a “presumably” without a tag counts as certain"),
    ]))

    # --- 9 frictions
    B.append(heading("9  Where model and data disagree"))
    B.append(grey_columns([
        ("Model lags data", ["staves, measures as free text", "no writing instruments"]),
        ("Data lags model", ["29 Sk## placeholders", "datings without year"]),
    ]))
    B.append(note("12 generator warnings – each gap is information."))

    # --- 10 conclusion
    B.append(heading("10  Conclusion"))
    B.append(bullet("**Layers** show where editorial judgment becomes explicit.", size=18))
    B.append(bullet("**Warnings** show where the data disagree.", size=18))
    B.append(bullet("**Model and data** are written side by side: concomitant.", size=18))
    B.append(note("Next: named graphs for ink and pencil layers · persons · archives", after=200))
    B.append(mint_box(
        para(runs("**For discussion.** Whose genetic order does the graph show – Webern’s or ours?", size=18), after=60)
        + para(runs("How much of Webern’s compositional process survives translation into formal models?", size=18), after=0)
    ))


# ================================================================ write
def build():
    content()
    with zipfile.ZipFile(TEMPLATE) as z:
        doc = z.read("word/document.xml").decode("utf-8")
        head = doc[: doc.index("<w:body>") + len("<w:body>")]
        sect = doc[doc.index("<w:sectPr"):]
        new_doc = head + "".join(B) + sect
        rels = z.read("word/_rels/document.xml.rels").decode("utf-8")
        img_rels = "".join(
            f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/{name}"/>'
            for rid, name, _ in IMAGES
        )
        rels = rels.replace("</Relationships>", img_rels + "</Relationships>")
        tmp = OUT + ".tmp"
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as out:
            names = [i for i in z.infolist() if not i.filename.endswith("/")]
            names.sort(key=lambda i: i.filename != "[Content_Types].xml")
            for info in names:
                if info.filename == "word/document.xml":
                    data = new_doc.encode("utf-8")
                elif info.filename == "word/_rels/document.xml.rels":
                    data = rels.encode("utf-8")
                else:
                    data = z.read(info)
                out.writestr(info.filename, data)
            for _, name, path in IMAGES:  # png is a Default content type in the template
                out.write(path, f"word/media/{name}")
    try:
        os.replace(tmp, OUT)
    except PermissionError:
        os.remove(tmp)
        sys.exit(f"Handout not updated: {OUT} is locked (open in Word?). Close it and run again.")
    print("saved", OUT)


def pdf():
    target = os.path.splitext(OUT)[0] + ".pdf"
    work = tempfile.mkdtemp(prefix="awg_ho_")
    made = os.path.join(work, os.path.basename(target))
    soffice = shutil.which("soffice") or r"C:\Program Files\LibreOffice\program\soffice.exe"
    if os.path.exists(soffice):
        subprocess.run(
            [soffice, f"-env:UserInstallation=file:///{work.replace(os.sep, '/')}/profile",
             "--headless", "--convert-to", "pdf", "--outdir", work, OUT],
            check=True, timeout=300, capture_output=True,
        )
    else:  # no LibreOffice: export with Word (Windows, COM)
        src = OUT.replace("'", "''")
        dst = made.replace("'", "''")
        subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "$w = New-Object -ComObject Word.Application; $w.Visible = $false; "
             f"$d = $w.Documents.Open('{src}', $false, $true); "
             f"$d.ExportAsFixedFormat('{dst}', 17); $d.Close(0); $w.Quit()"],
            check=True, timeout=300, capture_output=True,
        )
    try:
        shutil.copyfile(made, target)
        print("saved", target)
    except PermissionError:
        sys.exit(f"PDF not updated: {target} is locked (open in a viewer?). Close it and run again.")
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    build()
    pdf()
