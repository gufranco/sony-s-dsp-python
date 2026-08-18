<div align="center">

<h1>sdsp</h1>

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

**8** voices · **32** clocks per sample · **240** cases from real game configurations, **0** failures · **15,360** samples cross-checked · **130** tests · **100%** statement and branch coverage

```python
from sdsp import Sdsp, Memory

dsp = Sdsp(Memory(), model="s-dsp")
dsp.write(0x6C, 0x20)

len(dsp.render(64))
# 128, two channels per sample
```

---

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

## Quick start

### Prerequisites

| Tool | Version | Install |
|:-----|:--------|:--------|
| Python | >= 3.12 | [python.org](https://www.python.org/downloads/) |

### Setup

```bash
git clone https://github.com/gufranco/sony-s-dsp-python.git
cd sony-s-dsp-python
```

### Verify

```bash
python3 conformance/corpus.py
#   240 cases from conformance/corpus.json, against snes9x 1.63 SPC_DSP.cpp
#   configurations from 240 music dumps, 70 sample directory pages
#   240 agreed, 0 did not
```

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

## The corpus, and why it can ship

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
python3 conformance/capture.py "/path/to/spc/collection" census.json 500
#   500 register states from /path/to/spc/collection
#   81 sample directory pages, 2372 voices on envelopes
#   written to census.json
```

The census stays on your machine, and so does anything you build from it with real sample data.

## How this is proved

| What | Oracle | Strength |
|:-----|:-------|:---------|
| Whole chip | 15,360 samples against snes9x's `SPC_DSP.cpp` | Cross-checked, independent implementation |
| Real configurations | 240 register states from real music dumps | Shaped by hardware |
| BRR filters | All four filters, every shift including the clamped range | Behavioural |
| Envelopes | ADSR plus all four gain modes | Behavioural |
| Echo | Eight tap filter, feedback, buffer wrap, write suppression | Behavioural |
| Interpolation kernel | Verified monotonic, and its four taps sum to one unit at every position | Structural, exhaustive |
| Counter rates | Verified to divide the counter period, offsets verified to stagger | Structural, exhaustive |

## Models

```python
from sdsp import Sdsp, Memory, describe

describe("snes-dsp").voices
# 8

dsp = Sdsp(Memory(), model="s-dsp")
```

| Model | Voices | Registers | Notes |
|:------|:------:|:---------:|:------|
| `s-dsp` | 8 | 128 | Aliases: `sdsp`, `sonysdsp`, `dsp`, `snesdsp` |

> [!NOTE]
> One part, one behaviour. Sony built it into the S-SMP beside the SPC700 and never sold it separately, so there is no family of revisions to model.

## Project structure

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
  capture.py      reads register states out of dumps you own
  ref/            the reference driver, built around the chip's own C source
```

Each module has its tests beside it as `<module>.test.py`.

## Tests

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

Coverage is enforced at 100% of statements and branches by [`pyproject.toml`](pyproject.toml).

## Development

| Command | Description |
|:--------|:------------|
| `ruff format .` | Format |
| `ruff check .` | Lint |
| `python3 -m coverage report` | Coverage, which fails below 100% |
| `python3 conformance/corpus.py [file]` | Run the corpus |
| `python3 conformance/capture.py <dir> <out> [limit]` | Read dumps you own |

## Versioning

This project follows [Semantic Versioning](https://semver.org/), and every release is tagged from `main` by semantic-release. See [releases](https://github.com/gufranco/sony-s-dsp-python/releases).

> [!IMPORTANT]
> While the version is below `1.0.0`, the public interface may change on a minor release.

## FAQ

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

## License

[MIT](LICENSE)
