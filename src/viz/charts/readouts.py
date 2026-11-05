"""Lens readouts: a prompt with the position that was read outlined, and what a lens read there, layer by layer.

    viz.readouts(tokens, {20: ["phrase", ...], 40: [...]}, at=17,
                 compare={20: ["tok", ...], 40: [...]}, highlight=["Borges"],
                 lens="Oracle lens", lens_note="s3d · k=4", compare_label="J-lens", compare_note="top 10")

The look follows the oracle-lens panels of the J-lens paper (transformer-circuits.pub/2026/workspace, Figure 64):
the prompt on a card with the read token outlined and the context before it muted, then one row per layer with the
lens's phrases as a list and, optionally, a second lens's tokens as chips beside them. Strings in `highlight`
(targets, a quoted phrase) are set in bold on a pale accent wherever they appear, and a layer that names one gets
an accent dot by its label, so the reader sees at a glance which layers carry the concept.
"""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from .. import svg as S
from .. import text as T
from .. import theme as th
from ..figure import Body, Figure

ELLIPSIS = "…"


# ---------------------------------------------------------------------- measuring, with a fallback for CJK

def _wide(ch: str) -> bool:
    """Characters the bundled fonts don't have and browsers draw a full em wide (CJK, kana, Hangul, full-width)."""
    o = ord(ch)
    return (0x2E80 <= o <= 0x9FFF or 0xAC00 <= o <= 0xD7AF or 0xF900 <= o <= 0xFAFF or 0xFE30 <= o <= 0xFE4F
            or 0xFF00 <= o <= 0xFFEF or 0x20000 <= o <= 0x2FFFF)


def _measure(s: str, size: float, family: str, weight: int) -> float:
    """T.width, but text the shaper rejects (stray control or combining characters) is measured character by
    character, and a character it still rejects counts as an en."""
    try:
        return T.width(s, size, family, weight)
    except (RuntimeError, OSError, ValueError):
        if len(s) == 1:
            return size * 0.5
        return sum(_measure(c, size, family, weight) for c in s)


def _width(s: str, size: float, family: str, weight: int = 400) -> float:
    if not s:
        return 0.0
    if not any(_wide(c) for c in s):
        return _measure(s, size, family, weight)
    w, run = 0.0, ""
    for c in s:
        if _wide(c):
            w += _measure(run, size, family, weight) + size if run else size
            run = ""
        else:
            run += c
    return w + _measure(run, size, family, weight)


# ---------------------------------------------------------------------- rich text: (text, flag) atoms, wrapped

def _hit_mask(s: str, terms: Sequence[str]) -> list[bool]:
    """Which characters of s fall inside a case-insensitive match of any term."""
    mask = [False] * len(s)
    low = s.lower()
    for t in terms:
        t = t.strip().lower()
        if not t:
            continue
        pat = re.escape(t)
        if t[0].isalnum():  # "4" should not light up "14", nor "art" "start"
            pat = r"(?<![^\W_])" + pat
        if t[-1].isalnum():
            pat += r"(?![^\W_])"
        for m in re.finditer(pat, low):
            for i in range(m.start(), m.end()):
                mask[i] = True
    return mask


def _words(chars: list[tuple[str, int]]) -> list[tuple[list[tuple[str, int]], bool]]:
    """Split flagged characters into words: ([(run text, flag), ...], space_before). Newlines become ("\\n", -1)."""
    out: list[tuple[list[tuple[str, int]], bool]] = []
    cur: list[tuple[str, int]] = []
    space = False

    def flush():
        nonlocal cur, space
        if cur:
            out.append((cur, space))
            space = False
        cur = []

    for ch, f in chars:
        if ch == "\n":
            flush()
            out.append(([("\n", -1)], False))
        elif ch in " \t":
            flush()
            space = True
        elif cur and cur[-1][1] == f:
            cur[-1] = (cur[-1][0] + ch, f)
        else:
            cur.append((ch, f))
    flush()
    return out


def _break_long(word: list[tuple[str, int]], max_w: float, size: float, family: str, weights) -> list[list]:
    """A word wider than the line, cut into pieces that fit (CJK text has no spaces to wrap at)."""
    pieces, cur, cw = [], [], 0.0
    for text, f in word:
        for ch in text:
            w = _width(ch, size, family, weights(f))
            if cur and cw + w > max_w:
                pieces.append(cur)
                cur, cw = [], 0.0
            if cur and cur[-1][1] == f:
                cur[-1] = (cur[-1][0] + ch, f)
            else:
                cur.append((ch, f))
            cw += w
    if cur:
        pieces.append(cur)
    return pieces


def _layout(chars: list[tuple[str, int]], max_w: float, size: float, family: str, weights,
            max_lines: int | None = None, pad: Mapping[int, float] | None = None
            ) -> tuple[list[list[tuple[float, str, int]]], bool]:
    """Wrap flagged characters into lines of placed runs [(x, text, flag)]. Returns the lines and whether the text
    was cut at max_lines (the last line then ends in an ellipsis). pad: extra room on both sides of runs with
    these flags (the outlined read token)."""
    pad = pad or {}
    space = _width(" ", size, family)
    limit = max_w * T.SAFETY
    lines: list[list[tuple[float, str, int]]] = [[]]
    x = 0.0
    words = _words(chars)
    expanded: list[tuple[list[tuple[str, int]], bool]] = []
    for w, sp in words:
        ww = sum(_width(t, size, family, weights(f)) for t, f in w)
        if ww > limit and w[0][1] != -1:
            parts = _break_long(w, limit, size, family, weights)
            expanded += [(p, sp if k == 0 else False) for k, p in enumerate(parts)]
        else:
            expanded.append((w, sp))
    for w, sp in expanded:
        if w[0][1] == -1:  # a line break
            lines.append([])
            x = 0.0
            continue
        ww = sum(_width(t, size, family, weights(f)) + 2 * pad.get(f, 0.0) for t, f in w)
        lead = space if (sp and x > 0) else 0.0
        if x > 0 and x + lead + ww > limit:
            lines.append([])
            x, lead = 0.0, 0.0
        x += lead
        for t, f in w:
            x += pad.get(f, 0.0)
            lines[-1].append((x, t, f))
            x += _width(t, size, family, weights(f)) + pad.get(f, 0.0)
    while len(lines) > 1 and not lines[-1]:
        lines.pop()
    cut = bool(max_lines) and len(lines) > max_lines
    if cut:
        lines = lines[:max_lines]
        last = lines[-1]
        ew = _width(ELLIPSIS, size, family)
        while last:  # drop runs (then characters) until the ellipsis fits
            x0, t, f = last[-1]
            end = x0 + _width(t, size, family, weights(f))
            if end + ew <= limit:
                break
            if len(t) > 1:
                last[-1] = (x0, t[:-1].rstrip(), f)
                if not last[-1][1]:
                    last.pop()
            else:
                last.pop()
        x_end = (last[-1][0] + _width(last[-1][1], size, family, weights(last[-1][2]))) if last else 0.0
        last.append((x_end, ELLIPSIS, 0))
    return lines, cut


def _line_text(ln, x0: float, y: float, size: float, family: str, weights, ink) -> str:
    """One wrapped line, drawn as one <text> per stretch of same-flag runs, each pinned to its measured width with
    textLength. Chromium sets these fonts up to ~2% wider than PIL measures them; pinning keeps the highlight
    marks under their words and the spaces between stretches from being eaten."""
    if not ln:
        return ""
    space = _width(" ", size, family)
    groups: list[list] = []  # [x, text, flag, end]
    for x, t, f in ln:
        w = _width(t, size, family, weights(f))
        g = groups[-1] if groups else None
        if g and g[2] == f and abs(x - g[3] - space) < 0.75:
            g[1] += " " + t
            g[3] = x + w
        elif g and g[2] == f and abs(x - g[3]) < 0.25:
            g[1] += t
            g[3] = x + w
        else:
            groups.append([x, t, f, x + w])
    out = []
    for x, t, f, end in groups:
        a = S.font_attrs(size, family, weights(f), False, ink(f))
        fit = f' textLength="{S.n(end - x)}" lengthAdjust="spacing"' if len(t) > 1 and end - x > 1 else ""
        out.append(f'<text x="{S.n(x0 + x)}" y="{S.n(y)}" {a}{fit} xml:space="preserve">{S.esc(t)}</text>')
    return "".join(out)


# ---------------------------------------------------------------------- the prompt

def _prompt_stream(prompt, at) -> tuple[list[tuple[str, int]], tuple[int, int] | None]:
    """The prompt as flagged characters: flag 1 the read token, 0 text, and ("\\x00role", -2) for a role label.
    Returns the characters and the read token's character span."""
    if isinstance(prompt, str):
        if at is None:
            return [(c, 0) for c in prompt], None
        if isinstance(at, str):
            i = prompt.rfind(at)
            if i < 0:
                raise ValueError(f"at={at!r} is not in the prompt")
            span = (i, i + len(at))
        else:
            span = (int(at[0]), int(at[1]))
        return [(c, 1 if span[0] <= k < span[1] else 0) for k, c in enumerate(prompt)], span
    toks = list(prompt)
    if at is not None and not isinstance(at, int):
        raise TypeError("with a list of tokens, at= is the index of the token that was read")
    if at is not None and at < 0:
        at += len(toks)
    out: list[tuple[str, int]] = []
    span = None
    for i, t in enumerate(toks):
        if isinstance(t, Mapping):  # {"role": "user"}: a label on its own line
            out.append((str(t.get("role", "")), -2))
            continue
        flag = 1 if i == at else 0
        if flag:
            span = (len(out), len(out) + len(t))
        out += [(c, flag) for c in str(t)]
    return out, span


def _excerpt(stream, span, before: int | None, after: int | None):
    """Keep `before` characters before the read token and `after` after it, cut at spaces, with the speaker of
    the first kept text. Returns (stream, cut_before, cut_after)."""
    if span is None:
        return stream, False, False
    lo = 0 if before is None else max(0, span[0] - before)
    hi = len(stream) if after is None else min(len(stream), span[1] + after)
    if lo > 0:
        while lo < span[0] and stream[lo - 1][0] not in " \n":
            lo += 1
    if hi < len(stream):
        while hi > span[1] and stream[hi][0] not in " \n":
            hi -= 1
    role = None
    if lo > 0:
        for k in range(lo - 1, -1, -1):
            if stream[k][1] == -2:
                role = stream[k]
                break
    kept = ([role] if role else []) + list(stream[lo:hi])
    return kept, lo > 0, hi < len(stream)


# ---------------------------------------------------------------------- the chart

def _phrases(v) -> list[str]:
    """A cell's phrases: a list, or one string of "- " bullets (the oracle lens's raw output), or one phrase."""
    if v is None:
        return []
    if isinstance(v, str):
        v = [v]
    out: list[str] = []
    for s in v:
        s = str(s)
        if re.match(r"\s*- ", s):
            out += re.split(r"(?:^|\n)- ", s)
        else:
            out.append(s)
    out = [re.sub(r"\s*\n\s*", " ", p).strip().rstrip(" -–—").rstrip() for p in out]  # one phrase reads as one line of text
    return [p for p in out if p.strip(" -–—.…")]


def _tokens_of(v) -> list[str]:
    """A comparison cell's tokens: a list, or {"t": [...], "s": [...]} (tokens with scores)."""
    if v is None:
        return []
    if isinstance(v, Mapping):
        v = v.get("t") or v.get("tokens") or []
    return [str(t) for t in v]


def _layer_name(k) -> str:
    s = str(k)
    return f"L{s}" if s.lstrip("-").isdigit() else s


def readouts(prompt, reads, *, at=None, layers=None, compare=None, highlight=None, lens="Oracle lens",
             lens_note=None, compare_label="J-lens", compare_note=None, prompt_label="Prompt", prompt_note=None,
             before=600, after=160, max_lines=3, max_phrases=None, max_tokens=10, highlight_label="Target",
             title=None, subtitle=None, width=None) -> Figure:
    """A prompt with the position a lens read outlined, and the lens's readouts there, one row per layer.

    prompt: the text, or its tokens as the tokenizer gives them (" the" keeps its space); a {"role": "user"} item in
    a token list starts a new speaker, labeled on its own line. at: the token that was read, an index into the
    tokens (or, for a string prompt, the substring, its last occurrence, or a (start, end) character span).
    reads: {layer: phrases}, phrases a list of strings or one string of "- " bullets. compare: a second lens at the
    same layers, {layer: [token, ...]} or {layer: {"t": [...], "s": [...]}}, drawn as chips. layers: which layers
    to show, in order (all of reads by default). highlight: strings to mark wherever they appear, such as the
    target. before / after: characters of prompt kept around the read token (None keeps all); the cut is marked
    with [...]. max_lines: lines per phrase before it is cut with an ellipsis (None for no limit). max_phrases,
    max_tokens: how many phrases and comparison tokens a row shows.
    """
    terms = [highlight] if isinstance(highlight, str) else list(highlight or [])
    keys = list(layers) if layers is not None else list(reads)
    if not keys:
        raise ValueError("readouts() needs at least one layer to show")
    stream, span = _prompt_stream(prompt, at)
    stream, cut_lo, cut_hi = _excerpt(stream, span, before, after)

    accent = th.color("intervention")
    mark = th.tone("coral", 0.16)
    chip_fill, chip_line = th.CARD_LIGHT, th.RULE

    P_SIZE, P_LH = 15, 23            # prompt
    R_SIZE, R_LH = 13.5, 19.5        # readout phrases
    C_SIZE, C_H, C_PAD, C_GAP = 12, 22, 6, 5  # comparison chips
    CAP = 12                         # small caps labels (the house minimum)
    LAYER_W = 44

    def cap(x, y, s, fill=None, anchor="start"):
        return S.text(x, y, s.upper(), CAP, fill or th.MUTED, anchor, weight=600, extra='letter-spacing="0.06em"')

    def runs_svg(lines, x0, y0, lh, size, family, weights, ink, fill_of=None):
        """Draw wrapped lines; flag 1 runs bold on a pale mark."""
        out = []
        base = T.baseline(size, family, lh)
        for i, ln in enumerate(lines):
            y = y0 + i * lh
            # marks first, merged across the spaces between neighbouring hits
            k = 0
            while k < len(ln):
                if ln[k][2] == 1:
                    j = k
                    while j + 1 < len(ln) and ln[j + 1][2] == 1:
                        j += 1
                    xa = ln[k][0]
                    xb = ln[j][0] + _width(ln[j][1], size, family, weights(1))
                    out.append(S.rect(x0 + xa - 2, y + (lh - size * 1.32) / 2, xb - xa + 4, size * 1.32,
                                      fill_of(1) if fill_of else mark, 3))
                    k = j + 1
                else:
                    k += 1
            out.append(_line_text(ln, x0, y + base, size, family, weights, ink))
        return "".join(out)

    def prompt_card(W: float) -> tuple[str, float]:
        pad_x, pad_t, pad_b = 18, 14, 16
        inner = W - 2 * pad_x
        # split the stream into paragraphs at role labels
        blocks: list[tuple[str | None, list[tuple[str, int]]]] = [(None, [])]
        for c, f in stream:
            if f == -2:
                blocks.append((c, []))
            else:
                blocks[-1][1].append((c, f))
        blocks = [(r, cs) for r, cs in blocks if r is not None or "".join(c for c, _ in cs).strip()]
        for b, (r, cs) in enumerate(blocks):  # trim blank lines at the edges of each block
            while cs and cs[0][0] in "\n" and cs[0][1] != 1:
                cs.pop(0)
            while cs and cs[-1][0] in "\n " and cs[-1][1] != 1:
                cs.pop()
        if cut_lo and blocks:
            r, cs = blocks[0]
            blocks[0] = (r, [("[…] ", 2)] + cs)
        if cut_hi and blocks:
            r, cs = blocks[-1]
            blocks[-1] = (r, cs + [(" […]", 2)])

        def w8(f):
            return 400

        def ink(f):
            return th.FAINT if f == 2 else th.INK

        out, y = [], pad_t + 12
        head = cap(pad_x, y, prompt_label)
        if prompt_note:
            head += S.text(W - pad_x, y, prompt_note, 12.5, th.MUTED, "end")
        y += 12
        read_box = None
        for r, cs in blocks:
            if r is not None:
                y += 6
                out.append(cap(pad_x, y + 11, r, th.FAINT))
                y += 18
            chars: list[tuple[str, int]] = []
            for seg, f in cs:
                chars += [(c, f) for c in seg]
            lines, _ = _layout(chars, inner, P_SIZE, "serif", w8, pad={1: 3.0})
            for i, ln in enumerate(lines):
                for x, t, f in ln:
                    if f == 1:
                        tw = _width(t, P_SIZE, "serif")
                        bx, by = pad_x + x, y + i * P_LH
                        read_box = (bx, by, tw) if read_box is None else read_box
                        out.append(S.rect(bx - 3, by + 1.5, tw + 6, P_LH - 3, mark, 3))
                        out.append(f'<rect x="{S.n(bx - 3)}" y="{S.n(by + 1.5)}" width="{S.n(tw + 6)}" '
                                   f'height="{S.n(P_LH - 3)}" rx="3" fill="none" stroke="{th.INK}" stroke-width="1.4"/>')
            out.append(runs_svg(lines, pad_x, y, P_LH, P_SIZE, "serif", w8, ink, fill_of=lambda f: "none"))
            y += len(lines) * P_LH
        h = y + pad_b
        return S.rect(0, 0, W, h, th.CARD, 10) + head + "".join(out), h

    def table(W: float, y0: float) -> tuple[str, float]:
        has_cmp = compare is not None
        gap = 22
        x_r = LAYER_W
        if has_cmp:
            w_r = (W - LAYER_W - gap) * 0.62
            x_c = x_r + w_r + gap
            w_c = W - x_c
        else:
            w_r, x_c, w_c = W - LAYER_W, W, 0.0
        out = []
        y = y0
        # header
        hx = x_r
        out.append(cap(hx, y + 11, lens, th.INK2))
        if lens_note:
            out.append(S.text(hx + _width(lens.upper(), CAP, "sans", 600) + len(lens) * CAP * 0.06 + 8, y + 11,
                              lens_note, 12, th.MUTED))
        if has_cmp:
            out.append(cap(x_c, y + 11, compare_label, th.INK2))
            if compare_note:
                out.append(S.text(x_c + _width(compare_label.upper(), CAP, "sans", 600)
                                  + len(compare_label) * CAP * 0.06 + 8, y + 11, compare_note, 12, th.MUTED))
        if terms and highlight_label:
            lw = _width(highlight_label, 12, "sans", 600)
            out.append(S.rect(W - lw - 8, y - 1, lw + 8, 17, mark, 3))
            out.append(S.text(W - 4, y + 11.5, highlight_label, 12, th.INK, "end", weight=600))
        y += 22
        out.append(S.line(0, y, W, y, th.AXIS, 1))

        def wr(f):
            return 600 if f == 1 else 400

        for key in keys:
            phrases = _phrases(reads.get(key) if isinstance(reads, Mapping) else None)
            if key not in reads and str(key) in reads:
                phrases = _phrases(reads[str(key)])
            if max_phrases:
                phrases = phrases[:max_phrases]
            top = y + 10
            ry = top
            any_hit = False
            for p in phrases:
                mask = _hit_mask(p, terms)
                any_hit |= any(mask)
                lines, _ = _layout([(c, 1 if m else 0) for c, m in zip(p, mask)], w_r - 14, R_SIZE, "sans", wr,
                                   max_lines, pad={1: 1.5})
                out.append(S.circle(x_r + 3, ry + R_LH / 2, 2, th.FAINT))
                out.append(runs_svg(lines, x_r + 14, ry, R_LH, R_SIZE, "sans", wr,
                                    lambda f: th.INK if f == 1 else th.INK2))
                ry += len(lines) * R_LH + 3
            if not phrases:
                out.append(S.text(x_r, ry + T.baseline(R_SIZE, "sans", R_LH), "no readout", R_SIZE, th.FAINT,
                                  family="sans", italic=True))
                ry += R_LH
            cy = top
            if has_cmp:
                cv = compare.get(key, compare.get(str(key))) if isinstance(compare, Mapping) else None
                toks = _tokens_of(cv)[:max_tokens]
                cx = 0.0
                for t in toks:
                    shown = t.strip() or t.replace("\n", "⏎").replace(" ", "␣")  # a token's own space is noise
                    hit = any(_hit_mask(t.strip(), terms)) and bool(t.strip())
                    any_hit |= hit
                    tw = _width(shown, C_SIZE, "mono", 600 if hit else 400) + 2 * C_PAD
                    if cx > 0 and cx + tw > w_c:
                        cx, cy = 0.0, cy + C_H + C_GAP
                    bx = x_c + cx
                    if hit:
                        out.append(S.rect(bx, cy, tw, C_H, mark, 4))
                    else:
                        out.append(S.rect(bx, cy, tw, C_H, chip_fill, 4))
                        out.append(f'<rect x="{S.n(bx + .5)}" y="{S.n(cy + .5)}" width="{S.n(tw - 1)}" '
                                   f'height="{S.n(C_H - 1)}" rx="4" fill="none" stroke="{chip_line}"/>')
                    out.append(S.text(bx + C_PAD, cy + T.baseline(C_SIZE, "mono", C_H), shown, C_SIZE,
                                      th.INK if hit else th.INK2, family="mono", weight=600 if hit else 400,
                                      extra='xml:space="preserve"'))
                    cx += tw + C_GAP
                cy = cy + C_H if toks else cy
                if not toks:
                    out.append(S.text(x_c, top + T.baseline(R_SIZE, "sans", R_LH), "no readout", R_SIZE, th.FAINT,
                                      family="sans", italic=True))
                    cy = top + R_LH
            lab_y = top + T.baseline(12.5, "mono", R_LH)
            out.append(S.text(0, lab_y, _layer_name(key), 12.5, th.INK if any_hit else th.MUTED, family="mono",
                              weight=600 if any_hit else 400))
            if any_hit:
                out.append(S.circle(LAYER_W - 12, lab_y - 4.5, 3.5, accent))
            y = max(ry - 3, cy) + 10
            out.append(S.line(0, y, W, y, th.GRID, 1))
        return "".join(out), y

    def render(W: float) -> Body:
        card, h = prompt_card(W)
        tab, y = table(W, h + 20)
        return Body(card + tab, y + 2)

    return Figure(render, title=title, subtitle=subtitle, legend=False, width=width, kind="readouts")


def describe(prompt, reads, *, at=None, layers=None, compare=None, highlight=None, lens="Oracle lens",
             compare_label="J-lens", max_phrases=None, **_kw) -> str:
    """Alt text: where the lens read, and what it read at each layer."""
    stream, span = _prompt_stream(prompt, at)
    text = "".join(c for c, f in stream if f != -2)
    read = text[span[0]:span[1]].strip() if span else ""
    keys = list(layers) if layers is not None else list(reads)
    shown = text[: span[1]] if span else text  # the text leading up to the read token
    parts = [f"Lens readouts. Prompt: \"{shown.strip()[-240:]}\"" + (f", read at \"{read}\"." if read else ".")]
    for k in keys:
        ph = _phrases(reads.get(k, reads.get(str(k))))[: max_phrases or 4]
        s = f"{_layer_name(k)}, {lens}: " + "; ".join(p[:80] for p in ph)
        if compare is not None:
            toks = _tokens_of(compare.get(k, compare.get(str(k))))[:5]
            s += f". {compare_label}: " + ", ".join(t.strip() for t in toks)
        parts.append(s + ".")
    if highlight:
        hs = [highlight] if isinstance(highlight, str) else list(highlight)
        parts.append("Highlighted: " + ", ".join(hs) + ".")
    return " ".join(parts)
