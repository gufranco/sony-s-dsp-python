import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sdsp
from sdsp import models
from sdsp.memory import Memory


class CatalogueTest(unittest.TestCase):
    def test_the_package_names_every_model_it_covers(self):
        self.assertIn("s-dsp", models.MODELS)

    def test_a_model_says_what_it_is_and_what_it_carries(self):
        found = models.describe("s-dsp")

        self.assertTrue(found.summary)
        self.assertEqual(found.voices, 8)
        self.assertEqual(found.registers, 128)

    def test_a_model_name_is_matched_however_it_is_written(self):
        for written in ("S-DSP", "sdsp", "S_DSP", "snes-dsp"):
            self.assertEqual(models.describe(written).name, "s-dsp")

    def test_a_model_the_package_does_not_have_is_refused_by_name(self):
        with self.assertRaises(models.UnknownModelError):
            models.describe("spc700")

    def test_the_refusal_lists_what_is_available(self):
        with self.assertRaises(models.UnknownModelError) as raised:
            models.describe("nonsense")

        self.assertIn("s-dsp", str(raised.exception))

    def test_a_model_prints_as_its_name_and_voices(self):
        printed = repr(models.describe("s-dsp"))

        self.assertIn("s-dsp", printed)
        self.assertIn("8", printed)


class BuildTest(unittest.TestCase):
    def test_a_chip_is_built_from_its_model_name(self):
        self.assertEqual(sdsp.Sdsp(Memory(fill=0), model="s-dsp").model, "s-dsp")

    def test_the_default_model_is_the_one_the_console_carries(self):
        self.assertEqual(sdsp.Sdsp(Memory(fill=0)).model, "s-dsp")

    def test_options_reach_the_chip_that_gets_built(self):
        built = sdsp.Sdsp(Memory(fill=0), model="s-dsp", reset=False)

        self.assertEqual(len(built.registers), 128)

    def test_a_model_the_package_does_not_have_is_refused_at_construction(self):
        with self.assertRaises(models.UnknownModelError):
            sdsp.Sdsp(Memory(fill=0), model="ym2612")


if __name__ == "__main__":
    unittest.main()
