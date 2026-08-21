# Working in this repository

This file is for a coding agent. A person reading it will not be harmed, but
[README.md](README.md) is the document written for them.

## What this project is, in one paragraph

A model of the Sony S-DSP, the sound generator inside the SNES audio unit: eight
voices, BRR decoding, an envelope per voice, a noise source, pitch modulation,
and an eight tap echo. It is not the processor beside it, which is
[sony-spc700-python](https://github.com/gufranco/sony-spc700-python).

## The authority ladder, and where this project sits on it

1. **`conformance/hardware.json`**, which is the sound chapters of Nintendo's
   SNES Development Manual pinned table by table: the register map, the ADSR
   parameters, the GAIN parameters, and the noise clock. It decides every
   address and every rate.
2. **A recording of a real S-DSP.** There is none on this machine.
3. **`conformance/corpus.json`**, which is snes9x. It decides what the manual
   does not, which here is the audio itself.

**Rung 3 is doing more work in this project than in any of its siblings, and
that is the thing to fix.** The samples this model produces are checked against
an emulator. Where snes9x is wrong, this is wrong with it, and no check here can
tell. `conformance/divergences.json` says so plainly rather than leaving it
implied by the file names.

What is no longer on rung 3: every entry of the rate table, every attack time,
and every register address. Those are held to Nintendo's own figures by
`conformance/hardware.test.py`.

## Read the page, never the text layer

The manual is a scan with an OCR layer, and that layer interleaves the table
columns. Every figure in `hardware.json` was read off a rendered page:

```bash
pdftoppm -r 200 -png -f 153 -l 196 book1.pdf pages/p
```

The sound chapters are PDF pages 153 to 196. The register map is on 168, the
ADSR parameters on 170, the GAIN parameters on 172, the noise clock on 177.

## Every gate, in the order to run them

```bash
ruff format --check .                     # formatting
ruff check .                              # lint, zero warnings
mypy                                      # types, strict
pnpm run format:check                     # every JSON file
for f in sdsp/*.test.py conformance/*.test.py; do python3 "$f"; done
python3 -m coverage report                # fails below 100%

python3 conformance/corpus.py             # the audio, against the reference
python3 -m sdsp.doctor                    # what is missing on this machine
```

`conformance/hardware.test.py` is in that loop and needs nothing else on the
machine. It is the part of the gate that rests on the manual.

## How the manual's tables were checked

**The noise clock is the strongest check in the project.** Its 32 frequencies
are 32000 divided by the 32 entries of `COUNTER_RATES`, one for one. It names
every entry rather than a ratio between them, so it pins the whole table.

**The attack column is absolute.** The step is one sixty fourth, so a climb from
silence takes 64 ticks, and 64 times the tick period is a time that can be
compared directly. All 16 printed figures come out right.

**The decay and sustain columns are not absolute**, because a time to fall means
nothing without saying how far. Dividing each printed figure by the tick period
for that rate gives 576 to 600 ticks across all 39 of them. That constant is the
endpoint Nintendo measured to, recovered from the table. It is recorded as a
divergence rather than built in, because a number nobody printed is not a fact.

## Things that will bite you

**A tolerance here is not slack.** Nintendo rounds to two significant figures, so
1333 hertz is printed as 1.3 KHz. Three per cent covers that and nothing wider,
and `test_the_tolerance_is_tight_enough_to_catch_a_table_that_moved` exists to
prove the tolerance still fails on a table that moved.

**The corpus records no audio RAM.** A music dump is mostly the music. The
capture tool reads the registers and seeks past the rest, and nothing in
`corpus.json` could rebuild a bar of anything.

**The interpolation kernel has no source.** It shapes every sample and no check
here can reach it.

## What is deliberately not here

- **No music, no dump, no fragment of either.** The corpus holds register
  configurations and digests of computed output, never content.
- **The SPC700.** The processor that drives this chip is a separate package.
- **Timing.** The manual gives no cycle counts and none are claimed.

## Conventions

| Thing | Rule |
|:------|:-----|
| Language | Python only |
| Comments | None in source. Docstrings carry the reasoning, and say why rather than what |
| Test layout | `<module>.test.py` beside the module it covers |
| Test structure | Arrange, blank line, one act, blank line, assert. No section labels |
| Package manager for tooling | pnpm, never npm |
| Commits | Conventional Commits |
