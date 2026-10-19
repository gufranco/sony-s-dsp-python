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
cases and 23,040 samples.

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

**What is now known.** His `spc_dsp6.sfc` carries checks with expectations taken
on a console. Driven at this model through the composed audio unit in
[sony-s-smp-python](https://github.com/gufranco/sony-s-smp-python), each check
uploads as its own program carrying its name and the value a console produced, so
the verdict is per check. His harness reports only the first failure and then
restarts, so the run records each verdict and turns that check's four
conditional branches into no-ops to carry on. Nothing rewrites what a check
expects.

**All 104 verdicts it reaches agree** (as of 2026-10-19). The cartridge is
SHA-256 `b12038f865536a33003c9887e6f86fcbcb526b7f1766526ab30cb74b7380aa9a`, from
`https://gitlab.com/higan/snes-test-roms` at commit
`26e8aa91e0d3b90b901e7e693bc4a8244b391d7b`, and is not carried here.

| Group     |   Agree | Disagree |
| --------- | ------: | -------: |
| Order     |      19 |        0 |
| Timing    |      41 |        0 |
| KON       |      18 |        0 |
| Misc      |       9 |        0 |
| Random    |       8 |        0 |
| Envelope  |       7 |        0 |
| Echo      |       2 |        0 |
| **Total** | **104** |    **0** |

Every verdict is in
[`conformance/cartridge.json`](conformance/cartridge.json).

Seven of them disagreed until three causes were found, each read out of a second
implementation at a pinned commit and then confirmed by the console's value:

- **The bent gain increase tested the hidden envelope as a signed number.** It
  drops to the slow step once the previous step's hidden envelope is at or past
  `0x600`, and both `snes_spc 0.9.0` (`SPC_DSP.cpp` line 626, as snes9x at
  `2971061c` carries it) and ares at `9408cb43` (`sfc/dsp/envelope.cpp`) read it
  unsigned, so a hidden envelope a linear decrease drove below zero also takes
  the slow step. This was `Envelope/gain $E0 threshold`, `Envelope/hidden env 0
at kon`, `Envelope/hidden env after gain` and `KON/hidden env flag during kon`.
- **A write to OUTX or ENVX did not reach the value the schedule was holding.**
  Both implementations latch the written byte, so the schedule writes it back
  rather than its own. This was `Timing/Voice/V8 outx` and `Timing/Voice/V9
envx`. They are settled at the step granularity this model runs at, which is
  also the granularity ares runs its schedule at, so no finer interval is needed
  for them.
- **`Misc/$F0-$FF are not ram` was the audio unit's register file**, fixed in
  sony-s-smp-python.

**What is still not known.** The cartridge checks what the registers, the memory
and the schedule do. It reaches the sample values only through checksums of a
few of them, so every other sample still rests on agreement with `snes_spc`.

**What would settle or reopen it.** A recording of a real audio unit playing a
known program, compared sample for sample.

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

| Candidate            | Peak error | Mean error |
| :------------------- | ---------: | ---------: |
| cos^3.5(pi d / 4)    |         18 |        9.6 |
| Gaussian, sigma 0.63 |         21 |       10.5 |
| Cubic B-spline       |         38 |       18.4 |
| Hann squared         |         44 |       21.6 |
| cos^2(pi d / 4)      |        191 |      109.1 |
| Catmull-Rom          |        380 |      178.9 |

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

### What the part holds at power on.

**The document says.** Nothing, for any of it.

**What this project follows.** A pattern drawn from a seed, reproducible and not
cleared, for every piece of state the part has. None of it is kept fixed,
because nothing printed and nothing measured says what any of it holds:

- the 128 registers;
- which of the thirty two clocks runs first, and the rate counter the envelopes
  and the noise clock count against;
- the noise generator, anywhere in its fifteen bits except 0;
- the every-other-sample toggle, the key-on latch, the key-on value last taken
  and the flag that a key-on happened;
- the echo position, length and pointer, the eight samples of echo history and
  which of them is newest, and the flag value the echo unit last read;
- the left and right sums for the main mix, the echo input and the echo output;
- the values the schedule carries from one clock to the next: the pitch, the
  directory and block addresses, the block header and byte, the output, and the
  ENDX, OUTX and ENVX values waiting to be written;
- in each voice, its twelve decoded samples, the group of four the next decode
  lands on, its block address and the pair inside the block, its pitch position,
  its key-on delay, and its envelope phase, level, hidden level and the level it
  reports.

**Why.** Zero is the one answer that is certainly wrong: a machine does not
hand over cleared latches, and a value a reset sets is no better, because it
would make a part nobody reset behave like one somebody did. Each field is drawn
across the values the model's own logic gives it, so a part nobody reset still
runs. The noise generator never comes up holding 0, because 0 is the one value
its feedback cannot leave: a part that did would play silent noise until reset,
and the record says so under `powerOn`.

**What would settle or reopen it.** A capture of the register file, and of the
output of a voice keyed with noise on, on a real audio unit before anything is
written to it, repeated across power cycles and across parts. A field that held
the same value every time would then be fixed, with the capture cited.

### What a reset sets beyond the flag register.

**The document says.** That `FLG` carries a reset bit. It never says what a
reset leaves in any register or in any latch.

**What this project follows.** `snes_spc 0.9.0` as snes9x 1.63 carries it, the
implementation the corpus was recorded from: every register and every latch
cleared, `FLG` set to `$E0`, the noise generator set to `$4000`, the
every-other-sample toggle set to 1, and each voice's block offset set to the
first pair. `resetLine` in the record lists every field with its value, and a
test holds the model to that list.

**Why.** The corpus agrees only while the reset does all of that. A reset that
set the registers and released the voices and left everything else where power
on put it agreed on 2 of the 240 cases. So the reset is a reading of another
implementation, which is a rung below anything printed, and the record marks it
unverified.

**What would settle or reopen it.** A capture of the register file on a real
audio unit immediately after reset, and of a voice keyed with noise on straight
after it, which shows where the generator starts.

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

**What would settle or reopen it.** A capture of both parts on one bus. Shay
Green's `spc_dsp6.sfc` already holds the alignment the console sees: composed
with the processor in
[sony-s-smp-python](https://github.com/gufranco/sony-s-smp-python), its 41
timing checks agree with values taken on a console.

## What a comparison against the author's own implementation could not settle

`snes_spc 0.9.0` was built as a shared library and given the same four-port
interface this family's audio unit presents, so the same console harness could
drive either one and nothing but the implementation would differ. It starts,
answers `0xaa 0xbb`, takes the upload and runs five checks.

Then its memory goes to zero and stays there while the console polls a pair of
ports that never change again. That is the harness losing the unit rather than
the unit disagreeing about anything, and the cause was not found.

So the comparison says nothing about either implementation and is recorded as a
dead end rather than as a result. What it does establish is the shape of the
experiment for whoever tries again: the interface swap is the right idea, the
library needs the same sixty four bytes of boot program this family needs, and
the thing to fix first is whatever the adapter does to time.

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
