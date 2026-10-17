import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import sdsp  # noqa: E402
from sdsp import doctor  # noqa: E402

NOWHERE = Path("/nowhere/at/all")


class Complaint(Exception):
    pass


class WillNotReset:
    model = "s-dsp"

    def reset(self) -> Any:
        raise Complaint("the pin did nothing")


class Counted:
    model = "s-dsp"

    def __init__(self, resets: list[str]) -> None:
        self.part = sdsp.Chip("s-dsp", sdsp.Memory())
        self.resets = resets

    def reset(self) -> Any:
        self.resets.append("reset")
        return self.part.reset()

    def read(self, address: int) -> int:
        return self.part.read(address)


class Zeroed:
    def read8(self, address: int) -> int:
        return 0


class Clean:
    memory = Zeroed()


def a_finding(
    name: str = "something", ok: bool = True, detail: str = "detail", advice: str | None = None
) -> Any:
    return doctor.Finding(name, ok, detail, advice)


def a_file(text: str) -> Path:
    where = Path(tempfile.mkdtemp()) / "corpus.json"
    where.write_text(text)
    return where


def a_corpus(cases: int = 3, reference: str = "snes9x 1.63 SPC_DSP.cpp") -> Path:
    return a_file(json.dumps({"reference": reference, "cases": [{} for _ in range(cases)]}))


def boom(_name: str) -> Any:
    raise Complaint("the core exploded")


def unresettable(_name: str) -> Any:
    return WillNotReset()


def clean(_name: str) -> Any:
    return Clean()


def details(found: list[Any]) -> str:
    return " ".join(one.detail for one in found)


def named(found: list[Any], name: str) -> list[Any]:
    return [one for one in found if one.name == name]


class FindingTest(unittest.TestCase):
    def test_a_finding_says_what_was_checked(self) -> None:
        # Arrange
        name = "the corpus"

        # Act
        found = a_finding(name=name)

        # Assert
        self.assertEqual(found.name, "the corpus")

    def test_and_whether_it_was_well(self) -> None:
        # Arrange
        verdicts = (True, False)

        # Act
        found = [a_finding(ok=ok).ok for ok in verdicts]

        # Assert
        self.assertEqual(found, [True, False])

    def test_a_healthy_finding_prints_with_a_mark_that_says_so(self) -> None:
        # Arrange
        found = a_finding(ok=True)

        # Act
        line = found.line

        # Assert
        self.assertEqual(line, "  ok    something: detail")

    def test_and_an_unhealthy_one_prints_differently(self) -> None:
        # Arrange
        found = a_finding(ok=False)

        # Act
        line = found.line

        # Assert
        self.assertEqual(line, "     !  something: detail")

    def test_every_finding_carries_what_it_actually_saw(self) -> None:
        # Arrange
        found = a_finding(detail="240 cases")

        # Act
        line = found.line

        # Assert
        self.assertIn("240 cases", line)

    def test_an_unhealthy_finding_says_what_to_do_about_it(self) -> None:
        # Arrange
        found = a_finding(ok=False, advice="go and look")

        # Act
        report = found.report

        # Assert
        self.assertEqual(report, "     !  something: detail\n         go and look")

    def test_a_healthy_one_carries_no_advice(self) -> None:
        # Arrange
        found = a_finding(ok=True, advice="x")

        # Act
        report = found.report

        # Assert
        self.assertEqual(report, a_finding(ok=True).line)

    def test_a_finding_prints_as_itself(self) -> None:
        # Arrange
        found = a_finding(ok=False)

        # Act
        printed = repr(found)

        # Assert
        self.assertEqual(printed, "<Finding something not ok>")


class ExamineTest(unittest.TestCase):
    def test_it_reports_the_python_the_package_and_every_part_it_covers(self) -> None:
        # Arrange
        expected = {"python", "sdsp", *sdsp.MODELS}

        # Act
        names = {one.name for one in doctor.examine()}

        # Assert
        self.assertEqual(expected - names, set())

    def test_every_finding_carries_a_detail(self) -> None:
        # Arrange
        examined = doctor.examine

        # Act
        bare = [one.name for one in examined() if not one.detail]

        # Assert
        self.assertEqual(bare, [])

    def test_a_part_that_will_not_build_is_reported_with_what_it_said(self) -> None:
        # Arrange
        build = boom

        # Act
        found = named(doctor.examine(build=build), "s-dsp")

        # Assert
        self.assertEqual((found[0].ok, found[0].detail), (False, "Complaint: the core exploded"))

    def test_a_part_that_builds_is_reported_with_its_shape_and_its_reset_flags(self) -> None:
        # Arrange
        examined = doctor.examine

        # Act
        found = named(examined(), "s-dsp")

        # Assert
        self.assertEqual(
            found[0].detail, "8 voices, 128 registers, model s-dsp, resets to flags $E0"
        )

    def test_a_part_that_builds_and_will_not_reset_is_reported_as_broken(self) -> None:
        # Arrange
        build = unresettable

        # Act
        found = named(doctor.examine(build=build), "s-dsp")

        # Assert
        self.assertEqual((found[0].ok, found[0].detail), (False, "Complaint: the pin did nothing"))

    def test_the_doctor_resets_the_part_itself_rather_than_trusting_the_build(self) -> None:
        # Arrange
        resets: list[str] = []

        # Act
        found = named(doctor.examine(build=lambda _name: Counted(resets)), "s-dsp")

        # Assert
        self.assertEqual((found[0].ok, resets), (True, ["reset"]))


class MemoryTest(unittest.TestCase):
    def test_unwritten_audio_ram_holds_something_and_says_what(self) -> None:
        # Arrange
        examined = doctor.examine

        # Act
        found = named(examined(), "audio ram")

        # Assert
        self.assertEqual(
            (found[0].ok, found[0].detail),
            (True, "unwritten address 0x1234 holds 0x91, seed 0x5a5a5a5a"),
        )

    def test_memory_that_starts_clean_is_reported_as_a_failure(self) -> None:
        # Arrange
        build = clean

        # Act
        found = doctor.check_memory(build)

        # Assert
        self.assertEqual((found.ok, "does not" in (found.advice or "")), (False, True))

    def test_a_read_that_throws_is_reported_rather_than_swallowed(self) -> None:
        # Arrange
        build = boom

        # Act
        found = doctor.check_memory(build)

        # Assert
        self.assertEqual((found.ok, found.detail), (False, "Complaint: the core exploded"))


class CorpusTest(unittest.TestCase):
    def test_a_corpus_that_is_here_is_counted(self) -> None:
        # Arrange
        where = a_corpus(cases=7)

        # Act
        found = doctor.examine(corpus=where)

        # Assert
        self.assertIn("7 cases", details(found))

    def test_and_carries_the_digest_of_the_file_that_is_actually_here(self) -> None:
        # Arrange
        where = a_corpus()

        # Act
        found = doctor.examine(corpus=where)

        # Assert
        self.assertIn(hashlib.sha256(where.read_bytes()).hexdigest(), details(found))

    def test_and_names_what_it_was_recorded_from(self) -> None:
        # Arrange
        where = a_corpus(reference="somebody else 2.0")

        # Act
        found = doctor.examine(corpus=where)

        # Assert
        self.assertEqual(named(found, "recorded from")[0].detail, "somebody else 2.0")

    def test_a_corpus_that_says_nothing_about_its_source_says_so(self) -> None:
        # Arrange
        where = a_file(json.dumps({"cases": [{}]}))

        # Act
        found = doctor.examine(corpus=where)

        # Assert
        self.assertEqual(named(found, "recorded from")[0].detail, "not stated")

    def test_a_corpus_that_is_not_here_is_a_failure(self) -> None:
        # Arrange
        where = NOWHERE

        # Act
        found = doctor.examine(corpus=where)

        # Assert
        self.assertEqual([one.ok for one in named(found, "corpus")], [False])

    def test_a_corpus_that_is_here_and_damaged_is_worse_and_says_so(self) -> None:
        # Arrange
        where = a_file("{ this is not json")

        # Act
        found = named(doctor.examine(corpus=where), "corpus")

        # Assert
        self.assertEqual(
            (found[0].ok, "not readable as JSON" in found[0].detail, "sha256" in found[0].detail),
            (False, True, True),
        )

    def test_an_empty_corpus_is_a_failure_rather_than_a_pass(self) -> None:
        # Arrange
        where = a_file(json.dumps({"cases": []}))

        # Act
        found = doctor.examine(corpus=where)

        # Assert
        self.assertEqual([one.ok for one in named(found, "corpus")], [False])

    def test_the_corpus_it_reads_by_default_is_the_one_in_this_repository(self) -> None:
        # Arrange
        expected = ROOT / "conformance" / "corpus.json"

        # Act
        found = doctor.CORPUS

        # Assert
        self.assertEqual((found, found.exists()), (expected, True))


class DriverTest(unittest.TestCase):
    def test_a_driver_that_is_built_is_reported_as_here(self) -> None:
        # Arrange
        where = Path(tempfile.mkdtemp()) / "driver"
        where.write_bytes(b"not really a driver")

        # Act
        found = doctor.examine(driver=where)

        # Assert
        self.assertEqual(named(found, "reference driver")[0].detail, "built and here")

    def test_one_that_is_not_built_says_what_will_skip_and_is_not_a_failure(self) -> None:
        # Arrange
        where = NOWHERE

        # Act
        found = named(doctor.examine(driver=where), "reference driver")

        # Assert
        self.assertEqual((found[0].ok, "skip" in found[0].detail), (True, True))


if __name__ == "__main__":
    unittest.main()
