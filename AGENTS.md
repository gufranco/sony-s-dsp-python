# Working in this repository

Read [FAMILY.md](FAMILY.md) first. It is the standard every member of this
family carries, byte for byte, and it decides most questions before they are
asked. What follows is only what is true of this member. [README.md](README.md)
is the document written for a person.

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

`Chip(model, memory)` builds one, the shape every part in the family takes. It
arrives holding the power-on pattern. The caller calls `reset()` where the board
would pulse the line, and the constructor never does.

| Call                                     | What it does                                           |
| :--------------------------------------- | :----------------------------------------------------- |
| `clock()`                                | One of the thirty two clocks a sample is made of       |
| `read(address)`, `write(address, value)` | The register file, as a host reaches it                |
| `reset()`                                | The reset line, handed back so a caller can chain      |
| `voices`                                 | The eight, each holding its own envelope and BRR state |

## The authority ladder

1. **Nintendo's SNES Development Manual**, for the register map, the rate table
   and the attack times. Every figure is pinned with the page it came from.
2. **The thirty two step schedule**, for what happens on which step.
3. **A corpus of real game configurations**, cross-checked against a second
   implementation, for the audio itself.

The rung a Sony data sheet would occupy is empty and the record says so.

## What is settled and what is not

**Not settled: 7 things**, each in
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
uvx ruff@0.16.3 format --check .
uvx ruff@0.16.3 check .
uvx --python 3.12 --with types-setuptools==84.0.0.20260812 mypy==1.14.1
pnpm run format:check
uvx yamllint==1.38.0 --strict .
cov=(uvx --python 3.12 --from coverage==7.6.10 --with setuptools==84.0.0 coverage)
"${cov[@]}" erase
for file in $(find sdsp conformance -name '*.test.py' | sort); do
  "${cov[@]}" run -a "$file"
done
"${cov[@]}" report
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
- No comments in source, and a docstring counts as one. A step that would need
  a comment is a step that should be a named function.
- Tests sit beside the module they cover as `<module>.test.py`. Arrange, act
  and assert, each block opened by its bare marker.
- 100% statement and branch coverage, enforced. `mypy` at strict, with every
  optional error class on.
- Everything a caller can catch is defined once, in `sdsp/errors.py`, and
  imported from there.
- A check nobody has seen fail is not known to work. Drive every new check
  against input that should fail it before keeping it.

The linter's ignores in [`pyproject.toml`](pyproject.toml) carry no comments, so
their reasons live here:

- `N818`: some exceptions are control flow signals rather than failures. The
  standard library names those without the suffix too, and the ones that report
  a failure do end in `Error`.
- `N999` in tests: a test file sits beside its module and is named after it with
  a dot, so a module and its tests are read together.
- `T201` in `conformance/`: these are command line tools, and printing is their
  output.
- `BLE001` and `T201` in `environment.py`: a check that throws has to become a
  line in the report rather than end the run, and the report is the product.
- `BLE001` and `T201` in the doctor: it has to survive whatever a check throws
  and report it. A narrower catch would let a traceback take the rest of the
  report with it.

The coverage exclusions carry none either:

- `if __name__ == "__main__":`: the guard hands argv to a function that is
  itself tested, and importing the module to cover it would run the tool.
- `if TYPE_CHECKING:`: the block never runs. Python 3.14 drops it before
  coverage sees it and earlier versions do not, so counting it would make the
  gate mean something different on each runtime.
- `^\s*\.\.\.$` and `: \.\.\.$`: a protocol method's ellipsis is a contract the
  type checker reads and the runtime never runs.
- `@unittest\.skipUnless\(CLOCKED,` in the coverage exclusions: this member is
  not a clocked part, so the family tests that drive a clock are skipped here
  and their bodies never run.
- `@unittest\.skipUnless\(SOLD_AS_A_COMPONENT,`, `^def machine_mentions\(` and
  `^def listing\(` in the coverage exclusions: this part only existed inside one
  machine, so the family sweep for machine names is skipped here.

The formatter's ignores in [`.prettierignore`](.prettierignore) carry no
comments either, so their reasons live here:

- `pnpm-lock.yaml` and `package-lock.json`: the package manager writes them, in
  its own layout, on every install.
- `node_modules/`, `.venv/`, `venv/`, `build/`, `dist/` and `*.egg-info/`:
  installed or built, never written by hand.
- `.coverage`, `coverage.json`, `htmlcov/` and the tool caches: the output of a
  run, never committed.
- `docs/`, `specs/`, `.work/` and `.claude/`: local working material, never
  committed.

## Layout

```text
sdsp/
  __init__.py    the package, and the part chosen at construction
  core.py        the eight voices, and the thirty two step schedule
  voice.py       one voice, scrambled at power on and defined by a reset
  state.py       everything else the part holds, the same two ways
  echo.py        the echo unit's steps of the schedule
  words.py       clamping and sign extension
  memory.py      the store the part reads samples out of
  models.py      the catalogue, and the names the part answers to
  tables.py      the rate table, the counter offsets and the gaussian kernel
  errors.py      everything this package raises, in one place
  doctor.py      what is actually on this machine, printed for a bug report
  version.py     rewritten by the release job and by nothing else
conformance/
  family_*.test.py the family standard, held to this repository, one topic a file
  family_member.py what this member answers to them
  family_shared.py what more than one of them reads
  corpus.json    real game configurations, and what they produce
  corpus.py      replaying them and comparing sample for sample
  capture.py     reading dumps a reader owns, to add to the corpus
  hardware.json  what Nintendo printed, fact by fact, with the page
  divergences.json where sources part, and what would settle each
  quotes.py      looks for every quoted sentence in the document it cites
  register_rig.py a part wired the way the register tests drive it
  speed.py       the throughput floor
  ref/           the reference driver, built rather than vendored
```

## Things that will bite you

- **The interpolation kernel is the one table no digest can settle.** Every other
  artifact this family reads is a file with a manifest behind it. This one is on
  the die, has never been dumped, and circulates as a printed table of numbers.
  A caller may hand their own in as `Chip(model, memory, gaussian=...)`, where
  `check_kernel` holds it to the length, the shape and the four-tap identity.
  That is weaker than a digest and the readme says so rather than blurring the
  two: two different tables can pass it. Never add a digest here as though one
  existed.
- **The kernel is held on the part, not on the module.** Rebinding
  `tables.GAUSSIAN` would make the last constructor win for every part in the
  process. Holding it on the instance costs nothing measurable, which was
  measured rather than assumed: -0.4% against the module global over five
  alternating rounds, inside a run-to-run spread of about 2%.
- **The part comes up scrambled.** Every register, counter, latch and voice
  holds a pattern derived from a seed, not zero and not what a reset sets,
  because no machine hands over a defined part. The noise generator is drawn
  from everything but 0, which it could never leave. `reset()` is a separate
  event and sets what `resetLine` in the record lists, and nothing calls it for
  you: a test, a runner or an example that wants the defined state calls it
  itself. A new field goes in both the power-on draw and the reset, in
  `state.py` or `voice.py`, and in that list. Tests reach the part only through
  its public interface, so a voice field the reset misses fails the voice reset
  test, and a part field it misses fails only once it reaches the output: parts
  powered on from different seeds, reset and driven alike, must play alike.
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
