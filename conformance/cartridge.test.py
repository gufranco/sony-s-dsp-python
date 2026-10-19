import json
import unittest
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent

RECORD = HERE / "cartridge.json"

TEST_ROMS = HERE / "testroms.json"


def listed(name: str) -> dict[str, Any]:
    entries: list[dict[str, Any]] = json.loads(TEST_ROMS.read_text())["cartridges"]
    return next(one for one in entries if one["id"] == name)


class TheRecordedVerdictsTest(unittest.TestCase):
    def test_every_check_spc_dsp6_reaches_agrees_with_a_console(self) -> None:
        # Arrange
        entry = listed("blargg-spc-dsp6")
        held = json.loads(RECORD.read_text())

        # Act
        astray = [one["check"] for one in held["checks"] if not one["agreed"]]

        # Assert
        self.assertEqual((held["verdicts"], held["agreed"], astray), (104, 104, []))
        self.assertEqual(len(held["checks"]), 104)
        self.assertEqual(held["cartridge"]["sha256"], entry["sha256"])


if __name__ == "__main__":
    unittest.main()
