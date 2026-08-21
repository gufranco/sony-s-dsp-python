# The family standard

These sixteen repositories are one family and are held to one standard. Where
they differ, the difference must be something the hardware forces, not something
nobody got round to.

| Repository | What it models |
|:--|:--|
| [mos65xx-python](https://github.com/gufranco/mos65xx-python) | The 65xx family, eight parts |
| [nec-upd7725-python](https://github.com/gufranco/nec-upd7725-python) | The DSP the SNES coprocessors are built on |
| [snes-driver-python](https://github.com/gufranco/snes-driver-python) | Reading a cartridge's own coprocessor protocol |
| [snes-dsp-python](https://github.com/gufranco/snes-dsp-python) | The DSP-1 to DSP-4 family |
| [snes-graphics-python](https://github.com/gufranco/snes-graphics-python) | The Super Nintendo graphics formats |
| [snes-mapper-python](https://github.com/gufranco/snes-mapper-python) | Cartridge headers and address decoding |
| [snes-obc1-python](https://github.com/gufranco/snes-obc1-python) | The OBC1 sprite remapper |
| [snes-rom-image-python](https://github.com/gufranco/snes-rom-image-python) | A cartridge image as a file |
| [snes-rtc-python](https://github.com/gufranco/snes-rtc-python) | The two cartridge real-time clocks |
| [snes-sdd1-python](https://github.com/gufranco/snes-sdd1-python) | The S-DD1 decompressor |
| [snes-spc7110-python](https://github.com/gufranco/snes-spc7110-python) | All three modes of the SPC7110 decompressor |
| [snes-st010-python](https://github.com/gufranco/snes-st010-python) | The two Seta coprocessors |
| [sony-s-dsp-python](https://github.com/gufranco/sony-s-dsp-python) | The Sony S-DSP, on the clock schedule the hardware runs on |
| [sony-spc700-python](https://github.com/gufranco/sony-spc700-python) | The Sony SPC700, the audio unit's processor |
| [star-ocean-nochip-fix](https://github.com/gufranco/star-ocean-nochip-fix) | One header correction, end to end |
| [zilog-z80-python](https://github.com/gufranco/zilog-z80-python) | The Z80 |

## The authority ladder

Every factual question is answered by the highest rung that has an answer, and a
lower rung never overrules a higher one.

1. **Manufacturer documentation.** Anything printed decides. Read it in full
   rather than searching it, because the passages that matter are the ones
   nobody quotes.
2. **The part's own program or the artefact itself.** A cartridge, a firmware
   image, a header. What the silicon was actually asked to do.
3. **A recording from an independent implementation**, for behaviour nobody
   documented.
4. **Nothing else.** An emulator, an FPGA core, a wiki and a forum post are rung
   3 at best and rung 4 for anything printed.

A document that contradicts itself is common. When it does, the cycle table and
the pin descriptions have both times been right and the prose wrong.

**Never calibrate against an emulator where a document exists.** A recording is
evidence about behaviour nobody wrote down. It is not evidence about a register
width, a bit name, or anything else a manufacturer printed, however many
implementations agree with it. Where a recording contradicts a document, the
document wins, the disagreement is written down, and the model follows the
document.

**A recording whose answer depends on the machine it was built on is not evidence
at all.** It is a property of the recorder, and it is excluded and named rather
than allowed to decide.

## What every repository carries

| Gate | Standard |
|:--|:--|
| Format | `ruff format --check .`, clean |
| Lint | `ruff check .`, zero findings |
| Types | `mypy` at strict plus every optional error class, zero findings |
| Tests | `<module>.test.py` beside the module, run individually |
| Coverage | 100% statement and branch, enforced, on a machine holding no artefacts |
| JSON | `pnpm run format:check`, with every submodule tree exempted |
| CI | lint, types, tests on 3.12/3.13/3.14, plus the project's own conformance job |
| Schedule | a weekly run against unpinned tools and the newest runtime, starting on ground the pipeline never reaches |
| Analysis | CodeQL and Scorecard |
| Release | semantic-release from `main`, never tagged by hand |
| Docs | README, AGENTS.md plus the one-line pointer each tool reads, CONTRIBUTING, SECURITY, CODE_OF_CONDUCT |
| Review | CODEOWNERS on every path, and templates that ask a report for the run that settles it |
| Specs | `specs/current/`, requirements with checkable scenarios |
| Hardware facts | `conformance/hardware.json`, every fact with the sentence it came from |
| Disagreements | `conformance/divergences.json`, both readings and what would settle it |

## Conventions that are not negotiable

| Thing | Rule |
|:--|:--|
| Language | Python only |
| Comments | None in source, ever. Docstrings carry the reasoning |
| Test structure | Arrange, blank line, one act, blank line, assert. No section labels |
| Nothing starts clean | Memory and registers hold what they held, from a seed |
| Artefacts | Never committed: no ROM, no firmware, no fragment of one |
| Only retail dumps | A ROM hack is somebody's edit, not what hardware ran |
| Package manager | pnpm, never npm |

## What a conformance runner must report

A runner asked about ground it has never been held to has three options and two
of them are lies. Reporting agreement lies about the part. Skipping in silence
lies about the run, because the summary then counts a comparison that never
happened. The third is to refuse: name what was compared, name what was not and
why, and count the two apart.

Report per part, never one number over parts with different evidence. One part
held to its manufacturer's manual and another held to nothing are not one figure.

## The state of this repository
## The state of this repository

**The audio rests on an emulator, and that is the largest gap here.** The
samples this model produces are checked against snes9x, which is the lowest rung
the ladder recognises. Agreement with the corpus means agreement with that
program, and where it is wrong this model is wrong with it. Recorded in
[`conformance/divergences.json`](conformance/divergences.json) with what would
settle it.

**The tables underneath the audio no longer rest on it.** Nintendo's development
manual documents the DSP as a register map and four tables of times and
frequencies, and every one of them is now pinned in
[`conformance/hardware.json`](conformance/hardware.json) and checked:

- All 32 noise clock frequencies against all 32 entries of the rate table, one
  for one, to within the two significant figures Nintendo printed. That is the
  strongest check available, because it names every entry rather than a ratio.
- All 16 attack times, which are linear and therefore absolute. Every one is
  reproduced exactly.
- Every voice register offset and every global register address.
- The eight tap filter, the eight voices, the sixteen byte stride.

**One thing the manual leaves undetermined.** Its decay and sustain columns give
times without saying what level the fall is measured to, and the sustain column
has no sustain level to measure to at all. Dividing all 39 printed figures by
this model's tick period for their rate gives 576 to 600 ticks: one endpoint, to
within four per cent across the whole table. That says the rate table reproduces
every exponential figure in relative terms and that a constant is missing rather
than a behaviour. The endpoint is recovered and recorded rather than folded into
the model.

**The interpolation kernel has no source at all.** It shapes every sample the
chip emits, it comes from the reference, and nothing in the manual describes it.
It is the one part of this model that no check here can reach.

**Nothing is claimed about timing.** The manual describes the DSP in times and
frequencies and gives no cycle count anywhere. This model produces one sample per
call and says nothing about when within a sample period a register is read.
