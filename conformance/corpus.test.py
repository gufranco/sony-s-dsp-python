import contextlib
import importlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from typing import override

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "conformance"))

corpus = importlib.import_module("corpus")


class DefinitionTest(unittest.TestCase):
    def test_the_repository_ships_a_corpus(self) -> None:
        self.assertTrue(corpus.load()["cases"])

    def test_the_corpus_names_the_chip_its_audio_came_from(self) -> None:
        self.assertIn("snes9x", corpus.load()["reference"])

    def test_the_corpus_records_the_census_it_was_drawn_from(self) -> None:
        found = corpus.load()["census"]

        self.assertGreater(found["states"], 0)
        self.assertTrue(found["directories"])

    def test_a_corpus_is_read_from_where_it_is_asked_for(self) -> None:
        with tempfile.TemporaryDirectory() as where:
            path = Path(where) / "c.json"
            path.write_text(json.dumps({"cases": [], "reference": "x", "samples": 1}))

            self.assertEqual(corpus.load(path)["reference"], "x")


class ShapeTest(unittest.TestCase):
    def test_every_case_carries_a_whole_register_file(self) -> None:
        wrong = [c for c in corpus.load()["cases"] if len(c["registers"]) != 128]

        self.assertEqual(wrong, [])

    def test_the_cases_use_many_different_sample_directories(self) -> None:
        pages = {c["registers"][0x5D] for c in corpus.load()["cases"]}

        self.assertGreater(len(pages), 20)

    def test_the_cases_reach_the_envelope_the_echo_and_the_noise(self) -> None:
        cases = corpus.load()["cases"]

        self.assertTrue(any(c["registers"][0x4D] for c in cases))
        self.assertTrue(any(c["registers"][0x3D] for c in cases))
        self.assertTrue(any(c["registers"][v * 0x10 + 5] & 0x80 for c in cases for v in range(8)))

    def test_the_corpus_holds_no_audio_data(self) -> None:
        self.assertEqual(
            sorted(corpus.load()["cases"][0]),
            ["output_head", "output_sha256", "ram_seed", "registers", "samples"],
        )


class RamTest(unittest.TestCase):
    def test_the_sample_data_is_rebuilt_from_its_seed(self) -> None:
        case = corpus.load()["cases"][0]

        self.assertEqual(corpus.ram_for(case), corpus.ram_for(case))

    def test_the_sample_data_fills_the_whole_space(self) -> None:
        self.assertEqual(len(corpus.ram_for(corpus.load()["cases"][0])), 0x10000)

    def test_a_source_number_that_runs_past_the_space_falls_back(self) -> None:
        case = dict(corpus.load()["cases"][0])
        registers = list(case["registers"])
        registers[corpus.V_SRCN] = 212
        case["registers"] = registers

        ram = corpus.ram_for(case)
        entry = (case["registers"][0x5D] * 0x100 + 212 * 4) & 0xFFFF
        start = ram[entry] | (ram[entry + 1] << 8)

        self.assertEqual(start, corpus.FIRST_SAMPLE)

    def test_the_directory_points_where_the_real_registers_said(self) -> None:
        case = corpus.load()["cases"][0]
        ram = corpus.ram_for(case)
        entry = (case["registers"][0x5D] * 0x100 + case["registers"][0x04] * 4) & 0xFFFF

        start = ram[entry] | (ram[entry + 1] << 8)

        self.assertEqual(ram[start] & 0x03, 0)


class CheckTest(unittest.TestCase):
    def test_a_matching_case_reports_nothing(self) -> None:
        self.assertIsNone(corpus.check(corpus.load()["cases"][0]))

    def test_a_disagreement_is_reported(self) -> None:
        wrong = dict(corpus.load()["cases"][0], output_sha256="0" * 64)

        self.assertIsNotNone(corpus.check(wrong))

    def test_a_case_that_cannot_run_is_reported_rather_than_raising(self) -> None:
        broken = dict(corpus.load()["cases"][0], registers="not a register file")

        self.assertIsNotNone(corpus.check(broken))


class RunTest(unittest.TestCase):
    def test_the_whole_shipped_corpus_agrees(self) -> None:
        found = corpus.load()

        passed, failed, examples = corpus.run(found["cases"])

        self.assertEqual(failed, 0)
        self.assertEqual(examples, [])
        self.assertEqual(passed, len(found["cases"]))

    def test_a_disagreeing_case_is_counted_and_kept(self) -> None:
        wrong = dict(corpus.load()["cases"][0], output_sha256="0" * 64)

        passed, failed, examples = corpus.run([wrong])

        self.assertEqual((passed, failed), (0, 1))
        self.assertEqual(len(examples), 1)

    def test_only_a_few_examples_are_kept(self) -> None:
        wrong = dict(corpus.load()["cases"][0], output_sha256="0" * 64)

        _, _, examples = corpus.run([wrong] * 40)

        self.assertLessEqual(len(examples), corpus.EXAMPLE_LIMIT)


class MainTest(unittest.TestCase):
    @override
    def setUp(self) -> None:
        self.root = tempfile.mkdtemp(prefix="corpus-")
        self.addCleanup(shutil.rmtree, self.root, True)

    def run_main(self, argv: list[str]) -> tuple[int, str]:
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            code = corpus.main(argv)
        return code, captured.getvalue()

    def test_no_arguments_runs_the_corpus_that_ships(self) -> None:
        code, output = self.run_main([])

        self.assertEqual(code, 0)
        self.assertIn("agreed", output)

    def test_a_corpus_that_is_not_there_is_reported(self) -> None:
        code, output = self.run_main([str(Path(self.root) / "absent.json")])

        self.assertEqual(code, 2)
        self.assertIn("no corpus at", output)

    def test_a_disagreeing_corpus_fails(self) -> None:
        found = corpus.load()
        broken = dict(found, cases=[dict(found["cases"][0], output_sha256="0" * 64)])
        path = Path(self.root) / "broken.json"
        path.write_text(json.dumps(broken))

        code, output = self.run_main([str(path)])

        self.assertEqual(code, 1)
        self.assertIn("1 did not", output)


if __name__ == "__main__":
    unittest.main()
