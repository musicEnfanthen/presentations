"""Build the two-page handout AWG-Graph-Handout.docx (+ PDF) for the genetics2026 talk.

The handout complements the slides: it carries the reference detail the slides
only speak (op. 25 chain, class list, relation properties, warning rules,
standards with link types). Styles, footer and numbering come from
build/handout-template.docx (the first handout version); only word/document.xml
is generated here, from the same XML fragments as the template.

Inline markup in text: `code` -> Consolas, **bold** -> bold.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "handout-template.docx")
OUT = os.path.join(os.path.dirname(HERE), "AWG-Graph-Handout.docx")

EMAIL = "stefan.muennich@unibas.ch"
URL = "https://edition.anton-webern.ch"

TEAL = "006E6E"
MINT = "A5D7D2"
RED = "D20537"
GREY = "F2F2F2"
WIDTH = 10206  # text width in dxa (A4, 1.5 cm margins)


# ------------------------------------------------------------ runs
def rpr(bold=False, mono=False, color=None, size=None, georgia=False):
    out = ""
    if mono or georgia:
        f = "Consolas" if mono else "Georgia"
        out += f'<w:rFonts w:ascii="{f}" w:cs="{f}" w:eastAsia="{f}" w:hAnsi="{f}"/>'
    if bold:
        out += "<w:b/><w:bCs/>"
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
            out.append(run(part[2:-2], bold=True, size=size, color=color))
        else:
            out.append(run(part, size=size, color=color, bold=bold))
    return "".join(out)


# ------------------------------------------------------------ paragraphs
def para(content, after=60, before=None, extra=""):
    sp = f'<w:spacing w:after="{after}"' + (f' w:before="{before}"' if before is not None else "") + "/>"
    return f"<w:p><w:pPr>{extra}{sp}</w:pPr>{content}</w:p>"


def p(text, size=None, after=60):
    return para(runs(text, size=size), after=after)


def bullet(text, size=None):
    return (
        '<w:p><w:pPr><w:pStyle w:val="ListParagraph"/><w:numPr><w:ilvl w:val="0"/>'
        '<w:numId w:val="2"/></w:numPr><w:spacing w:after="50"/></w:pPr>'
        f"{runs(text, size=size)}</w:p>"
    )


def heading(text, new_page=False):
    return para(
        run(text, bold=True, color=TEAL, size=22),
        after=100,
        before=300,
        extra=("<w:keepNext/><w:pageBreakBefore/>" if new_page else "<w:keepNext/>") + '<w:pBdr><w:bottom w:val="single" w:color="1EA5A5" w:sz="6" w:space="1"/></w:pBdr>',
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


def grid_table(widths, header, rows, keep=False):
    """Teal header row, grey grid; cells are text with inline markup.
    keep=True keeps the whole table on one page."""
    kn = "<w:keepNext/>" if keep else ""
    head = "".join(
        cell(w, para(run(t, bold=True, color="FFFFFF", size=18), after=0, extra=kn), GRIDBORDER, fill=TEAL)
        for w, t in zip(widths, header)
    )
    out = f"<w:tr><w:trPr><w:tblHeader/></w:trPr>{head}</w:tr>"
    for n, r in enumerate(rows):
        k = kn if n < len(rows) - 1 else ""
        cells = "".join(cell(w, para(runs(t, size=18), after=0, extra=k), GRIDBORDER) for w, t in zip(widths, r))
        out += f"<w:tr><w:trPr><w:cantSplit/></w:trPr>{cells}</w:tr>"
    return tbl(widths, out)


def mint_box(paras_xml):
    """Mint box with a red bar on the left (thesis, discussion)."""
    b = NOBORDER.format(left="single", lc=RED, lsz=24)
    return tbl([WIDTH], f"<w:tr>{cell(WIDTH, paras_xml, b, fill=MINT, mar=(120, 180))}</w:tr>")


def grey_columns(columns):
    """Grey side-by-side boxes; each column = (title, [bullets])."""
    w = WIDTH // len(columns)
    b = NOBORDER.format(left="none", lc="FFFFFF", lsz=0)
    cells = ""
    for title, items in columns:
        body = para(run(title, bold=True, color=TEAL, size=19), after=60)
        body += "".join(bullet(i, size=18) for i in items)
        cells += cell(w, body, b, fill=GREY, mar=(100, 140))
    # keep the box together with the note line below it
    # (schema order: pStyle before keepNext)
    cells = re.sub(r'<w:pPr>(<w:pStyle w:val="[^"]+"/>)?', r"<w:pPr>\1<w:keepNext/>", cells)
    return tbl([w] * len(columns), f'<w:tr><w:trPr><w:cantSplit/></w:trPr>{cells}</w:tr>')


def note(text):
    """Small grey line below a block."""
    return para(runs(text, size=16, color="595959"), after=0, before=80)


def chain(items):
    """Boxes joined by red arrows, e.g. the op. 25 chain."""
    box, arrow = 2600, 700
    b = NOBORDER.format(left="none", lc="FFFFFF", lsz=0)
    centre = '<w:jc w:val="center"/>'
    cells, widths = "", []
    for n, item in enumerate(items):
        if n:
            cells += cell(arrow, para(run("→", bold=True, color=RED, size=28), after=0, extra=centre), b, mar=(80, 0))
            widths.append(arrow)
        cells += cell(box, para(run(item, bold=True, color=TEAL, size=20), after=0, extra=centre), b, fill=MINT, mar=(110, 80))
        widths.append(box)
    return tbl(widths, f"<w:tr>{cells}</w:tr>")


def spacer(after=0):
    return para("", after=after, extra='<w:rPr><w:sz w:val="8"/></w:rPr>')


# ================================================================ content
B = []

# --- header
B.append(para(run("Compositional Processes as Graph", georgia=True, bold=True, color="000000", size=34), after=40))
B.append(para(run("Semantic Modelling and Terminology in the Anton Webern Gesamtausgabe (AWG)", georgia=True, color="000000", size=22), after=80))
B.append(para(run("Stefan Münnich · Anton Webern Gesamtausgabe, University of Basel · ", color="595959", size=17)
              + run(EMAIL, color=TEAL, size=17), after=20))
B.append(para(run("IMS Study Group conference, Rome, German Historical Institute, 16–18 November 2026 · ", color="595959", size=17)
              + run(URL.split("//")[1], color=TEAL, size=17), after=200))

# --- question
B.append(mint_box(
    para(runs("**Question.** How can a digital edition represent non-linear compositional processes – and keep philological claims as open as the evidence demands?", size=19), after=60)
    + para(runs("**Answer: partly.** `concomitates`, plain `precedes` and a certainty tag keep claims open; elsewhere openness survives only as free text and warnings.", size=19), after=0)
))

# --- 1 layers
B.append(heading("1  One graph, two layers"))
B.append(grey_columns([
    ("Generated", ["derived from the edition data", "relations read off the numbering", "op. 25: 1226 triples"]),
    ("Curated", ["asserted by editors", "evidence, uncertainty, relations across complexes", "op. 25: 1133 triples"]),
]))
B.append(note("Draft ontology v0.1 · SPARQL in the app · Turtle export · no reasoning"))

# --- 2 op. 25
B.append(heading("2  Op. 25: the sketches cross the opus order"))
B.append(p("Edition complex op. 25 = M 317 (song I) · M 322 (song II) · M 321 (song III)"))
B.append(chain(["M 317 Sk4", "M 321 Sk1–9", "M 322 Sk1"]))
B.append(note("Curated chain: song III was sketched before song II, alongside the row table `Op25_SkRT`. The generator sees three separate islands."))

# --- 3 terms
B.append(heading("3  Terms and classes"))
B.append(grid_table([2900, 3700, 3606], ["Editorial term", "Class", "Note"], [
    ["sketch (Skizze)", "`Sketch` ⊂ `Inscription`", "content and object at once"],
    ["paratext", "`Paratext` ⊂ `Inscription`", "can stand in a genetic chain"],
    ["row table, continuity draft", "`RowTable`, `ContinuityDraft` ⊂ `Sketch`", ""],
    ["version (Textfassung)", "`TextVersion`", "abstract, not the edited sheet"],
    ["work, text, sketch edition", "⊂ `EditedMusicText`", "`edits` its object"],
    ["uncertainty", "tag on a statement", "no tag = certain"],
    ["study composition, ink draft", "not modelled yet", ""],
]))

# --- 4 relations
B.append(heading("4  Genetic relations"))
B.append(grid_table([2300, 3700, 2400, 1806], ["Relation", "Meaning", "Properties", "CRM (seeAlso)"], keep=True, rows=[
    ["`precedes`", "A begun before B, overlap allowed", "transitive", "P176"],
    ["`concomitates`", "mutual influence, order undecidable", "symmetric, not transitive", "P174 (overlap)"],
    ["`precedesScripture`", "evidence: the writing", "subproperty", ""],
    ["`precedesContent`", "evidence: the music", "subproperty", ""],
]))
B.append(note("Generator: Sk1 → Sk2 as plain `precedes`, Sk2.1 `concomitates` Sk2 – never across complexes."))

# --- 5 frictions
B.append(heading("5  Where model and data disagree", new_page=True))
B.append(grey_columns([
    ("Model lags data", ["staves, measures as free text (“1c–3c”)", "writing instruments missing"]),
    ("Data lag model", ["sketchbook 3 described twice", "29 sketches as Sk## placeholders", "datings without year"]),
]))
B.append(note("12 generator warnings: `emptyItem` `folioConflict` `labelConflict` `incompleteDate` `noComplex` `noDocument` `noFolio` `noParentSketch` `placeholder` `unknownConvolute` `unknownItem` `unresolvedReference`"))

# --- 6 standards
B.append(heading("6  Standards: alignments, not the model"))
B.append(grid_table([2300, 5906, 2000], ["Standard", "Mapping", "Link"], [
    ["LRMoo", "complex ≈ F1 · version, sketch ≈ F2 · document ≈ F5", "`seeAlso`"],
    ["CIDOC CRM", "`precedes` ≈ P176 · `concomitates` ≈ P174 (via F28)", "`seeAlso`"],
    ["CRMinf", "editorial statement ≈ I2 Belief", "`seeAlso`"],
    ["DC terms, SKOS, PROV", "parts · concept schemes · attribution", "used directly"],
    ["MEI", "not integrated (sheets are SVG)", "–"],
]))

# --- 7 next
B.append(heading("7  Next steps"))
B.append(bullet("named graphs for ink and pencil layers"))
B.append(bullet("statement nodes only where uncertainty or a justification needs them"))
B.append(bullet("persons and archives"))
B.append(spacer(after=200))
B.append(mint_box(
    para(runs("**For discussion.** Whose genetic order does the graph show – Webern’s or ours?", size=19), after=60)
    + para(runs("How much of Webern’s compositional process survives translation into shared standards?", size=19), after=0)
))


# ================================================================ write
def build():
    with zipfile.ZipFile(TEMPLATE) as z:
        doc = z.read("word/document.xml").decode("utf-8")
        head = doc[: doc.index("<w:body>") + len("<w:body>")]
        sect = doc[doc.index("<w:sectPr"):]
        new_doc = head + "".join(B) + sect
        tmp = OUT + ".tmp"
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as out:
            names = [i for i in z.infolist() if not i.filename.endswith("/")]
            names.sort(key=lambda i: i.filename != "[Content_Types].xml")
            for info in names:
                data = new_doc.encode("utf-8") if info.filename == "word/document.xml" else z.read(info)
                out.writestr(info.filename, data)
    try:
        os.replace(tmp, OUT)
    except PermissionError:
        os.remove(tmp)
        sys.exit(f"Handout not updated: {OUT} is locked (open in Word?). Close it and run again.")
    print("saved", OUT)


def pdf():
    soffice = shutil.which("soffice") or r"C:\Program Files\LibreOffice\program\soffice.exe"
    target = os.path.splitext(OUT)[0] + ".pdf"
    work = tempfile.mkdtemp(prefix="lo_awg_ho_")
    subprocess.run(
        [soffice, f"-env:UserInstallation=file:///{work.replace(os.sep, '/')}/profile",
         "--headless", "--convert-to", "pdf", "--outdir", work, OUT],
        check=True, timeout=300, capture_output=True,
    )
    try:
        shutil.copyfile(os.path.join(work, os.path.basename(target)), target)
        print("saved", target)
    except PermissionError:
        sys.exit(f"PDF not updated: {target} is locked (open in a viewer?). Close it and run again.")
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    build()
    pdf()
