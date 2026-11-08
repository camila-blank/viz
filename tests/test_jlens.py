"""viz.jlens: the J-lens paper style readout page."""
from __future__ import annotations

import json
from pathlib import Path

from viz import jlens

SPEC = json.loads((Path(__file__).resolve().parents[1] / "examples" / "jlens" / "injection.json").read_text())


def test_page_has_the_papers_pieces():
    html = jlens.page(SPEC)
    assert html.count('class="vi-panel"') == 2
    assert html.count('class="vi-col"') == 6  # 4 + 2 readouts
    assert '<span class="tok-hit">&quot;</span>' in html or '<span class="tok-hit">"</span>' in html
    assert "<b>lighthouse</b>" in html and "<b>paper crane</b>" in html
    assert 'class="hl"' in html and "#fff59d" in html
    assert "fig-title" in html  # panel headings only; the page carries no figure title or caption
    assert "<figcaption" not in html


def test_fonts_paper_stack_with_similar_faces_embedded():
    html = jlens.page(SPEC)
    assert "--font-sans: 'Anthropic Sans', 'DM Sans'," in html
    assert "--font-mono: 'Anthropic Mono', 'DM Mono'," in html
    assert html.count("@font-face") == 3  # DM Sans variable + DM Mono regular and medium


def test_real_fonts_are_embedded_when_given(tmp_path):
    fonts = Path(jlens.__file__).resolve().parent / "fonts"
    (tmp_path / "AnthropicSans-Regular.ttf").write_bytes((fonts / "DMSans.ttf").read_bytes())
    html = jlens.page(SPEC, font_dir=tmp_path)
    assert "font-family: 'Anthropic Sans'; src:" in html
    assert "--font-sans: 'Anthropic Sans', system-ui" in html  # no stand-in once the real face is there
    assert "'DM Mono'" in html  # mono still falls back


def test_turn_options():
    spec = {"panels": [{"turns": [{"body": "a, b, c", "read": ",", "read_at": 1, "read_hl": True}],
                        "readouts": [{"text": "x", "at": False, "quote": False}]}]}
    html = jlens.page(spec)
    assert 'a<span class="tok-hit hl">,</span> b, c' in html
    assert "<span class=\"prompt-role\">" not in html
    assert "Oracle lens</span>" in html
