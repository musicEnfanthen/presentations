"""Print version of speaker-notes.md: writes AWG-Graph-Speaker-Notes.pdf (A4).

Continuous text (no page break per slide): slide number, title, label and target time as header,
spoken text in large type, cues ([…]) in grey italics. The preamble of the
Markdown file (conventions) is left out. Rendered with headless Chrome/Edge.
"""
import html
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "speaker-notes.md"
OUT = ROOT / "AWG-Graph-Speaker-Notes.pdf"
TMP = Path(__file__).resolve().parent / "speaker-notes-print.html"

BROWSERS = [
    shutil.which("chrome"), shutil.which("msedge"),
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]

CSS = """
@page { size: A4; margin: 18mm 20mm 18mm 22mm; }
body { font-family: Arial, sans-serif; font-size: 14pt; line-height: 1.5;
       color: #2D373C; margin: 0; }
section { margin-top: 22pt; }
section:first-of-type { margin-top: 0; }
header { border-bottom: 2pt solid #A5D7D2; padding-bottom: 6pt; margin-bottom: 12pt;
         break-inside: avoid; break-after: avoid; }
.meta { display: flex; justify-content: space-between; font-size: 11pt;
        color: #006E6E; font-weight: bold; }
.time { color: #D20537; white-space: nowrap; padding-left: 12pt; }
h2 { font-family: Georgia, serif; font-size: 11.5pt; line-height: 1.3;
     margin: 4pt 0 0; }
p { margin: 0 0 10pt; }
.cue { color: #6E787D; font-style: italic; font-size: 12pt; }
p.cue { margin-left: 0; }
code { font-family: Consolas, monospace; font-size: 13pt; }
"""


def inline(text):
    t = html.escape(text, quote=False)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\w)\*([^*]+)\*(?!\w)", r"<em>\1</em>", t)
    return re.sub(r"\[[^\]]*\]", lambda m: f'<span class="cue">{m.group(0)}</span>', t)


def arrival(duration, cumulative):
    """Expected start of the slide: cumulative end time minus its duration."""
    sec = lambda s: int(s.split(":")[0]) * 60 + int(s.split(":")[1])
    start = sec(cumulative) - sec(duration)
    return f"{start // 60}:{start % 60:02d}"


def slides(md):
    for block in re.split(r"^## ", md, flags=re.M)[1:]:
        head, _, body = block.partition("\n")
        m = re.match(r"Slide (\d+) – (.*?) / (.*)$", head.strip())
        num, title, label = m.groups()
        paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
        tm = re.match(r"\[.*?\] Target time: ([\d:]+) \(cumulative ([\d:]+)", paras[0])
        yield num, title, label, tm.groups() if tm else None, paras[1:] if tm else paras


def build_html():
    parts = []
    for num, title, label, time, paras in slides(SRC.read_text(encoding="utf-8")):
        t = f"at {arrival(*time)}" if time else ""
        body = []
        for p in paras:
            # lines inside one paragraph: keep the break
            p_html = "<br>".join(inline(line) for line in p.splitlines())
            cls = ' class="cue"' if re.fullmatch(r"\[[^\]]*\]", p) else ""
            if cls:
                p_html = html.escape(p, quote=False)
            body.append(f"<p{cls}>{p_html}</p>")
        parts.append(
            f'<section><header><div class="meta"><span>Slide {num} · {html.escape(label)}</span>'
            f'<span class="time">{t}</span></div><h2>{inline(title)}</h2></header>'
            + "\n".join(body) + "</section>")
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f"<title>Speaker notes</title><style>{CSS}</style></head><body>"
            + "\n".join(parts) + "</body></html>")


def main():
    TMP.write_text(build_html(), encoding="utf-8")
    browser = next((b for b in BROWSERS if b and Path(b).exists()), None)
    if not browser:
        sys.exit("No Chrome or Edge found.")
    tmp_pdf = TMP.with_suffix(".pdf")
    subprocess.run([browser, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={tmp_pdf}", TMP.as_uri()], check=True,
                   capture_output=True)
    try:
        shutil.copyfile(tmp_pdf, OUT)
    except PermissionError:
        sys.exit(f"{OUT.name} is open in a viewer: please close it and run again.")
    tmp_pdf.unlink()
    TMP.unlink()
    print("saved", OUT)


if __name__ == "__main__":
    main()
