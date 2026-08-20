"""Look at this machine and say what is actually here, so a report can be believed.

What goes wrong with this package is rarely a defect in it. It is a corpus that
is not the corpus everybody else has, a reference driver that was never built so
the checks needing it quietly did nothing, or audio RAM that somebody assumed
starts at zero. All three look the same from outside: the numbers disagree.

So this looks, and prints what it found in a form that can be pasted into an
issue as it stands.

Two rules shape it, and they are the whole point.

Nothing is hidden. A check that fails says what it saw, and a check that itself
throws is caught and reported as what it threw, named by its type. Swallowing
either would leave a report that says everything is fine on a machine where
something is not, which is worse than no report.

Nothing is inferred. Every line is something looked at on this machine just now:
the version installed, the digest of the corpus present, what an unwritten
address actually holds. A doctor that reports what ought to be true is a doctor
nobody can use.
"""

import hashlib
import json
import platform
import sys
from pathlib import Path

from . import memory, models
from .version import VERSION

ROOT = Path(__file__).resolve().parent.parent

CORPUS = ROOT / "conformance" / "corpus.json"

DRIVER = ROOT / "conformance" / "ref" / "driver"

OLDEST_PYTHON = (3, 12)

UNWRITTEN = 0x1234
"""An address nothing has written to, read to show what the part powers up holding."""


class Finding:
    """One thing that was looked at, and what was there."""

    def __init__(self, name, ok, detail, advice=None):
        self.name = name
        self.ok = ok
        self.detail = detail
        self.advice = advice

    @property
    def line(self):
        """The one-line form, which is what a reader scans."""
        return f"  {'ok  ' if self.ok else '   !'}  {self.name}: {self.detail}"

    @property
    def report(self):
        """The same, with what to do about it when there is something to do."""
        if self.ok or not self.advice:
            return self.line
        return f"{self.line}\n         {self.advice}"

    def __repr__(self):
        return f"<Finding {self.name} {'ok' if self.ok else 'not ok'}>"


def _python():
    return Finding(
        "python",
        sys.version_info[:2] >= OLDEST_PYTHON,
        f"{platform.python_version()} on {platform.system()} {platform.machine()}",
        f"this package needs {OLDEST_PYTHON[0]}.{OLDEST_PYTHON[1]} or newer",
    )


def _package():
    return Finding("sdsp", True, f"version {VERSION}")


def _default_build(name):
    return models.describe(name).build(memory.Memory())


def _part(name, build):
    """Whether that part builds, saying exactly what stopped it if not."""
    try:
        chip = build(name)
    except Exception as trouble:
        return Finding(
            name,
            False,
            f"{type(trouble).__name__}: {trouble}",
            "this is the part failing to build rather than anything to do with a"
            " corpus; the line above is what it said",
        )
    described = models.describe(name)
    return Finding(
        name,
        True,
        f"{described.voices} voices, {described.registers} registers,"
        f" model {getattr(chip, 'model', name)}",
    )


def _memory(build):
    """That audio RAM powers up holding something, which is what silicon does.

    A model whose memory starts at zero passes every test written against it and
    disagrees with hardware on the one case that matters: a driver reading a
    block it never wrote. This reads an address nothing has touched and prints
    what came back, so a report says which of the two this machine is running.
    """
    try:
        chip = build("s-dsp")
        held = chip.memory.read8(UNWRITTEN)
    except Exception as trouble:
        return Finding(
            "audio ram",
            False,
            f"{type(trouble).__name__}: {trouble}",
            "reading an unwritten address failed, which is itself the finding",
        )
    return Finding(
        "audio ram",
        held != 0,
        f"unwritten address {UNWRITTEN:#06x} holds {held:#04x}, seed {memory.UNSET_SEED:#010x}",
        "this memory starts clean, and hardware does not. Every result that"
        " depends on an unwritten block will disagree with the part",
    )


def _corpus(where):
    """The corpus that is here, which settles a disagreement about numbers.

    Two people running the same part against different corpora will disagree
    forever and neither will be wrong. The digest is what ends that in one glance
    rather than after a round trip.
    """
    try:
        raw = Path(where).read_bytes()
    except OSError as trouble:
        return [
            Finding(
                "corpus",
                False,
                f"could not be read: {trouble}",
                "the recorded states this package is settled against are missing from conformance/",
            )
        ]
    digest = hashlib.sha256(raw).hexdigest()
    try:
        held = json.loads(raw)
    except ValueError as trouble:
        return [
            Finding(
                "corpus",
                False,
                f"is not readable as JSON: {trouble}, sha256 {digest}",
                "the file is here and damaged, which is worse than absent",
            )
        ]
    cases = held.get("cases", [])
    return [
        Finding("corpus", bool(cases), f"{len(cases)} cases, sha256 {digest}"),
        Finding("recorded from", True, str(held.get("reference", "not stated"))),
    ]


def _driver(where):
    """Whether the reference is built, since its absence is silent otherwise.

    The corpus was produced by building somebody else's implementation and
    running it. That build is not needed to check against what it produced, and a
    machine without it is the normal case rather than a broken one. It is
    reported so that nobody reads a run that skipped as a run that passed.
    """
    found = Path(where).exists()
    return Finding(
        "reference driver",
        True,
        "built and here"
        if found
        else "not built, so anything that regenerates the corpus will skip rather than run",
    )


def examine(build=_default_build, corpus=CORPUS, driver=DRIVER):
    """Everything worth looking at on this machine, in the order a reader wants it."""
    found = [_python(), _package()]
    found.extend(_part(name, build) for name in sorted(models.MODELS))
    found.append(_memory(build))
    found.extend(_corpus(corpus))
    found.append(_driver(driver))
    return found


def report(found):
    """The lines a person pastes into an issue."""
    unwell = [one for one in found if not one.ok]
    lines = [f"sdsp {VERSION} on {platform.python_version()}, {platform.system()}", ""]
    lines.extend(one.report for one in found)
    lines.append("")
    if unwell:
        lines.append(f"  {len(unwell)} of {len(found)} checks did not pass")
    else:
        lines.append(f"  {len(found)} checks, nothing to report")
    return lines


def main(argv=(), examine=examine, say=print):
    found = examine()
    for line in report(found):
        say(line)
    return 1 if any(not one.ok for one in found) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
