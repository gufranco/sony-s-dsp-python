import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sdsp
from sdsp import errors, models
from sdsp.memory import Memory


class CatalogueTest(unittest.TestCase):
    def test_the_package_names_every_model_it_covers(self) -> None:
        self.assertIn("s-dsp", models.MODELS)

    def test_a_model_says_what_it_is_and_what_it_carries(self) -> None:
        found = models.lookup("s-dsp")

        self.assertTrue(found.summary)
        self.assertEqual(found.voices, 8)
        self.assertEqual(found.registers, 128)

    def test_a_model_name_is_matched_however_it_is_written(self) -> None:
        for written in ("S-DSP", "sdsp", "S_DSP", "snes-dsp"):
            self.assertEqual(models.lookup(written).name, "s-dsp")

    def test_a_model_the_package_does_not_have_is_refused_by_name(self) -> None:
        with self.assertRaises(errors.UnknownModelError):
            models.lookup("spc700")

    def test_the_refusal_lists_what_is_available(self) -> None:
        with self.assertRaises(errors.UnknownModelError) as raised:
            models.lookup("nonsense")

        self.assertIn("s-dsp", str(raised.exception))

    def test_a_model_prints_as_its_name_and_voices(self) -> None:
        printed = repr(models.lookup("s-dsp"))

        self.assertIn("s-dsp", printed)
        self.assertIn("8", printed)


class BuildTest(unittest.TestCase):
    def test_a_chip_is_built_from_its_model_name(self) -> None:
        self.assertEqual(sdsp.Chip("s-dsp", Memory(fill=0)).model, "s-dsp")

    def test_the_default_model_is_the_one_the_console_carries(self) -> None:
        self.assertEqual(sdsp.Chip("s-dsp", memory=Memory(fill=0)).model, "s-dsp")

    def test_options_reach_the_chip_that_gets_built(self) -> None:
        built = sdsp.Chip("s-dsp", Memory(fill=0), reset=False)

        self.assertEqual(len(built.registers), 128)

    def test_a_model_the_package_does_not_have_is_refused_at_construction(self) -> None:
        with self.assertRaises(errors.UnknownModelError):
            sdsp.Chip("ym2612", Memory(fill=0))


class NamingNoneTest(unittest.TestCase):
    """That leaving the model out is refused, and refused usefully."""

    def test_building_without_naming_a_model_is_refused(self) -> None:
        with self.assertRaises(errors.UnknownModelError):
            sdsp.Chip()

    def test_and_the_refusal_names_every_model_there_is(self) -> None:
        with self.assertRaises(errors.UnknownModelError) as caught:
            sdsp.Chip()

        missing = [name for name in sdsp.MODELS if name not in str(caught.exception)]

        self.assertEqual(missing, [])

    def test_nothing_named_describe_is_published(self) -> None:
        self.assertFalse(hasattr(sdsp, "describe"))

    def test_and_no_default_model_is_published_either(self) -> None:
        self.assertFalse(hasattr(sdsp, "DEFAULT_MODEL"))


if __name__ == "__main__":
    unittest.main()
