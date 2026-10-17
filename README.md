# S-DSP

The Sony S-DSP sound generator in Python, run on the thirty two clock schedule the part runs on and held to the register map and parameter tables in Nintendo's SNES Development Manual.

English | [日本語](README.ja.md) | [简体中文](README.zh-Hans.md) | [繁體中文（香港）](README.zh-HK.md)

[![CI](https://github.com/gufranco/sony-s-dsp-python/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/sony-s-dsp-python/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/gufranco/sony-s-dsp-python)](https://github.com/gufranco/sony-s-dsp-python/releases)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**240** register states from real music dumps replayed for **23,040** samples, **0** failures against `snes_spc 0.9.0`, **97** of **104** checks taken on a console agree, **28** quotes located in the manual, **814** tests, **100%** statement and branch coverage, no dependencies

```python
import sdsp

dsp = sdsp.Chip("s-dsp", sdsp.Memory(fill=0)).reset()

for address, value in {0x0200: 0x00, 0x0201: 0x03, 0x0202: 0x00, 0x0203: 0x03}.items():
    dsp.memory.write8(address, value)
dsp.memory.write8(0x0300, 0xB3)
for offset in range(1, 9):
    dsp.memory.write8(0x0300 + offset, 0x77)

voice = {0x00: 0x7F, 0x01: 0x7F, 0x02: 0x00, 0x03: 0x10, 0x04: 0x00, 0x05: 0x8F, 0x06: 0xE0}
chip = {0x0C: 0x7F, 0x1C: 0x7F, 0x5D: 0x02, 0x6C: 0x20, 0x4C: 0x01}
for register, value in {**voice, **chip}.items():
    dsp.write(register, value)

print(dsp.render(16)[0::2])
print(f"ENVX {dsp.read(0x08):#04x}, OUTX {dsp.read(0x09):#04x}, ENDX {dsp.read(0x7C):#04x}")
```

```
[0, 0, 0, 0, 0, 0, 0, 0, 7057, 14110, 14110, 14110, 14110, 14110, 14110, 14110]
ENVX 0x7f, OUTX 0x37, ENDX 0x01
```

The sample directory at page `$02` points source 0 at one BRR block at `$0300`. Its header `$B3` sets shift 11, filter 0, and the end and loop flags, so the block repeats one value. Voice 0 plays it at pitch `$1000`, which is one sample out per sample in, with ADSR on and attack rate F. `FLG` is `$20`, which clears the reset and mute bits and leaves echo writes off. The example prints the left channel of 16 samples. The first 8 are silent because KON is read on every other sample and a keyed voice then waits 5 samples before it decodes. Attack rate F adds `$400` per step, so the envelope reaches half on sample 8 and full on sample 9. ENDX bit 0 is set because the block carried the end flag.

## Install

| Requirement | Version |
|:--|:--|
| Python | 3.12 or newer |
| git | Any |
| Docker | Only to rebuild the reference driver from [`conformance/ref/Dockerfile`](conformance/ref/Dockerfile) |

```bash
git clone https://github.com/gufranco/sony-s-dsp-python.git
cd sony-s-dsp-python
python3 sdsp/doctor.py
```

The package imports nothing outside the standard library. [`conformance/corpus.json`](conformance/corpus.json) is tracked, so the corpus runs on a fresh checkout.

The doctor checks the machine and the checkout, builds the part, reads one unwritten address, digests the corpus and ends with one line. It exits 0 when every check passes and 1 otherwise. Paste its whole output into any bug report.

```
  7 checks, nothing to report
```

An installed copy has the same report as `sdsp-doctor`.

Releases follow [Semantic Versioning](https://semver.org/) and are cut from the commit history by semantic-release. Every release is tagged and listed on the [releases page](https://github.com/gufranco/sony-s-dsp-python/releases).

## The interface

`sdsp.Chip(model, memory=None, seed=UNSET_SEED, gaussian=None)` builds one part. `model` is required. `memory` is any object with `read8(address)` and `write8(address, value)`, and the part builds a `SparseMemory` when it is left out. `seed` sets the power-on pattern of every register, counter, latch, decoded sample and position, which the part holds until the caller calls `reset()`. The noise generator is never drawn as 0, the one value its feedback cannot leave. The constructor never calls `reset()`, and no option makes it. `gaussian` replaces the interpolation kernel with a table of your own, checked by `check_kernel`.

| Model | Aliases | Voices | Registers |
|:--|:--|:--|:--|
| `s-dsp` | `sdsp`, `sonysdsp`, `dsp`, `snesdsp` | 8 | 128 |

A name is matched with case, hyphens and underscores ignored, so `SNES-DSP` builds `s-dsp`.

### Calls

| Call | Effect |
|:--|:--|
| `read(address)` | Returns the register at `address & $7F` |
| `write(address, value)` | Stores `value & $FF` at `address & $7F`. A write to KON is latched for the next KON sample. A write to ENDX clears it to 0 |
| `reset()` | What the reset line does in `snes_spc`, the implementation the corpus was recorded from: clears every register and every latch, sets `FLG` to `$E0`, the noise generator to `$4000` and the every-other-sample toggle to 1, and silences all eight voices. Returns the part |
| `clock()` | Runs the steps `PIPELINE` names for the current clock and moves to the next of the 32 |
| `run(clocks)` | `clock()` that many times |
| `render(samples)` | Runs `samples` times 32 clocks and returns the output as left and right values interleaved, two per sample |
| `voice_1` to `voice_9`, `voice_3a`, `voice_3b`, `voice_3c`, `misc_27` to `misc_30`, `echo_22` to `echo_30` | The steps `PIPELINE` names. `clock()` calls them; a caller does not need to |

### State

| Attribute | Meaning |
|:--|:--|
| `model` | The canonical model name |
| `memory` | The 64 KB audio RAM object the voices and the echo buffer read and write |
| `registers` | The 128 registers as a `bytearray` |
| `voices` | The eight `Voice` objects |
| `phase` | Which of the 32 clocks runs next, 0 to 31 |
| `rendered` | The output values produced since the last `render` |
| `gaussian` | The kernel this part resamples through |

A `Voice` holds `index`, `bit`, `base`, its BRR state in `brr_address`, `brr_offset`, `buffer` and `buffer_position`, its pitch position in `interpolation`, its envelope in `envelope`, `hidden_envelope`, `envelope_mode` and `envelope_out`, and `key_on_delay`.

```python
import sdsp

for name, model in sdsp.MODELS.items():
    print(name, model.aliases, model.voices, model.registers)

print(sdsp.Chip("SNES-DSP").model)

for name in (None, "ym2612"):
    try:
        sdsp.Chip(name)
    except sdsp.UnknownModelError as error:
        print(error)
```

```
s-dsp ('sdsp', 'sonysdsp', 'dsp', 'snesdsp') 8 128
s-dsp
no model was named, and this package will not choose one for you. Name one of: s-dsp
ym2612 is not a model this package covers; it has s-dsp
```

```python
import sdsp

dsp = sdsp.Chip("s-dsp")
print(f"{dsp.read(0x6C):#04x} {dsp.read(0x7C):#04x} {dsp.read(0xEC):#04x}")
print(dsp.reset() is dsp, f"{dsp.read(0x6C):#04x} {dsp.read(0x7C):#04x}")

dsp.write(0x7C, 0xFF)
dsp.write(0x13, 0x1234)
print(
    f"{dsp.read(0x7C):#04x} {dsp.read(0x13):#04x}", dsp.phase, len(dsp.voices), dsp.voices[3].base
)
```

```
0x25 0x27 0x25
True 0xe0 0x00
0x00 0x34 0 8 48
```

Before the reset the registers hold the scrambled pattern, and address `$EC` reads the same register as `$6C`. After it `FLG` holds `$E0`. A write to ENDX clears it, and a value wider than a byte keeps its low 8 bits. Voice 3's registers start at `$30`.

### Module contents

| Name | Content |
|:--|:--|
| `sdsp.MODELS` | The `Model` records, keyed by canonical name |
| `sdsp.Model` | A model record: `name`, `summary`, `voices`, `registers`, `aliases`, and `build(memory, **options)` |
| `sdsp.Memory(size=0x10000, fill=None, seed=UNSET_SEED)` | Flat audio RAM. `fill` is a byte value or a byte string, and without it the contents are scrambled from `seed`. Addresses wrap at 16 bits |
| `sdsp.SparseMemory(seed=UNSET_SEED)` | The same contract with no allocation. An unwritten address returns a byte mixed from the address and `seed`, and `cells` holds what was written |
| `sdsp.scramble(size, seed=UNSET_SEED)` | The scrambled bytes `Memory` and the register file come up holding |
| `sdsp.UNSET_SEED` | The default seed, `0x5A5A5A5A` |
| `sdsp.Voice` | One voice and its state |
| `sdsp.PIPELINE` | The schedule: for each of the 32 clocks, the steps that run, each a step name or a step name and a voice number |
| `sdsp.VOICE_COUNT`, `sdsp.REGISTER_COUNT` | 8 and 128 |
| `sdsp.ENV_RELEASE`, `sdsp.ENV_ATTACK`, `sdsp.ENV_DECAY`, `sdsp.ENV_SUSTAIN` | The envelope phases, 0 to 3, as `Voice.envelope_mode` holds them |
| `sdsp.COUNTER_RATES` | The 32 periods, in samples, of the envelope and noise clocks, one per rate |
| `sdsp.COUNTER_OFFSETS` | The 32 offsets that stagger rates sharing a period |
| `sdsp.GAUSSIAN` | The 512 entry interpolation kernel |
| `sdsp.check_kernel(table)` | Returns a kernel as a tuple, or raises `NotAKernel` naming the property and the entry that failed |
| `sdsp.UnknownModelError` | Raised for a missing or unknown model name. The message lists the names accepted |
| `sdsp.NotAKernel` | Raised by `check_kernel`, and by `Chip` when `gaussian` fails it |
| `sdsp.__version__` | The installed version |

```python
import sdsp

print(sdsp.UNSET_SEED, sdsp.scramble(4).hex(), sdsp.scramble(4, seed=1).hex())
print(
    sdsp.Memory(fill=0x55).read8(0x1234),
    sdsp.Memory().read8(0x1234),
    sdsp.SparseMemory().read8(0x1234),
)
held = sdsp.SparseMemory()
held.write8(0x1_0005, 0x1FF)
print(held.read8(5), held.cells)
```

```
1515870810 eb6cefd8 f5b16522
85 145 94
255 {5: 255}
```

```python
import sdsp

print(len(sdsp.GAUSSIAN), sdsp.GAUSSIAN[:4], sdsp.GAUSSIAN[-1])
print(sdsp.COUNTER_RATES[:4], sdsp.COUNTER_RATES[-1], sdsp.COUNTER_OFFSETS[:4])

for broken in (sdsp.GAUSSIAN[:256], (0, 9, 3) + sdsp.GAUSSIAN[3:], [0] * 256 + [2048] * 256):
    try:
        sdsp.Chip("s-dsp", gaussian=broken)
    except sdsp.NotAKernel as error:
        print(error)

own = sdsp.Chip("s-dsp", gaussian=list(sdsp.GAUSSIAN))
print(own.gaussian == sdsp.GAUSSIAN, sdsp.Chip("s-dsp").gaussian is sdsp.GAUSSIAN)
```

```
512 (0, 0, 0, 0) 1305
(30721, 2048, 1536, 1280) 1 (1, 0, 1040, 536)
a kernel is 512 entries, one quarter of the curve; this one has 256
the curve rises from nothing to its peak and never dips; entry 1 is 9 and entry 2 is 3
the four taps of every position sum to 2048; at position 0 they sum to 4096
True True
```

Rate 0 has a period of 30,721 samples, longer than the counter's range of 30,720, so it never fires. Rate 31 fires every sample.

### Command-line tools

| Command | What it does | Exit codes |
|:--|:--|:--|
| `python3 sdsp/doctor.py` | The machine and checkout report above | 0 clean, 1 a check failed |
| `python3 -m conformance.corpus [file]` | Replays every case in the corpus and compares the output digest | 0 all agree, 1 a case disagrees, 2 no corpus at the path |
| `python3 -m conformance.capture <dump directory> <census out> [limit]` | Reads the 128 DSP registers out of `.spc` dumps you own and writes a census | 0 written, 1 no dumps found, 2 bad arguments or no directory |
| `python3 -m conformance.documents [--check] [--only SUBSTRING]` | Fetches the manual into `docs/` and verifies its SHA-256. `--check` verifies without fetching | 0 verified, 1 refused or no match |
| `python3 -m conformance.quotes` | Looks for every quoted sentence in [`conformance/hardware.json`](conformance/hardware.json) in the manual | 0 every quote located or no manual on this machine, 1 otherwise |
| `python3 -m conformance.speed` | Measures `clock()` calls per second against a floor of 90,000 | 0 above the floor, 1 below |
| `python3 -m conformance.links` | Probes every address in this README | 0 every address is live, 1 an address returns HTTP 404 or 410 |
| `python3 -m conformance.package <wheel>` | Checks a built wheel ships every module and no test | 0 clean, 1 a fault or no wheel, 2 no argument |

## The thirty two clock schedule

A sample is 32 clocks, and the eight voices are pipelined across them. On any one clock, different voices run different steps, and the echo unit and the KON and KOFF latches run on fixed clocks of their own. A model that loops over voices once per sample computes the same notes and gets wrong which value a register read returns in the middle of a sample.

```python
import sdsp

for clock in (0, 17, 22, 30):
    print(clock, sdsp.PIPELINE[clock])

dsp = sdsp.Chip("s-dsp").reset()
dsp.run(40)
print(dsp.phase, len(dsp.rendered))
print(len(dsp.render(3)), dsp.phase)
```

```
0 [('voice_5', 0), ('voice_2', 1)]
17 [('voice_1', 0), ('voice_7', 5), ('voice_4', 6)]
22 [('voice_3a', 0), ('voice_9', 6), ('voice_6', 7), 'echo_22']
30 ['misc_30', ('voice_3c', 0), 'echo_30']
8 2
6 8
```

On clock 17, voice 0 starts its directory lookup while voice 5 writes ENDX and voice 6 decodes and mixes left. Voice 0's third step is split across clocks 22, 25 and 30. After 40 clocks the part has finished one sample, one stereo pair, and `phase` is 8. `render(3)` runs 96 clocks from there and leaves `phase` where it found it.

`PIPELINE` in [`sdsp/core.py`](sdsp/core.py) is the whole table. `clock()` runs it and nothing else decides the order.

## Models

```python
import sdsp

dsp = sdsp.Chip("snesdsp", sdsp.Memory())
print(dsp.model, sdsp.MODELS[dsp.model].voices, sdsp.MODELS[dsp.model])
print(sdsp.Chip("sdsp").model, sdsp.Chip("sonysdsp").model, sdsp.Chip("dsp").model)
```

```
s-dsp 8 <Model s-dsp, 8 voices>
s-dsp s-dsp s-dsp
```

There is one model. The S-DSP sits inside the S-SMP audio unit beside the SPC700 and was never sold on its own, so no revision is known to model. A part reached by an alias carries the canonical name.

## Is it right

| What | Held to | Kind of evidence |
|:--|:--|:--|
| Register map | Nintendo's table 3-7-1, every address this model names | Manufacturer |
| Rate table | Table 3-7-4, the noise clock, all 32 rows | Manufacturer |
| Attack times | Table 3-7-2, all 16 rows | Manufacturer |
| Decay and sustain times | Table 3-7-2, all 39 rows, against one endpoint the manual does not print | Manufacturer, relative |
| Whole-part output | 240 cases, 23,040 samples, against `snes_spc 0.9.0` | A second implementation |
| Console checks | 97 of 104 verdicts in Shay Green's `spc_dsp6` cartridge agree | Values taken on a console |
| Interpolation kernel | Length, shape and the four-tap sum | Self-check only, no artifact |

[`conformance/hardware.json`](conformance/hardware.json) carries each figure from the manual with its page, and [`conformance/hardware.test.py`](conformance/hardware.test.py) compares the package's constants with them. The manual's text layer stops at the figures, so every table was read off a rendered page image. `python3 -m conformance.quotes` locates 28 quoted sentences in the manual.

### The noise clock pins the rate table

Table 3-7-4 prints a frequency for each of the 32 noise clock values. Each one is 32,000 divided by one entry of `COUNTER_RATES`, so the table is pinned entry by entry. All 32 agree within 3 percent or 0.5 Hz, whichever is larger. The attack column pins the same table a second way: an attack is 64 steps, so the slowest rate takes 4.096 seconds, and all 16 printed times agree.

### The endpoint the manual leaves out

The decay and sustain columns give times without the level the fall is measured to. Dividing each of the 39 printed times by this model's period for its rate gives between 576 and 600 ticks, a spread under 5 percent. The recovered endpoint, about 590 ticks, is recorded in [`conformance/divergences.json`](conformance/divergences.json) and not built into the model.

### The interpolation kernel

The kernel is on the die, has never been dumped, and circulates as a printed table, so there is no file to digest. [`conformance/carried.json`](conformance/carried.json) pins the values the package carries by SHA-256, which detects an edit and says nothing about whether the table is the part's.

`check_kernel` holds a supplied table to what the interpolator needs:

| Property | Why the part needs it |
|:--|:--|
| 512 entries | The interpolator indexes up to `forward + 256` |
| Every tap a signed 16-bit word | The multiply is a signed 16-bit one |
| Rises from 0 and never dips | A dip reverses the curve |
| The four taps of every position sum to 2048, within 0.2 percent | Otherwise a voice's volume depends on where between two samples it lands |

Two different tables can pass, so passing means the table could be the part's. The kernel is held on each part, so two parts in one process can carry different tables.

### Where the audio comes from

`snes_spc 0.9.0` by Shay Green, which snes9x carries at `apu/bapu/dsp/SPC_DSP.cpp`, decides everything the manual does not reach, which is the audio itself. Agreement with it is agreement with that program, and [`conformance/divergences.json`](conformance/divergences.json) records that as its first entry, at severity high. The same author wrote the `spc_dsp6` cartridge, so the two are one source, not two.

The cartridge carries checks with expectations taken on a console. Driven through the audio unit in [sony-s-smp-python](https://github.com/gufranco/sony-s-smp-python), 104 of them reach a verdict here, 97 agree and 7 do not. [`conformance/cartridge.json`](conformance/cartridge.json) holds every verdict, and [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) groups the 7 by cause.

### The corpus

An SPC dump holds 64 KB of audio RAM, which is the music, and the 128 DSP registers, which are how a driver set the part up. [`conformance/capture.py`](conformance/capture.py) reads only the registers and seeks past the RAM.

[`conformance/corpus.json`](conformance/corpus.json) is built in three steps:

1. 240 register states from real dumps, covering 70 sample directory pages, 11 echo delays and 1,402 voices on ADSR envelopes.
2. Sample data generated from a seed per case, laid out where each state's directory and source numbers point.
3. 96 samples per case rendered by the reference driver in [`conformance/ref/`](conformance/ref), stored as a SHA-256 of the output.

`python3 -m conformance.corpus` replays all 240 and ends with `240 agreed, 0 did not`.

To read a collection of your own, `python3 -m conformance.capture /path/to/spc/collection census.json 500` writes the census for the first 500 dumps it finds. The census and anything built from it stay on your machine.

[OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) lists what is not settled, each with the measurement that would settle it.

## Working on it

| Need | Where |
|:--|:--|
| Every gate and the order to run them | [CONTRIBUTING.md](CONTRIBUTING.md) |
| The same material for a coding agent | [AGENTS.md](AGENTS.md) |
| The standard this repository shares with the rest of the family | [FAMILY.md](FAMILY.md) |
| Bug reports | [GitHub Issues](https://github.com/gufranco/sony-s-dsp-python/issues) |
| Security reports | [SECURITY.md](SECURITY.md) |

```bash
uvx ruff@0.16.3 format --check .
uvx ruff@0.16.3 check .
uvx --python 3.12 mypy==1.14.1
python3 sdsp/core.test.py
```

Each module has a test file beside it, named after it, and each runs on its own as above. Coverage is a hard gate at 100% statement and branch. A change to `PIPELINE` or to anything that alters output needs `python3 -m conformance.corpus` as well as the unit tests.

## References

- *SNES Development Manual, Book I*, Section 3, Nintendo of America Inc., undated. 240 pages, 21,022,582 bytes, SHA-256 `f1405241000046abba7849376d2ec53cf85f1ad2e9950d69a7c2cf1f3ff6b791`. It is not redistributable and is not in this repository. `python3 -m conformance.documents` downloads it from https://archive.org/download/SNESDevManual/book1_text.pdf into `docs/` and refuses any other file. Sony published no data sheet for the part.
- `snes_spc 0.9.0` by Shay Green, as snes9x 1.63 carries it at `apu/bapu/dsp/SPC_DSP.cpp`, for the corpus audio. [`conformance/ref/Dockerfile`](conformance/ref/Dockerfile) builds it from the snes9x `1.63` tag; no copy is vendored.
- Shay Green's `spc_dsp6` test cartridge, for the 104 console verdicts in [`conformance/cartridge.json`](conformance/cartridge.json).

## Citing this

[CITATION.cff](CITATION.cff) is updated with each release by the script that stamps the package version.

## License

MIT. See [LICENSE](LICENSE).
