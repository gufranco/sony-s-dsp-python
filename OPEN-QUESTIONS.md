# Open questions

What this project does not know for certain, and what it would take to find out.

Sony published no data sheet for this part. What exists is Nintendo's manual,
written for somebody programming the sound unit rather than describing the
silicon: it gives the register map, the rate table and the attack times, and it
says almost nothing about the order the part does its work in.

That order is the thing this repository is for. A sample is thirty two clocks, in
a fixed sequence, and which step reads a voice decides what a register read taken
mid sample answers. The sequence is modelled clock by clock because that is what
the hardware does, and it rests on a corpus rather than on a page, which is a
rung below everything else here and is recorded as such.

Every entry is also in
[`conformance/divergences.json`](conformance/divergences.json) with its status
and severity, so a program can read what a person reads here.

## What would settle almost all of them

A Sony document, or a capture of a real audio unit's register file and output
while a known program plays. Neither is available here.

## Where the audio rests on a second implementation

### Every sample this part produces.

**The document says.** The register map, the rates and the attack times, and
nothing about the arithmetic between them.

**What this project follows.** A corpus of real game configurations, cross
checked sample for sample against another implementation of the same part: 240
cases and 15,360 samples.

**Which implementation, exactly.** `snes_spc 0.9.0` by Shay Green, which is what
snes9x carries at `apu/bapu/dsp/SPC_DSP.cpp`. Naming the author rather than the
emulator around it changes the reading in both directions. It is stronger than a
generic emulator, because the same person wrote the programs that hold an audio
unit to a console. It is weaker than two sources, because for that same reason
it is one: agreeing with `snes_spc` and agreeing with his test programs is one
judgement, not two.

**Why.** It is the only source that reaches the audio at all. What it settles is
that two implementations agree, which is not the same as either being right about
silicon, and the record names the rung rather than presenting the agreement as a
measurement.

**What is now known.** His `spc_dsp6.sfc` carries 111 checks with expectations
taken on a console, and it is no longer out of reach. Driven at this model
through the composed audio unit in
[sony-s-smp-python](https://github.com/gufranco/sony-s-smp-python), it runs the
echo group, reaches the envelope group, and reports a disagreement with a table
checksum of `E7EEFEC8`.

The obvious way for that to be an artefact is the clock, since the console and
the audio unit run from separate crystals and the harness driving this had to
pick a rate between them. It is not: at one, two and three of the unit's cycles
per console instruction the checksum is the same every time, which is what a
figure that comes out of the part rather than out of the harness looks like.

**Five of his checks pass and one fails.** Each check is uploaded as its own
program carrying both its name and the value a console produced, so the verdict
is per check rather than for the run:

| Check | Console | This model | |
| --- | --- | --- | --- |
| Echo/edl 0 quirk | `72 10 02 2d` | `72 10 02 2d` | agrees |
| Echo/edl lengths | `48 cb 9a 15` | `48 cb 9a 15` | agrees |
| Envelope/attack->decay during gain | `46 86 5d bd` | `46 86 5d bd` | agrees |
| Envelope/decay->sustain during gain | `90 c8 96 de` | `90 c8 96 de` | agrees |
| Envelope/envelope rates | `90 e0 49 9b` | `90 e0 49 9b` | agrees |
| Envelope/gain $E0 threshold | `35 9a 05 12` | `37 01 11 18` | **disagrees** |

Six earlier programs, `Echo/basics` through `Echo/echo calc`, ran without a
comparison of that shape and are not counted either way.

**The failing check is down to one byte.** Everything it feeds its checksum was
captured at the one instruction that feeds it, 28 bytes, and plain CRC-32 begun
at all ones reproduces the unit's own accumulator exactly, so the capture is the
input rather than a reconstruction of it. Of every single-byte and every
single-word correction to those 28 bytes, exactly one produces the console's
value: **the seventeenth byte must be `0x27` and this model makes it `0x3f`.**

That byte is the low half of a word the check halves before reporting, so what
it means is that this model counts **126 where a console counts 78**.

**The obvious cause has been ruled out, three ways.** The bent increase adds
`0x20` and drops to `0x8` once past `0x600`, and it tests the hidden envelope
left by the previous step rather than the value it has just computed. That
asymmetry is real and it is not this: testing the computed value with `>`, and
again with `>=`, leaves the byte at `0x3f` both times. The line stands unchanged
rather than being adjusted to look tidier.

That is the interesting result rather than a disappointing one. This model agrees
with `snes_spc` across 15,360 samples and disagrees with the same author's
hardware check, so the two are reaching different ground: either the corpus does
not cover what the check covers, or something between them is at fault.

**The divergence is real, and it no longer needs a cartridge to see.** The
failing check was captured at the instant the audio unit jumps into it and
written back out as a file that both this family and the author's own library
load. `snes_spc 0.9.0` was built from source and handed the same file. Run with
no console attached at all:

| Running the same program, no console | Result |
| --- | --- |
| This family's sound generator, in the composed audio unit | `a2 c9 a2 2b` |
| `snes_spc 0.9.0`, by the author of the check | `00 ed 26 be` |

Both are settled rather than caught mid-run: unchanged across one, two and four
million instructions on one side and one hundred, two hundred and four hundred
thousand samples on the other.

That is the useful shape. The neighbouring member ran the same experiment for the
processor and the two implementations agreed exactly, which is what tells us this
one is a real difference between two models of this part rather than an artefact
of how either was driven.

What the check does, read out of its own code: it writes `$ff` to voice 0's gain
register, which is bent increase at rate 31, then `$e0`, which is bent increase at
rate 0, waits, and reports a sixteen bit count halved on the way out. This model
makes that count 126 and a console makes it 78.

**What is not known.** Where the two implementations part company inside that
sequence. It is now a bounded job rather than a cartridge run: both are on this
machine, both take under a minute, and the state of one can be compared against
the state of the other after any number of samples.

**A third opinion was read and it agrees with this model.** The MiSTer SNES core
keeps a latched flag for the bent increase, sets it from the freshly computed
envelope with `>= 0x600`, and uses it on the following step, which is what this
package does by testing the previous step's hidden envelope. It also sets that
flag when the computed value overflows either way, which this package did not.
Adding that made no difference to the check, so it is not the cause, and the line
stands as it was. That core is another implementation rather than a measurement,
so it is a third opinion and not a rung.

**What would settle or reopen it.** Isolating that check and reading what it
expects, which is in the cartridge rather than in anybody's prose. Failing that,
a recording of a real audio unit playing a known program, compared sample for
sample.

### The gaussian interpolation kernel.

**The document says.** That pitch is a fourteen bit value. It never gives the
filter that resamples.

**What this project follows.** The 512 entry table every implementation carries.

**Why.** Nothing else exists. The table is not derived here and cannot be: it is
a property of the silicon that somebody read out of it, and this repository
carries the numbers rather than a derivation of them.

**A closed form was looked for and there is none.** If the table were a computed
curve, the formula would be the source and a transcription error would show up as
a mismatch. Fitted by least squares against all 512 entries on 2026-08-25, taking
entry `u` as the kernel at distance `(511.5 - u) / 256`, the closest candidates
leave these peak errors on a maximum of 1305:

| Candidate | Peak error | Mean error |
|:--|--:|--:|
| cos^3.5(pi d / 4) | 18 | 9.6 |
| Gaussian, sigma 0.63 | 21 | 10.5 |
| Cubic B-spline | 38 | 18.4 |
| Hann squared | 44 | 21.6 |
| cos^2(pi d / 4) | 191 | 109.1 |
| Catmull-Rom | 380 | 178.9 |

Nothing lands inside rounding, so the table is stored rather than computed. The
search is written down with its numbers so the next person to have the idea finds
the result instead of repeating it.

**What is checked instead.** The properties the silicon has to have for the chip
to work at all, and they hold: the curve never decreases, it starts at zero and
peaks at the end, every entry fits a signed word, and the four taps reading any
position sum to one unit to within one part in two thousand. Those do not say the
numbers are right. They say a transcription that broke one of them would be
caught.

**What would settle or reopen it.** A die read, or a Sony document.

## Where the manual stops short

### Where the decay and sustain times are measured to.

**The document says.** Two columns of times, internally consistent to within two
per cent of one endpoint. It never says what level that endpoint is.

**What this project follows.** The rate table, which reproduces every printed
figure.

**Why.** The rates are what the part counts in, and the times are derived from
them. A model built from the times rather than the rates would have to invent the
endpoint the manual omits.

**What would settle or reopen it.** A page naming the level, or a measurement.

### What a register holds at power on.

**The document says.** Nothing.

**What this project follows.** A scrambled pattern derived from a seed, which is
reproducible and is not zero.

**Why.** Zero is the one answer that is certainly wrong: a machine does not hand
over cleared registers. What a reset leaves behind is a separate question and is
modelled, with the record marking it unverified.

**What would settle or reopen it.** A capture of the register file at power on.

### Whether any of this is a claim about Sony's part rather than about a model.

**The document says.** Nothing. There is no Sony document.

**What this project follows.** Nintendo's manual where it prints a figure, and
the corpus everywhere else.

**Why.** It is worth stating outright rather than leaving implied: the top rung
of the ladder is empty here, and a reader who assumes a manufacturer stands
behind the audio would be assuming something no file in this repository claims.

**What would settle or reopen it.** A Sony data sheet.

## Where the question is a scope boundary, not an unknown

### Anything measured in cycles.

**What this project does.** Models the thirty two step schedule and makes no
claim about how those steps line up with the processor beside it.

**Why it is not a gap.** The manual describes this part in times and frequencies,
so nothing here can settle when within a sample period a register is read from
the processor's point of view. The processor is
[sony-spc700-python](https://github.com/gufranco/sony-spc700-python) and it
reports its own cycles.

**What would settle or reopen it.** A capture of both parts on one bus.

## What is not in question

So the boundary is visible rather than implied:

- **Every rate, every attack time and every register address.** Checked against
  Nintendo's own tables, with the page each was read from.
- **The order of the thirty two steps.** A voice read the hardware performs on
  step 9 is performed on step 9 here, which is what makes a mid sample register
  read answer what the hardware answers.
- **That the corpus can ship.** It is configurations and outputs, not anybody's
  music, and it is generated rather than extracted.

## What is deliberately not modelled

Absent rather than unknown, and absent on purpose:

- **The processor beside it.** The audio unit is this part, a processor, RAM and
  a boot ROM. The processor is
  [sony-spc700-python](https://github.com/gufranco/sony-spc700-python).
- **The boot ROM.** It is Sony's program and is not carried.
- **Anything measured in cycles.** See above.
