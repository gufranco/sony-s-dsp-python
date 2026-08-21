# Security

## Reporting

Report anything you believe is a security problem through
[GitHub's private vulnerability reporting](https://docs.github.com/code-security/security-advisories/guidance-on-reporting-and-writing/privately-reporting-a-security-vulnerability)
on this repository, rather than in a public issue. There is no service behind
this and no user data, so the realistic reports are about the supply chain and
about what a malformed input can make the code do.

## What is in scope

| Class | Example |
|-------|---------|
| Supply chain | A dependency or a pinned action that has been compromised |
| Malformed input | A crafted corpus or dump that makes a runner allocate without bound or loop without end |
| Path handling | An input that causes a write outside the directory the caller named |
| Dump handling | A crafted music dump that makes the capture tool read or write outside what it declared |

## What is not

A conformance disagreement is a correctness bug and belongs in a normal issue.
So does a model that disagrees with real hardware. Neither is a security matter,
and filing them privately only slows the fix.

## What this repository reads, and what it never keeps

`conformance/capture.py` reads music dumps you already have. A dump is a
snapshot of a running audio unit: a header, sixty four kilobytes of audio RAM,
and the DSP registers. Only the registers are read. The RAM holds the samples
and the sequence data, which together are the music, and this tool seeks past it
and writes none of it anywhere.

A report that the capture path can be made to read past the end of a dump, to
follow a length out of the header without bound, or to write a byte of audio RAM
into the corpus, is in scope and is the most interesting thing here.

Nothing reaches the network. Any file the model reads is one already on the
machine because somebody put it there.
