<div align="center">

<h1>S-DSP</h1>

<strong>A model of the Sony S-DSP that runs on the clock schedule the hardware runs on.</strong>

<br>
<br>

[![CI](https://github.com/gufranco/sony-s-dsp-python/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/sony-s-dsp-python/actions/workflows/ci.yml)
[![Corpus](https://img.shields.io/badge/corpus-240%20%2F%20240-brightgreen)](#the-corpus-and-why-it-can-ship)
[![Coverage](https://img.shields.io/badge/coverage-100%25%20statement%20%2B%20branch-brightgreen)](#tests)
[![Python](https://img.shields.io/badge/python-3.12%20%7C%203.13%20%7C%203.14-blue)](pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

</div>

<p align="center">
  <a href="#quick-start">Quick start</a> &nbsp;|&nbsp;
  <a href="#the-thirty-two-clock-schedule">The schedule</a> &nbsp;|&nbsp;
  <a href="#the-corpus-and-why-it-can-ship">Why the corpus is legal</a> &nbsp;|&nbsp;
  <a href="#how-this-is-proved">How this is proved</a> &nbsp;|&nbsp;
  <a href="https://github.com/gufranco/sony-s-dsp-python/issues">Issues</a>
</p>

**8** voices · **32** clocks per sample · every **rate**, every **attack time** and every **register address** checked against Nintendo's own tables · **240** cases from real game configurations, **0** failures · **15,360** samples cross-checked · **531** tests · **100%** statement and branch coverage · no dependencies

```python
from sdsp import Chip, Memory

dsp = Chip("s-dsp", Memory())
dsp.write(0x6C, 0x20)

len(dsp.render(64))

# 128, two channels per sample
```

---

## Install
```bash
pip install git+https://github.com/gufranco/sony-s-dsp-python.git
```

Python 3.12 or newer. Nothing else.

## The interface
Everything a caller touches. Nothing else is public.

| Name | What it is |
|:--|:--|
| `Chip(model, memory)` | A part of that model, on a store it builds when one is not handed over |
| `Memory`, `SparseMemory` | Flat memory, and the same promise without the allocation |
| `describe(model)`, `MODELS`, `Model` | The catalogue, without building anything |
| `clock()` | One of the thirty two clocks a sample is made of |
| `read(address)`, `write(address, value)` | The register file, as a host reaches it |
| `reset()` | The reset line, handed back so a caller can chain |
| `Voice` | One of the eight, and what it holds |
| `PIPELINE`, `VOICE_COUNT`, `REGISTER_COUNT` | The schedule, and the two counts it runs over |
| `COUNTER_RATES`, `COUNTER_OFFSETS`, `GAUSSIAN` | The tables the part works from |
| `ENV_ATTACK`, `ENV_DECAY`, `ENV_SUSTAIN`, `ENV_RELEASE` | The four envelope phases, by name |
| `scramble`, `UNSET_SEED` | The pattern the registers come up holding |
| `UnknownModelError` | No part goes by that name |

`Chip` takes the model first, which is the argument every member of the family
takes first, and the name is the kind rather than the chip.

```python
from sdsp import Chip, describe

describe("s-dsp").name

# 's-dsp'
```

A name no part answers to is refused rather than quietly building the only one
there is:

```python
from sdsp import Chip, UnknownModelError

try:
    Chip("ym2612")
except UnknownModelError as refused:
    print(str(refused).split(";")[0])

# ym2612 is not a part this package covers
```

## The problem
The S-DSP looks like eight independent voices summed together. It is not.

Its eight voices are **pipelined across thirty two clocks**, so at any moment one voice is fetching its sample pointer, another is decoding a block, and a third is writing a register. A voice under pitch modulation reads the previous voice's output from whichever clock it happens to land on. Key-on is sampled every *other* sample. The end-of-sample flag reaches its register two clocks after the voice that raised it.

Write it as a loop over voices and everything above quietly changes. The result still sounds like music, which is exactly the problem: it is wrong in ways that only appear when a real driver is doing something clever.

## The solution
Run the schedule the hardware runs, one clock at a time.

`PIPELINE` in [`sdsp/core.py`](sdsp/core.py) is that ordering, taken from the hardware, with one entry per clock naming which step runs for which voice. The model then steps it and nothing else.

Correctness is measured against the reference implementation, and the schedule is where measurement earned its keep: a first attempt with the voice indices off by one passed every single-voice test, every envelope test and every echo test, and diverged the moment a second voice joined.

<table>
<tr>
<td width="50%" valign="top">

### The real schedule, not a loop

Thirty two clocks, voices pipelined. The ordering is data in one table rather than control flow spread through the code.

</td>
<td width="50%" valign="top">

### Real game configurations

The corpus carries DSP register states lifted from **240** music dumps: real envelope rates, real echo delays, real filter taps.

</td>
</tr>
<tr>
<td width="50%" valign="top">

### Cross-checked, not self-checked

Expected audio comes from the reference chip. Nothing here grades its own homework.

</td>
<td width="50%" valign="top">

### Ships no music

The audio RAM of every dump is skipped rather than read. What travels is how the chip was driven.

</td>
</tr>
</table>

## The thirty two clock schedule
Every sample is thirty two clocks, and the work of the eight voices is spread across them. Reading the table down the page is the fastest way to see why a loop cannot stand in for it:

| Clock | What runs |
|------:|:----------|
| 17 | voice 0 fetches its pointer, voice 5 mixes left, voice 6 writes its output register |
| 21 | voice 6 writes, voice 7 mixes right, voice 0 reads its sample pointer |
| 30 | the key-on latch updates, voice 0 interpolates and runs its envelope, the echo writes right |

Three different voices, three different stages, one sample. The full table is `PIPELINE` in [`sdsp/core.py`](sdsp/core.py).

> [!NOTE]
> The composite steps are the trap. `V7_V4_V1(n)` means voice `n` does step 7, voice `n+3` does step 1, and voice `n+1` does step 4, in that order. Reading it as `n`, `n+1`, `n+2` gives a model that agrees on one voice and drifts on eight.

## Models
```python
from sdsp import Chip, Memory, describe

describe("snes-dsp").voices

# 8

dsp = Chip("s-dsp", Memory())
```

| Model | Voices | Registers | Notes |
|:------|:------:|:---------:|:------|
| `s-dsp` | 8 | 128 | Aliases: `sdsp`, `sonysdsp`, `dsp`, `snesdsp` |

> [!NOTE]
> One part, one behaviour. Sony built it into the S-SMP beside the SPC700 and never sold it separately, so there is no family of revisions to model.

## Is it right
| What | Oracle | Strength |
|:-----|:-------|:---------|
| Register map | Nintendo's table 3-7-1 | Manufacturer, exhaustive |
| Rate table | Nintendo's noise clock table 3-7-4, all 32 rows | Manufacturer, exhaustive |
| Attack times | Nintendo's table 3-7-2, all 16 rows | Manufacturer, exhaustive |
| Decay and sustain | Nintendo's table 3-7-2, all 39 rows, relative to one endpoint the manual omits | Manufacturer, relative |
| Whole chip | 15,360 samples against snes9x's `SPC_DSP.cpp` | An emulator, which is the weakest rung here |
| Real configurations | 240 register states from real music dumps | Shaped by hardware |
| BRR filters | All four filters, every shift including the clamped range | Behavioural |
| Envelopes | ADSR plus all four gain modes | Behavioural |
| Echo | Eight tap filter, feedback, buffer wrap, write suppression | Behavioural |
| Interpolation kernel | Verified monotonic, and its four taps sum to one unit at every position | Structural, exhaustive |
| Counter rates | Verified to divide the counter period, offsets verified to stagger | Structural, exhaustive |

### Where the facts come from

Two sources, and they are not equally strong. Saying which is which is the point
of this section.

**Nintendo's SNES Development Manual** documents the DSP as a register map and
four tables of times and frequencies. [`conformance/hardware.json`](conformance/hardware.json)
pins all of them with the page each was read from, and
[`conformance/hardware.test.py`](conformance/hardware.test.py) holds this model
to them. That covers every register address, every one of the 32 rate table
entries, and every attack time.

**snes9x** decides the rest, which is the audio itself. That is an emulator, and
agreement with it means agreement with that program rather than with the chip.
[`conformance/divergences.json`](conformance/divergences.json) says so as its
first and highest-severity entry, along with what a real recording would settle.

> [!NOTE]
> The manual's OCR text layer interleaves the table columns. Every figure was
> read off a rendered page image instead.

### The strongest check here is the noise clock

Table 3-7-4 gives a frequency for each of the 32 values of the noise clock
field. Each one is 32000 divided by one entry of the rate table this whole model
is built around, so the table is pinned entry by entry rather than by the ratios
between its entries. All 32 agree to the two significant figures Nintendo prints
them at.

The attack column pins the same table a second way, and absolutely: the step is
one sixty fourth, so a climb takes 64 ticks, and all 16 printed times come out
right.

### One number the manual leaves out

Its decay and sustain columns give times without saying what level the fall is
measured to, and the sustain column has no sustain level to measure to at all.

Dividing each of the 39 printed figures by this model's tick period for that rate
gives between 576 and 600 ticks. One endpoint, to within four per cent across the
whole table. That says the rate table reproduces every exponential figure and
that what is missing is a constant rather than a behaviour.

The constant is recovered and written down rather than folded into the model,
because a number nobody printed is not a fact.

### The corpus, and why it can ship

An SPC dump is a snapshot of a running audio unit, and it holds two very different things.

| Part of a dump | What it is | Ships? |
|:---------------|:-----------|:-------|
| The 64 KB audio RAM | BRR samples and sequence data. The music | Never |
| The 128 DSP registers | Volumes, pitches, envelope rates, echo taps, which voices feed the echo | Yes |

The registers are the parameters a driver poked into a peripheral. They describe *how the chip was driven* rather than what was played, and without the samples they reproduce nothing. Functional elements sit outside what copyright reaches, per [17 U.S.C. 102(b)](https://www.law.cornell.edu/uscode/text/17/102). [`conformance/capture.py`](conformance/capture.py) reads only that block and seeks past the audio rather than loading it.

So [`conformance/corpus.json`](conformance/corpus.json) is built in three steps:

1. **Configurations taken from real dumps.** 240 register states covering **70** sample directory pages, **11** distinct echo delays and **1,402** voices running envelopes.
2. **Sample data generated from a seed**, laid out so the directory sits where the real registers point and each voice finds blocks where its source number says.
3. **Audio computed by the reference chip**, not by this implementation.

This matters more than it might sound. A random generator picks an envelope rate uniformly; a composer does not. Real rates cluster where instruments sit, real echo delays are chosen deliberately, real filter taps are mostly zero until they are not, and real drivers key voices on in patterns nothing random produces.

> [!IMPORTANT]
> This is how the repository is built, not legal advice. The rule it follows is short enough to restate: publish behaviour, never content.

### Reading dumps of your own

```bash
python3 -m conformance.capture "/path/to/spc/collection" census.json 500

#   500 register states from /path/to/spc/collection

#   81 sample directory pages, 2372 voices on envelopes

#   written to census.json
```

The census stays on your machine, and so does anything you build from it with real sample data.

**Open questions** are listed with the measurement that would close each one:
[`OPEN-QUESTIONS.md`](OPEN-QUESTIONS.md). Where two sources part, both are kept
in [`conformance/divergences.json`](conformance/divergences.json) with what would
settle it.

## Working on it
```bash
python -m coverage erase
for file in $(find sdsp conformance -name '*.test.py' | sort); do
  python -m coverage run -a "$file"
done
python -m coverage report
```

`python3 sdsp/doctor.py` says what is actually on this machine. It is run as a file rather than with `-m` so that it still runs when the package itself will not import, which is the case it exists for.

[`AGENTS.md`](AGENTS.md) is the document for an agent working here. [`FAMILY.md`](FAMILY.md) is the standard this repository shares with the rest of the family, kept identical in every member.

### Project structure

```
sdsp/
  __init__.py     the package, and the model chosen at construction
  core.py         the DSP, and the clock schedule it runs on
  tables.py       the interpolation kernel and the counter rates
  memory.py       audio RAM that holds what it held
  models.py       what each part is
  version.py      rewritten by the release job and by nothing else
conformance/
  corpus.py       replays the corpus and reports what disagreed
  corpus.json     240 real configurations with reference audio
  hardware.json     Nintendo's tables, pinned table by table
  hardware.test.py  this model's rates and addresses against those tables
  divergences.json  every place a source is weak, and what would strengthen it
  capture.py      reads register states out of dumps you own
  ref/            the reference driver, built around the chip's own C source
```

Each module has its tests beside it as `<module>.test.py`.

### Tests

```bash
for f in sdsp/*.test.py conformance/*.test.py; do python3 "$f"; done
```

| Suite | File | Covers |
|:------|:-----|:-------|
| Core | [`sdsp/core.test.py`](sdsp/core.test.py) | Reset, registers, the schedule, voices, envelopes, noise, echo |
| Tables | [`sdsp/tables.test.py`](sdsp/tables.test.py) | Kernel shape and unit sum, counter rates and stagger |
| Memory | [`sdsp/memory.test.py`](sdsp/memory.test.py) | Scrambled fills, sparse derivation, wrapping, seeding |
| Models | [`sdsp/models.test.py`](sdsp/models.test.py) | The catalogue, alias matching, construction |
| Corpus | [`conformance/corpus.test.py`](conformance/corpus.test.py) | The whole shipped set, sample layout, reporting |
| Capture | [`conformance/capture.test.py`](conformance/capture.test.py) | Dump parsing, the census, and that no audio is read |
| Tables against Nintendo | [`conformance/hardware.test.py`](conformance/hardware.test.py) | Every register address, all 32 noise clock rows, all 16 attack times, and the endpoint the manual omits |

Coverage is enforced at 100% of statements and branches by [`pyproject.toml`](pyproject.toml).

### Development

| Command | Description |
|:--------|:------------|
| `ruff format .` | Format |
| `ruff check .` | Lint |
| `mypy` | Types, strict |
| `python3 -m coverage report` | Coverage, which fails below 100% |
| `python3 -m conformance.corpus [file]` | Run the corpus |
| `python3 -m conformance.capture <dir> <out> [limit]` | Read dumps you own |

### Versioning

This project follows [Semantic Versioning](https://semver.org/), and every release is tagged from `main` by semantic-release. See [releases](https://github.com/gufranco/sony-s-dsp-python/releases).

> [!IMPORTANT]
> While the version is below `1.0.0`, the public interface may change on a minor release.

### FAQ

<details>
<summary><strong>Does this include the SPC700 processor?</strong></summary>
<br>

No. The SPC700 is the CPU that drives this chip and lives in [`sony-spc700-python`](https://github.com/gufranco/sony-spc700-python). Keeping them apart is what lets each be tested against its own oracle: the processor against a per-instruction suite, the DSP against rendered audio.

</details>

<details>
<summary><strong>Is it sample accurate or cycle accurate?</strong></summary>
<br>

It runs the thirty two clock schedule, so register effects land on the clock they land on, and the output is verified sample for sample against the reference. It does not model the SPC700 bus timing around it, because that belongs to the processor.

</details>

<details>
<summary><strong>Why does the corpus use generated samples instead of real ones?</strong></summary>
<br>

Because real ones are the music. The register states are what carry the behaviour worth testing, and they drive generated samples perfectly well. If you want the full check with real audio, run it locally against dumps you own.

</details>

### When something is wrong

```bash
python3 -m sdsp.doctor
```

It looks at this machine and prints what is actually there, and every line is
something it looked at just now rather than something that ought to be true. A
check that fails says what it saw. A check that itself throws is reported as what
it threw rather than taking the report down with it. Paste all of it into an
issue.

### Contributing

Measurements first. [CONTRIBUTING.md](CONTRIBUTING.md) has the gates a change is
expected to pass, [SECURITY.md](SECURITY.md) says what belongs in a private
report, and the [Code of Conduct](CODE_OF_CONDUCT.md) applies wherever this
project is discussed.

Never attach a copyrighted file, and never link to somewhere one can be
downloaded. A digest identifies a file without carrying it.

## References
This repository carries no documents. Every claim is traced to something
published elsewhere, listed here so a reader can fetch the same file and check
the same page.

Sony published no data sheet for this part. The rung a data sheet would occupy on
the authority ladder is empty, and
[`conformance/hardware.json`](conformance/hardware.json) says so rather than
promoting the rung below it.

| Document | Used for |
|:---------|:---------|
| Nintendo of America Inc., *SNES Development Manual, Book 2* | The register map, the rate table and the attack times, quoted with the page each came from |

| Source | Used for |
|:-------|:---------|
| The corpus in [`conformance/corpus.json`](conformance/corpus.json) | Real game configurations, cross-checked sample for sample |

## Citing this
[CITATION.cff](CITATION.cff) is kept in step with the released version by the
same script that stamps the package, so the version it names is the version that
shipped.

## License
[MIT](LICENSE)
