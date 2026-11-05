"""viz.readouts: the read token is outlined, phrases and chips are drawn, targets are marked, long prompts are cut."""
import re

import viz
from viz.charts import readouts as R

TOKS = ["The", " capital", " of", " France", " is"]


def test_draws_prompt_phrases_and_chips():
    fig = viz.readouts(TOKS, {20: ["Paris, the city of light", "Lyon"], 40: "- Paris\n- France's capital"},
                       at=-1, compare={20: [" Paris", " city"], 40: {"t": [" Paris"], "s": [3.1]}},
                       highlight="Paris", title="The lens reads Paris at the last token")
    svg = fig.svg()
    assert "L20" in svg and "L40" in svg
    assert "J-LENS" in svg and "ORACLE LENS" in svg
    assert 'stroke-width="1.4"' in svg  # the read token's outline
    assert svg.count(">Paris<") >= 3  # in two phrases and a chip, marked runs drawn on their own
    assert "Lens readouts" in fig.alt_text()


def test_bullet_strings_split_and_clean():
    assert R._phrases("- a b\n- c\nd\n- -") == ["a b", "c d"]
    assert R._phrases(None) == []


def test_highlight_respects_word_edges():
    m = R._hit_mask("14 or 4", ["4"])
    assert m == [False, False, False, False, False, False, True]
    assert any(R._hit_mask("Simula 67.", ["simula 67"]))


def test_long_prompt_is_cut_around_the_read_token():
    words = [f" w{i}" for i in range(400)]
    fig = viz.readouts(words, {20: ["x"]}, at=200, before=50, after=20)
    svg = re.sub(r"<desc.*?</desc>", "", fig.svg())
    assert "[…]" in svg and "w199" in svg and "w0<" not in svg and "w399" not in svg


def test_roles_and_cjk_wrap():
    toks = [{"role": "User"}, "写一首诗" * 60, {"role": "Assistant"}, "OK"]
    svg = viz.readouts(toks, {20: ["诗" * 300]}, at=3, max_lines=2).svg()
    assert "USER" in svg and "ASSISTANT" in svg and "…" in svg
    assert all(float(x) < 1100 for x in re.findall(r'<text x="([\d.]+)"', svg))
