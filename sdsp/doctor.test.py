import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, override

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sdsp import core, doctor, memory


class Complaint(Exception):
    pass


def a_finding(
    name: str = "something", ok: bool = True, detail: str = "detail", advice: str | None = None
) -> Any:
    return doctor.Finding(name, ok, detail, advice)


def a_corpus(cases: int = 3, reference: str = "snes9x 1.63 SPC_DSP.cpp") -> Path:
    where = Path(tempfile.mkdtemp()) / "corpus.json"
    where.write_text(json.dumps({"reference": reference, "cases": [{} for _ in range(cases)]}))
    return where


class FindingTest(unittest.TestCase):
    def test_a_finding_says_what_was_checked(self) -> None:
        self.assertEqual(a_finding(name="the corpus").name, "the corpus")

    def test_and_whether_it_was_well(self) -> None:
        self.assertTrue(a_finding(ok=True).ok)
        self.assertFalse(a_finding(ok=False).ok)

    def test_a_healthy_finding_prints_with_a_mark_that_says_so(self) -> None:
        self.assertIn("ok", a_finding(ok=True).line)

    def test_and_an_unhealthy_one_prints_differently(self) -> None:
        self.assertNotIn("ok", a_finding(ok=False).line)

    def test_every_finding_carries_what_it_actually_saw(self) -> None:
        self.assertIn("240 cases", a_finding(detail="240 cases").line)

    def test_an_unhealthy_finding_says_what_to_do_about_it(self) -> None:
        self.assertIn("go and look", a_finding(ok=False, advice="go and look").report)

    def test_a_healthy_one_carries_no_advice(self) -> None:
        self.assertEqual(a_finding(ok=True, advice="x").report, a_finding(ok=True).line)

    def test_a_finding_prints_as_itself(self) -> None:
        self.assertIn("something", repr(a_finding()))


class ExamineTest(unittest.TestCase):
    def test_the_examination_produces_findings(self) -> None:
        self.assertTrue(doctor.examine())

    def test_it_reports_the_python_it_is_running_on(self) -> None:
        self.assertIn("python", [one.name for one in doctor.examine()])

    def test_and_the_version_of_this_package(self) -> None:
        self.assertIn("sdsp", [one.name for one in doctor.examine()])

    def test_and_one_finding_per_part_it_covers(self) -> None:
        from sdsp import models

        names = [one.name for one in doctor.examine()]

        for model in models.MODELS:
            self.assertIn(model, names, model)

    def test_every_finding_carries_a_detail(self) -> None:
        for one in doctor.examine():
            self.assertTrue(one.detail, one.name)

    def test_a_part_that_will_not_build_is_reported_rather_than_hidden(self) -> None:
        def boom(_name: str) -> Any:
            raise Complaint("the core exploded")

        found = doctor.examine(build=boom)

        self.assertTrue(any(not one.ok for one in found))

    def test_and_the_report_carries_what_it_said_and_what_kind(self) -> None:
        def boom(_name: str) -> Any:
            raise Complaint("the core exploded")

        text = "\n".join(one.report for one in doctor.examine(build=boom))

        self.assertIn("the core exploded", text)
        self.assertIn("Complaint", text)

    def test_a_part_that_builds_is_reported_with_its_shape(self) -> None:
        for one in doctor.examine():
            if one.name == "s-dsp":
                self.assertIn("8 voices", one.detail)

    def test_and_with_the_flags_the_reset_left_behind(self) -> None:
        """Driven rather than described, so a reset that stopped working shows here."""
        found = [one for one in doctor.examine() if one.name == "s-dsp"]

        self.assertIn("resets to flags $E0", found[0].detail)

    def test_a_part_that_builds_and_will_not_reset_is_reported_as_broken(self) -> None:
        class WillNotReset(core.Chip):
            @override
            def reset(self) -> Any:
                raise Complaint("the pin did nothing")

        def build(_name: str) -> Any:
            return WillNotReset(memory.Memory())

        found = [one for one in doctor.examine(build=build) if one.name == "s-dsp"]

        self.assertFalse(found[0].ok)


class MemoryTest(unittest.TestCase):
    """That the report says whether this machine starts clean, because silicon does not."""

    def test_unwritten_audio_ram_holds_something(self) -> None:
        for one in doctor.examine():
            if one.name == "audio ram":
                self.assertTrue(one.ok)

    def test_and_the_report_says_what_it_actually_held(self) -> None:
        for one in doctor.examine():
            if one.name == "audio ram":
                self.assertIn("holds", one.detail)

    def test_memory_that_starts_clean_is_reported_as_a_failure(self) -> None:
        class Clean:
            memory = type("Zeroed", (), {"read8": staticmethod(lambda _address: 0)})()

        found = doctor._memory(lambda _name: Clean())

        self.assertFalse(found.ok)
        self.assertIn("does not", found.advice or "")

    def test_a_read_that_throws_is_reported_rather_than_swallowed(self) -> None:
        def boom(_name: str) -> Any:
            raise Complaint("no memory at all")

        found = doctor._memory(boom)

        self.assertFalse(found.ok)
        self.assertIn("no memory at all", found.detail)


class CorpusTest(unittest.TestCase):
    def test_a_corpus_that_is_here_is_counted(self) -> None:
        found = doctor.examine(corpus=a_corpus(cases=7))

        self.assertIn("7 cases", " ".join(one.detail for one in found))

    def test_and_carries_the_digest_of_the_file_that_is_actually_here(self) -> None:
        import hashlib

        where = a_corpus()

        found = doctor.examine(corpus=where)

        digest = hashlib.sha256(where.read_bytes()).hexdigest()
        self.assertIn(digest, " ".join(one.detail for one in found))

    def test_and_names_what_it_was_recorded_from(self) -> None:
        found = doctor.examine(corpus=a_corpus(reference="somebody else 2.0"))

        self.assertIn("somebody else 2.0", " ".join(one.detail for one in found))

    def test_a_corpus_that_says_nothing_about_its_source_says_so(self) -> None:
        where = Path(tempfile.mkdtemp()) / "corpus.json"
        where.write_text(json.dumps({"cases": [{}]}))

        found = doctor.examine(corpus=where)

        self.assertIn("not stated", " ".join(one.detail for one in found))

    def test_a_corpus_that_is_not_here_is_a_failure(self) -> None:
        found = doctor.examine(corpus=Path("/nowhere/at/all.json"))

        self.assertTrue(any(one.name == "corpus" and not one.ok for one in found))

    def test_a_corpus_that_is_here_and_damaged_is_worse_and_says_so(self) -> None:
        where = Path(tempfile.mkdtemp()) / "corpus.json"
        where.write_text("{ this is not json")

        found = doctor.examine(corpus=where)

        text = " ".join(one.detail for one in found)
        self.assertIn("not readable as JSON", text)
        self.assertIn("sha256", text)

    def test_an_empty_corpus_is_a_failure_rather_than_a_pass(self) -> None:
        where = Path(tempfile.mkdtemp()) / "corpus.json"
        where.write_text(json.dumps({"cases": []}))

        found = doctor.examine(corpus=where)

        self.assertTrue(any(one.name == "corpus" and not one.ok for one in found))

    def test_the_corpus_it_reads_by_default_is_the_one_in_this_repository(self) -> None:
        self.assertTrue(doctor.CORPUS.exists())


class DriverTest(unittest.TestCase):
    def test_a_driver_that_is_built_is_reported_as_here(self) -> None:
        where = Path(tempfile.mkdtemp()) / "driver"
        where.write_bytes(b"not really a driver")

        found = doctor.examine(driver=where)

        self.assertIn("built and here", " ".join(one.detail for one in found))

    def test_one_that_is_not_built_says_what_will_skip(self) -> None:
        found = doctor.examine(driver=Path("/nowhere/at/all"))

        self.assertIn("skip", " ".join(one.detail for one in found))

    def test_and_that_is_not_treated_as_a_failure(self) -> None:
        found = doctor.examine(driver=Path("/nowhere/at/all"))

        for one in found:
            if one.name == "reference driver":
                self.assertTrue(one.ok)


class ReportTest(unittest.TestCase):
    def test_the_report_has_a_line_for_every_finding(self) -> None:
        found = doctor.examine()

        self.assertGreaterEqual(len(doctor.report(found)), len(found))

    def test_it_opens_with_something_that_says_what_it_is(self) -> None:
        self.assertIn("sdsp", doctor.report(doctor.examine())[0])

    def test_an_unhealthy_run_says_how_many_did_not_pass(self) -> None:
        self.assertIn("1", " ".join(doctor.report([a_finding(ok=False)])))

    def test_a_healthy_run_says_there_is_nothing_to_report(self) -> None:
        self.assertIn("nothing to report", " ".join(doctor.report([a_finding(ok=True)])))


class EntryTest(unittest.TestCase):
    def test_a_healthy_run_reports_success(self) -> None:
        self.assertEqual(
            doctor.main([], examine=lambda **_: [a_finding(ok=True)], say=lambda _: None), 0
        )

    def test_an_unhealthy_one_reports_failure(self) -> None:
        self.assertEqual(
            doctor.main([], examine=lambda **_: [a_finding(ok=False)], say=lambda _: None), 1
        )

    def test_the_report_is_printed_rather_than_kept(self) -> None:
        said: list[str] = []

        doctor.main([], examine=lambda **_: [a_finding(ok=True)], say=said.append)

        self.assertTrue(said)

    def test_a_real_run_says_something_about_this_machine(self) -> None:
        said: list[str] = []

        doctor.main([], say=said.append)

        self.assertIn("sdsp", " ".join(said))


if __name__ == "__main__":
    unittest.main()
