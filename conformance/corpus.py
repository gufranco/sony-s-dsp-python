import hashlib
import json
import random
import struct
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sdsp.core import REGISTER_COUNT, Chip
from sdsp.memory import Memory

EXAMPLE_LIMIT = 5

DEFAULT_CORPUS = Path(__file__).resolve().parent / "corpus.json"

REG_DIR = 0x5D
V_SRCN = 0x04
REG_KON = 0x4C
REG_KOFF = 0x5C

BLOCKS_PER_VOICE = 30
BRR_BLOCK_BYTES = 9
VOICE_STRIDE = 0x120
FIRST_SAMPLE = 0x1000
SPACE = 0x10000


def load(path: Path | str | None = None) -> dict[str, Any]:
    with Path(path or DEFAULT_CORPUS).open() as handle:
        loaded: dict[str, Any] = json.load(handle)
    return loaded


def ram_for(case: Mapping[str, Any]) -> Any:
    registers = case["registers"]
    rng = random.Random(case["ram_seed"])
    ram = bytearray(rng.randbytes(SPACE))
    directory = registers[REG_DIR] * 0x100

    for voice in range(8):
        source = registers[voice * 0x10 + V_SRCN]
        start = (FIRST_SAMPLE + source * VOICE_STRIDE) & 0xFFFF
        if start + BLOCKS_PER_VOICE * BRR_BLOCK_BYTES >= 0xFF00:
            start = FIRST_SAMPLE
        for block in range(BLOCKS_PER_VOICE):
            at = start + block * BRR_BLOCK_BYTES
            ram[at] = (rng.randrange(13) << 4) | (rng.randrange(4) << 2)
            for offset in range(8):
                ram[at + 1 + offset] = rng.randrange(256)
        ram[start + (BLOCKS_PER_VOICE - 1) * BRR_BLOCK_BYTES] |= 0x01
        entry = (directory + source * 4) & 0xFFFF
        ram[entry : entry + 4] = struct.pack("<HH", start, start)

    return bytes(ram)


def render(case: Mapping[str, Any]) -> list[int]:
    registers = case["registers"]
    dsp = Chip(Memory(fill=ram_for(case)))
    for address in range(REGISTER_COUNT):
        if address not in (REG_KON, REG_KOFF):
            dsp.write(address, registers[address])
    dsp.write(REG_KOFF, registers[REG_KOFF])
    dsp.write(REG_KON, registers[REG_KON])
    return dsp.render(case["samples"])


def _label(case: Mapping[str, Any]) -> str:
    registers = case.get("registers")
    if isinstance(registers, list) and len(registers) > REG_DIR:
        return f"directory {registers[REG_DIR]:#04x}"
    return "a case with no register file"


def check(case: Mapping[str, Any]) -> str | None:
    try:
        produced = render(case)
    except Exception as error:  # noqa: BLE001
        return f"{_label(case)}: {type(error).__name__}"

    raw = b"".join(struct.pack("<h", value) for value in produced)
    digest = hashlib.sha256(raw).hexdigest()
    if digest == case["output_sha256"]:
        return None
    return f"{_label(case)}: want {case['output_sha256'][:16]} got {digest[:16]}"


def run(cases: list[dict[str, Any]]) -> tuple[int, int, list[str]]:
    passed = failed = 0
    examples: list[str] = []
    for case in cases:
        wrong = check(case)
        if wrong is None:
            passed += 1
        else:
            failed += 1
            if len(examples) < EXAMPLE_LIMIT:
                examples.append(wrong)
    return passed, failed, examples


def main(argv: list[str]) -> int:
    path = Path(argv[0]) if argv else DEFAULT_CORPUS
    if not path.is_file():
        print(f"  no corpus at {path}")
        return 2

    found = load(path)
    passed, failed, examples = run(found["cases"])
    census = found["census"]
    print(f"  {passed + failed} cases from {path}, against {found['reference']}")
    print(
        f"  configurations from {census['states']} music dumps, "
        f"{len(census['directories'])} sample directory pages"
    )
    print(f"  {passed} agreed, {failed} did not")
    for line in examples:
        print(f"    {line}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
