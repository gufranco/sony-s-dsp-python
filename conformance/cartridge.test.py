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


def self_test(name: str) -> tuple[bool, int, str, list[str]]:
    images: list[dict[str, Any]] = json.loads(RECORD.read_text())["selfTests"]["images"]
    run = next(one for one in images if one["id"] == name)["measured"]
    failing = [one for one, passed in run["subTests"].items() if not passed]
    return run["handshake"], run["result"] & ~0x04, run["ports"], failing


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

    def test_the_burn_in_self_test_passes_every_sub_test_but_the_envelope(self) -> None:
        # Arrange
        name = "burn-in-rev-d-apu"

        # Act
        held = self_test(name)

        # Assert
        self.assertEqual(held, (True, 0, "00 00", []))

    def test_the_snsp_aging_self_test_passes_every_sub_test(self) -> None:
        # Arrange
        name = "snsp-aging-1-02-apu"

        # Act
        held = self_test(name)

        # Assert
        self.assertEqual(held, (True, 0, "00 00", []))

    def test_the_control_deck_tester_self_test_passes_every_sub_test(self) -> None:
        # Arrange
        name = "control-deck-tester-rev-1-apu"

        # Act
        held = self_test(name)

        # Assert
        self.assertEqual(held, (True, 0, "00 00", []))

    def test_the_aging_1_00_self_test_passes_all_six_of_its_sub_tests(self) -> None:
        # Arrange
        name = "aging-1-00-apu"

        # Act
        held = self_test(name)

        # Assert
        self.assertEqual(held, (True, 0, "00 00", []))


if __name__ == "__main__":
    unittest.main()
