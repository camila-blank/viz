"""Lens readouts.

A prompt with the position a lens read outlined, and what two lenses read there, layer by layer.
"""
import viz

# Readout templates carry no title: the caption (or the page around the figure) says what it shows.
# The prompt as the tokenizer split it; the lens was read at "with" (index 19). Phrases and tokens are made up.
prompt = ["Fact", ":", " the", " 1967", " Norwegian", " Computing", " Center", " creation", " that", " introduced",
          " the", " concepts", " of", " class", " and", " object", " was", " designed", " by", " Ole", "-J", "ohan",
          " Dahl", " together", " with"]
oracle = {
    20: ["co-authors to create Simula 67. They developed the concept together",
         "Kristen Nygaard and together they presented the language in 1967"],
    36: ["Kristen Nygaard to create a language called Simula 67. Together with",
         "the Norwegian Computing Center team. They are credited with creating the language"],
    52: ["Kristen Nygaard, with whom he designed Simula 67, the first object-oriented language",
         "Nygaard. The answer is Kristen Nygaard"],
}
jlens = {20: ["colleague", "together", ".hpp", "assistant", "partner"],
         36: ["together", "colleague", "Simula", "computer", "IBM"],
         52: ["Kristen", "Nygaard", "Simula", "colleague", "programmer"]}
fig = viz.readouts(
    prompt, oracle, at=-1, compare=jlens, highlight=["Simula 67", "Simula", "Nygaard"],
    lens="Oracle lens", lens_note="K=2", compare_label="J-lens", compare_note="top 5")
fig.save("34_readouts.png")
