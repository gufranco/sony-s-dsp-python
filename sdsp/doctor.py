import hashlib
import json
import platform
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, override

ROOT = Path(__file__).resolve().parent.parent

from sdsp import environment  # noqa: E402

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sdsp import core, memory, models  # noqa: E402
from sdsp.version import VERSION  # noqa: E402

CORPUS = ROOT / "conformance" / "corpus.json"

DRIVER = ROOT / "conformance" / "ref" / "driver"

OLDEST_PYTHON = (3, 12)

UNWRITTEN = 0x1234


class Finding:
    def __init__(self, name: str, ok: bool, detail: str, advice: str | None = None) -> None:
        self.name = name
        self.ok = ok
        self.detail = detail
        self.advice = advice

    @property
    def line(self) -> str:
        return f"  {'ok  ' if self.ok else '   !'}  {self.name}: {self.detail}"

    @property
    def report(self) -> str:
        if self.ok or not self.advice:
            return self.line
        return f"{self.line}\n         {self.advice}"

    @override
    def __repr__(self) -> str:
        return f"<Finding {self.name} {'ok' if self.ok else 'not ok'}>"


def _python() -> "Finding":
    return Finding(
        "python",
        sys.version_info[:2] >= OLDEST_PYTHON,
        f"{platform.python_version()} on {platform.system()} {platform.machine()}",
        f"this package needs {OLDEST_PYTHON[0]}.{OLDEST_PYTHON[1]} or newer",
    )


def _package() -> "Finding":
    return Finding("sdsp", True, f"version {VERSION}")


def _default_build(name: str) -> Any:
    return models.lookup(name).build(memory.Memory())


def _part(name: str, build: Callable[[str], Any]) -> "Finding":
    try:
        chip = build(name)
        chip.reset()
    except Exception as trouble:
        return Finding(
            name,
            False,
            f"{type(trouble).__name__}: {trouble}",
            "this is the part failing to build rather than anything to do with a"
            " corpus; the line above is what it said",
        )
    described = models.lookup(name)
    return Finding(
        name,
        True,
        f"{described.voices} voices, {described.registers} registers,"
        f" model {getattr(chip, 'model', name)},"
        f" resets to flags ${chip.read(core.REG_FLG):02X}",
    )


def _memory(build: Callable[[str], Any]) -> "Finding":
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


def _corpus(where: Path | str) -> list["Finding"]:
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


def _driver(where: Path | str) -> "Finding":
    found = Path(where).exists()
    return Finding(
        "reference driver",
        True,
        "built and here"
        if found
        else "not built, so anything that regenerates the corpus will skip rather than run",
    )


def examine(
    build: Callable[[str], Any] = _default_build,
    corpus: Path | str = CORPUS,
    driver: Path | str = DRIVER,
) -> list["Finding"]:
    found = [_python(), _package()]
    found.extend(_part(name, build) for name in sorted(models.MODELS))
    found.append(_memory(build))
    found.extend(_corpus(corpus))
    found.append(_driver(driver))
    return found


def report(found: list["Finding"]) -> list[str]:
    unwell = [one for one in found if not one.ok]
    lines = [f"sdsp {VERSION} on {platform.python_version()}, {platform.system()}", ""]
    lines.append("  the machine")
    lines.extend(environment.lines(ROOT))
    lines.append("")
    lines.append("  this package")
    lines.extend(one.report for one in found)
    lines.append("")
    if unwell:
        lines.append(f"  {len(unwell)} of {len(found)} checks did not pass")
    else:
        lines.append(f"  {len(found)} checks, nothing to report")
    return lines


def main(
    argv: Sequence[str] = (),
    examine: Callable[..., list["Finding"]] = examine,
    say: Callable[[str], None] = print,
) -> int:
    found = examine()
    for line in report(found):
        say(line)
    return 1 if any(not one.ok for one in found) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
