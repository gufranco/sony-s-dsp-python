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
checked sample for sample against a second implementation of the same part: 240
cases and 15,360 samples.

**Why.** It is the only source that reaches the audio at all. What it settles is
that two implementations agree, which is not the same as either being right about
silicon, and the record names the rung rather than presenting the agreement as a
measurement.

**What would settle or reopen it.** A recording of a real audio unit playing a
known program, compared sample for sample.

### The gaussian interpolation kernel.

**The document says.** That pitch is a fourteen bit value. It never gives the
filter that resamples.

**What this project follows.** The 512 entry table every implementation carries.

**Why.** Nothing else exists. The table is not derived here and cannot be: it is
a property of the silicon that somebody read out of it, and this repository
carries the numbers rather than a derivation of them.

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
