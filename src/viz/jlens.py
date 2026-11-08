"""J-lens paper style readout figures: prompt + oracle-lens readouts, drawn exactly like the J-lens paper's figures.

A literal port of the J-lens paper's Figure 7 (verbal introspection) markup and CSS
(transformer-circuits.pub/2026/workspace), with readout text in its Figure 64 oracle-lens phrase style:
type scale 11/12/13/15px, gray ramp, .prompt-block, .hl yellow #fff59d, .tok-hit outline, h6 column headers with a
swatch and a condition line. No figure title, no caption, no key: readout templates never carry them.

This is HTML rendered by Chromium, not a `viz.Figure`: `page(spec)` returns the HTML, `render(spec, stem)` writes
stem.html, stem.png (2x) and stem.pdf.

Fonts: the paper's stack, 'Anthropic Sans' / 'Anthropic Mono' first. Those files are not public, so the page embeds
similar open faces shipped in viz/fonts: DM Sans for Anthropic Sans, DM Mono for Anthropic Mono (OFL). A browser with
the real fonts installed still uses them. To embed the real files, pass `font_dir=` (or set VIZ_ANTHROPIC_FONTS) to a
folder holding .ttf/.otf/.woff/.woff2 files whose names contain "AnthropicSans" / "AnthropicMono".

Spec (dict or JSON):
  {"panels": [
     {"heading": "Asked whether a thought was injected",          # optional panel label
      "width": 600,                                                # optional px (default 600, or 600 + 352 for two)
      "cols": 2,                                                   # readout columns
      "turns": [{"role": "User",                                   # optional; no role -> plain text
                 "body": "...",
                 "injected": true,                                 # yellow wash over the turn
                 "read": "\"",                                     # read token, outlined (last occurrence)
                 "read_at": 12,                                    # optional char index if `read` repeats
                 "read_hl": false}],                               # optional yellow wash on the read token
      "readouts": [{"label": "Oracle lens",                         # header; " at <read token>" is appended
                    "at": true,                                     # false drops the " at <token>"
                    "color": "#ee7733",                             # swatch (paper's J-lens orange)
                    "cond": "After injecting \u201cBread\u201d", "cond_hl": ["injecting"],
                    "text": "I cannot detect any magic in this bread.",
                    "terms": ["bread"],                             # matched whole words in bold
                    "quote": true}]}]}                              # wrap the text in curly quotes

CLI: python -m viz.jlens spec.json OUT_STEM   -> OUT_STEM.{html,png,pdf}
Example: examples/jlens/injection.json
"""
from __future__ import annotations

import base64
import html
import json
import os
import re
import sys
from pathlib import Path

from viz.charts.readouts import _hit_mask

SIMILAR = Path(__file__).resolve().parent / "fonts"  # OFL faces close to the paper's: DM Sans, DM Mono
STAND_INS = {"Sans": [("DMSans.ttf", "100 900")], "Mono": [("DMMono-Regular.ttf", "400"), ("DMMono-Medium.ttf", "500 900")]}
ORANGE = "#ee7733"  # util.tol.orange, the paper's J-lens swatch
FMT = {".ttf": "truetype", ".otf": "opentype", ".woff": "woff", ".woff2": "woff2"}
MIME = {".ttf": "font/ttf", ".otf": "font/otf", ".woff": "font/woff", ".woff2": "font/woff2"}

CSS = """
:root {
  --font-sans: 'Anthropic Sans', __SANS_FALLBACK__system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  --font-mono: 'Anthropic Mono', __MONO_FALLBACK__ui-monospace, "SF Mono", Menlo, monospace;
  --fs-label: 11px; --fs-small: 12px; --fs-body: 13px; --fs-figure: 14px; --fs-title: 15px;
  --gray-100: #fafafa; --gray-200: #eee; --gray-300: #ddd; --gray-400: #bbb;
  --gray-500: #888; --gray-600: #555; --gray-700: #333; --gray-900: #111;
  --text: var(--gray-700); --text-light: var(--gray-500); --text-faint: var(--gray-400);
  --tok-bg: var(--gray-100); --tok-border: var(--gray-200); --tok-hit-outline: var(--gray-900);
  --hl-yellow: #fff59d; --lh-heading: 1.25;
}
html, body { margin: 0; background: #fff; }
figure { font-family: var(--font-sans); font-size: var(--fs-figure); line-height: normal;
  margin: 0; padding: 24px; width: max-content; color: var(--text); }

.fig-title { font-size: var(--fs-title); font-weight: 600; color: var(--text); margin: 0 0 10px;
  font-family: var(--font-sans); line-height: var(--lh-heading); }
.prompt-block { font-family: var(--font-mono); font-size: var(--fs-small);
  line-height: 1.6; white-space: pre-wrap; word-break: break-word;
  background: var(--tok-bg); border: 1px solid var(--tok-border);
  border-radius: 4px; padding: 8px 10px; color: var(--gray-600); }
.prompt-role { font-weight: 400; }
.tok-hit { outline: 1px solid var(--tok-hit-outline); outline-offset: -1px; border-radius: 2px;
  padding: 0 2px; background: transparent; }
.hl, mark { background: var(--hl-yellow); padding: 0 1px; border-radius: 1px; }
.swatch { display: inline-block; width: 10px; height: 10px; border-radius: 2px; flex-shrink: 0;
  vertical-align: middle; }

.vi-main { display: flex; flex-direction: row; gap: 28px; align-items: flex-start; }
.vi-panel { flex: none; position: relative; min-width: 0; }
.vi-prompt { margin-bottom: 24px; }
.vi-turn + .vi-turn { margin-top: 1.2em; }
.vi-turn { white-space: normal; }
.vi-cols { display: grid; grid-template-columns: repeat(var(--cols), minmax(0, 1fr)); gap: 18px 12px; align-items: start; }
.vi-col h6 { margin: 0 0 4px; font-size: var(--fs-label); color: var(--text); font-weight: 400;
  line-height: 1.3; min-height: 2.6em; font-family: var(--font-sans); }

/* readout text: the oracle-lens phrase style of Fig 64 (ol.ol-phrases) — mono, small; matched terms bold */
.ol-readout { margin: 0; font-family: var(--font-mono); font-size: var(--fs-small); line-height: 1.55;
  color: var(--text); word-break: break-word; }
.ol-readout b { color: var(--gray-900); font-weight: 600; }
"""


def esc(s: str) -> str:
    return html.escape(s, quote=False)


def _face(family: str, path: Path) -> str:
    name = path.stem.lower()
    weight = next((w for k, w in [("thin", 100), ("extralight", 200), ("light", 300), ("medium", 500),
                                   ("semibold", 600), ("bold", 700), ("black", 900)] if k in name), 400)
    if "variable" in name or "vf" in re.split(r"[-_ ]", name):
        weight = "100 900"
    style = "italic" if ("italic" in name or "oblique" in name) else "normal"
    b64 = base64.b64encode(path.read_bytes()).decode()
    return (f"@font-face {{ font-family: '{family}'; src: url(data:{MIME[path.suffix.lower()]};base64,{b64}) "
            f"format('{FMT[path.suffix.lower()]}'); font-weight: {weight}; font-style: {style}; font-display: block; }}")


def fonts(font_dir: str | Path | None = None) -> tuple[str, str]:
    """@font-face rules and the CSS with fallbacks filled in. Real Anthropic fonts if found in `font_dir`
    (or $VIZ_ANTHROPIC_FONTS), else the similar open faces."""
    found = {"Sans": [], "Mono": []}
    font_dir = font_dir or os.environ.get("VIZ_ANTHROPIC_FONTS")
    if font_dir and Path(font_dir).is_dir():
        for f in sorted(Path(font_dir).iterdir()):
            key = re.sub(r"[\s_-]", "", f.name.lower())
            for fam in found:
                if f.suffix.lower() in FMT and f"anthropic{fam.lower()}" in key:
                    found[fam].append(f)
    faces, css = [], CSS
    for fam, stand_in, token in [("Sans", "DM Sans", "__SANS_FALLBACK__"), ("Mono", "DM Mono", "__MONO_FALLBACK__")]:
        if found[fam]:
            faces += [_face(f"Anthropic {fam}", f) for f in found[fam]]
            css = css.replace(token, "")
        else:  # the similar face, embedded: DM Sans (variable) / DM Mono (regular; medium serves the bold)
            for file, weight in STAND_INS[fam]:
                faces.append(re.sub(r"font-weight: [^;]+;", f"font-weight: {weight};", _face(stand_in, SIMILAR / file)))
            css = css.replace(token, f"'{stand_in}', ")
    return "".join(faces), css


def _turn(t: dict) -> str:
    body, read = t["body"], t.get("read")
    if read:
        k = t["read_at"] if "read_at" in t else body.rfind(read)  # read_at: char index when read occurs more than once
        cls = "tok-hit hl" if t.get("read_hl") else "tok-hit"  # read_hl: yellow wash on the read token too
        inner = f'{esc(body[:k])}<span class="{cls}">{esc(read)}</span>{esc(body[k + len(read):])}'
    else:
        inner = esc(body)
    if t.get("injected"):
        inner = f'<span class="hl">{inner}</span>'
    role = f'<span class="prompt-role">{esc(t["role"])}: </span>' if t.get("role") else ""  # no role: plain text
    return f'<div class="vi-turn">{role}{inner}</div>'


def _marked(text: str, terms: list[str], tag: str, cls: str = "") -> str:
    if not terms:
        return esc(text)
    mask, out, k = _hit_mask(text, terms), [], 0
    open_ = f'<{tag} class="{cls}">' if cls else f"<{tag}>"
    while k < len(text):
        j = k
        while j < len(text) and mask[j] == mask[k]:
            j += 1
        out.append(f"{open_}{esc(text[k:j])}</{tag}>" if mask[k] else esc(text[k:j]))
        k = j
    return "".join(out)


def _readout(r: dict, read: str | None) -> str:
    at = f' at <span class="tok-hit">{esc(read)}</span>' if read and r.get("at", True) else ""
    head = (f'<div><span class="swatch" style="background:{r.get("color", ORANGE)};margin-right:5px"></span>'
            f'<span>{esc(r.get("label", "Oracle lens"))}{at}</span></div>')
    if r.get("cond"):
        head += f'<div class="cond">{_marked(r["cond"], r.get("cond_hl", []), "span", "hl")}</div>'
    text = f"“{r['text']}”" if r.get("quote", True) else r["text"]
    return f'<div class="vi-col"><h6>{head}</h6><p class="ol-readout">{_marked(text, r.get("terms", []), "b")}</p></div>'


def _default_widths(n: int) -> list[int]:
    return {1: [600], 2: [600, 352]}.get(n, [300] * n)


def page(spec: dict, font_dir: str | Path | None = None) -> str:
    """The figure as a standalone HTML page, fonts embedded."""
    panels = spec["panels"]
    widths = [p.get("width") or w for p, w in zip(panels, _default_widths(len(panels)))]
    body = []
    for p, w in zip(panels, widths):
        read = next((t["read"] for t in p["turns"] if t.get("read")), None)
        head = f'<div class="fig-title">{esc(p["heading"])}</div>' if p.get("heading") else ""
        cols = "".join(_readout(r, read) for r in p["readouts"])
        body.append(f'<div class="vi-panel" style="width:{w}px">{head}'
                    f'<div class="vi-prompt prompt-block">{"".join(_turn(t) for t in p["turns"])}</div>'
                    f'<div class="vi-cols" style="--cols:{p.get("cols", 1)}">{cols}</div></div>')
    faces, css = fonts(font_dir)
    return (f'<!doctype html><html><head><meta charset="utf-8"><title>Lens readouts</title>'
            f"<style>{faces}{css}</style></head><body>"
            f'<figure><div class="vi-main">{"".join(body)}</div></figure></body></html>')


def render(spec: dict, stem: str | Path, font_dir: str | Path | None = None) -> None:
    """Write stem.html, stem.png (2x) and stem.pdf."""
    from playwright.sync_api import sync_playwright

    stem = Path(stem)
    src = stem.with_suffix(".html")
    src.write_text(page(spec, font_dir))
    with sync_playwright() as p:
        br = p.chromium.launch()
        pg = br.new_page(device_scale_factor=2, viewport={"width": 1400, "height": 800})
        pg.goto(src.resolve().as_uri())
        pg.evaluate("document.fonts.ready")
        fig = pg.locator("figure")
        box = fig.bounding_box()
        fig.screenshot(path=str(stem.with_suffix(".png")))
        pg.set_viewport_size({"width": int(box["width"]) + 1, "height": 800})
        pg.pdf(path=str(stem.with_suffix(".pdf")), width=f"{box['width'] + 1}px",
               height=f"{box['height'] + 2}px", print_background=True, page_ranges="1")
        br.close()


if __name__ == "__main__":
    render(json.loads(Path(sys.argv[1]).read_text()), sys.argv[2])
    print("ok")
