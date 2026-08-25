# Working in this repository

This file is for a coding agent. A person reading it will not be harmed, but
[README.md](README.md) is the document written for them.

## What this project is, in one paragraph

The S-DSP: the sound generator Sony put in the SNES audio unit, eight voices with
envelopes, echo and gaussian resampling. What makes this model different from a
description of the part is that it runs the schedule the hardware runs: a sample
is thirty two clocks in a fixed order, and this does the same thirty two in the
same order rather than computing a sample and calling it done. That is what makes
a register read taken mid sample answer what the hardware answers. Sony published
no data sheet; Nintendo's manual gives the registers and the parameter tables,
and the audio itself rests on a corpus cross-checked against a second
implementation.

## The interface a caller drives

The part answers accesses. Nothing a host does to it is measured in cycles, so
none of the family's clocked interface appears here. The thirty two steps are the
part's own schedule rather than a caller's budget.

`Chip(model, memory)` builds one, the shape every part in the family takes.

| Call | What it does |
|:--|:--|
| `clock()` | One of the thirty two clocks a sample is made of |
| `read(address)`, `write(address, value)` | The register file, as a host reaches it |
| `reset()` | The reset line, handed back so a caller can chain |
| `voices` | The eight, each holding its own envelope and BRR state |

## The authority ladder

1. **Nintendo's SNES Development Manual**, for the register map, the rate table
   and the attack times. Every figure is pinned with the page it came from.
2. **The thirty two step schedule**, for what happens on which step.
3. **A corpus of real game configurations**, cross-checked against a second
   implementation, for the audio itself.

The rung a Sony data sheet would occupy is empty and the record says so.

## What is settled and what is not

**Not settled: 6 things**, each in
[OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) with the measurement that would close it.
The sharpest is that every sample rests on agreement between two
implementations, which is not a measurement of silicon. The gaussian kernel is
carried rather than derived, because nothing published derives it.

Settled: every rate, every attack time and every register address, against
Nintendo's tables; and the order of the thirty two steps, which is what this
model exists to get right.

## The schedule is the point

`PIPELINE` at the bottom of `sdsp/core.py` is the ordering, one entry per clock.
A change that computes the same sample in a different order is not a smaller
change; it is a different part. Anything that touches the schedule needs the
corpus run, not just the unit tests.

## Every gate, in the order to run them

```bash
ruff format --check .
ruff check .
mypy
pnpm run format:check
python3 -m coverage erase
for file in $(find sdsp conformance -name '*.test.py' | sort); do
  python3 -m coverage run -a "$file"
done
python3 -m coverage report
```

Then the throughput floor, which runs outside the coverage step because a tracer
costs about ten times what the model does:

```bash
python3 -m conformance.speed
```

And the runs that report what they could not check rather than passing quietly:

```bash
python3 sdsp/doctor.py
python3 -m conformance.quotes
python3 -m conformance.corpus
```

Everything under `conformance/` runs as a module. Run as a script, its own
directory goes on the import path and a file there shadows any standard library
module of the same name. `doctor.py` is the exception and runs as a file on
purpose, so that it still runs when the package itself will not import, which is
the case it exists for.

## Conventions that are not negotiable

- Python only, standard library only, no dependencies.
- No comments in source. Reasoning goes in docstrings, and a step that would need
  a comment is a step that should be a named function.
- Tests sit beside the module they cover as `<module>.test.py`. Arrange, blank
  line, one act, blank line, assert, with no section labels.
- 100% statement and branch coverage, enforced. `mypy` at strict, with every
  optional error class on.
- Everything a caller can catch is defined once, in `sdsp/errors.py`, and
  imported from there.
- A check nobody has seen fail is not known to work. Drive every new check
  against input that should fail it before keeping it.

## Layout

```text
sdsp/
  __init__.py    the package, and the part chosen at construction
  core.py        the eight voices, and the thirty two step schedule
  memory.py      the store the part reads samples out of
  models.py      the catalogue, and the names the part answers to
  tables.py      the rate table, the counter offsets and the gaussian kernel
  errors.py      everything this package raises, in one place
  doctor.py      what is actually on this machine, printed for a bug report
  version.py     rewritten by the release job and by nothing else
conformance/
  family.test.py the family standard, held to this repository
  corpus.json    real game configurations, and what they produce
  corpus.py      replaying them and comparing sample for sample
  capture.py     reading dumps a reader owns, to add to the corpus
  hardware.json  what Nintendo printed, fact by fact, with the page
  divergences.json where sources part, and what would settle each
  quotes.py      looks for every quoted sentence in the document it cites
  speed.py       the throughput floor
  ref/           the reference driver, built rather than vendored
```

## Things that will bite you

- **The schedule is not an implementation detail.** See above.
- **The part comes up scrambled.** Registers hold a pattern derived from a seed,
  not zero, because no machine hands over cleared registers. `reset()` is a
  separate event and does a different thing.
- **The corpus is the only source for the audio.** A change that alters output
  and still passes the unit tests has not been checked at all until the corpus
  runs.
- **The reference driver is not vendored.** It is built from a pinned commit, and
  a machine without a C++ compiler skips that step and says so.

## Before calling anything finished

Every gate above, green, with output shown. A claim without a run behind it is
not evidence. If a check was skipped because a file is not on this machine, say
which check and why rather than reporting a pass.

## What a change is expected to leave behind

A test that fails without the change and passes with it. An entry in
[OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) if it turned a settled thing into an open
one, or removed one. A record entry with the sentence and the page if it added a
fact from the manual.
