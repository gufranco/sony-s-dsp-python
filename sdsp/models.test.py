import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sdsp


def refusal(name: str | None) -> str:
    try:
        sdsp.Chip(name, sdsp.Memory(fill=0))
    except sdsp.UnknownModelError as error:
        return str(error)
    return ""


class CatalogueTest(unittest.TestCase):
    def test_the_package_names_every_model_it_covers(self) -> None:
        # Arrange
        catalogue = sdsp.MODELS

        # Act
        names = sorted(catalogue)

        # Assert
        self.assertEqual(names, ["s-dsp"])

    def test_a_model_says_what_it_is_and_what_it_carries(self) -> None:
        # Arrange
        catalogue = sdsp.MODELS

        # Act
        found = catalogue["s-dsp"]

        # Assert
        self.assertEqual(
            (bool(found.summary), found.name, found.voices, found.registers),
            (True, "s-dsp", 8, 128),
        )

    def test_a_model_name_is_matched_however_it_is_written(self) -> None:
        # Arrange
        written = ("S-DSP", "sdsp", "S_DSP", "snes-dsp", " SNES_DSP ")

        # Act
        found = {sdsp.Chip(name, sdsp.Memory(fill=0)).model for name in written}

        # Assert
        self.assertEqual(found, {"s-dsp"})

    def test_every_alias_the_catalogue_lists_builds_the_model(self) -> None:
        # Arrange
        aliases = sdsp.MODELS["s-dsp"].aliases

        # Act
        found = {sdsp.Chip(alias, sdsp.Memory(fill=0)).model for alias in aliases}

        # Assert
        self.assertEqual((found, aliases), ({"s-dsp"}, ("sdsp", "sonysdsp", "dsp", "snesdsp")))

    def test_a_model_the_package_does_not_have_is_refused_by_name(self) -> None:
        # Arrange
        name = "spc700"

        # Act
        said = refusal(name)

        # Assert
        self.assertEqual(said, "spc700 is not a model this package covers; it has s-dsp")

    def test_a_model_prints_as_its_name_and_voices(self) -> None:
        # Arrange
        model = sdsp.MODELS["s-dsp"]

        # Act
        printed = repr(model)

        # Assert
        self.assertEqual(printed, "<Model s-dsp, 8 voices>")


class BuildTest(unittest.TestCase):
    def test_a_chip_is_built_from_its_model_name(self) -> None:
        # Arrange
        memory = sdsp.Memory(fill=0)

        # Act
        built = sdsp.Chip("s-dsp", memory)

        # Assert
        self.assertEqual((built.model, built.memory), ("s-dsp", memory))

    def test_a_model_record_builds_the_part_it_describes(self) -> None:
        # Arrange
        model = sdsp.MODELS["s-dsp"]

        # Act
        built = model.build(sdsp.Memory(fill=0), seed=0x1234)

        # Assert
        self.assertEqual((built.model, built.registers), ("s-dsp", sdsp.scramble(128, 0x1234)))

    def test_a_chip_built_without_memory_gets_sparse_memory(self) -> None:
        # Arrange
        name = "s-dsp"

        # Act
        built = sdsp.Chip(name)

        # Assert
        self.assertIsInstance(built.memory, sdsp.SparseMemory)

    def test_options_reach_the_chip_that_gets_built(self) -> None:
        # Arrange
        seed = 0x1234

        # Act
        built = sdsp.Chip("s-dsp", sdsp.Memory(fill=0), seed=seed)

        # Assert
        self.assertEqual(built.registers, sdsp.scramble(128, seed))

    def test_a_chip_built_by_name_arrives_unreset(self) -> None:
        # Arrange
        memory = sdsp.Memory(fill=0)

        # Act
        built = sdsp.Chip("s-dsp", memory)

        # Assert
        self.assertEqual(built.registers, sdsp.scramble(128))

    def test_and_no_option_asks_for_it_to_arrive_reset(self) -> None:
        # Arrange
        memory = sdsp.Memory(fill=0)

        # Act
        refused = self.assertRaises(TypeError)
        with refused:
            sdsp.Chip("s-dsp", memory, reset=True)

        # Assert
        self.assertIn("reset", str(refused.exception))

    def test_a_model_the_package_does_not_have_is_refused_at_construction(self) -> None:
        # Arrange
        name = "ym2612"

        # Act
        said = refusal(name)

        # Assert
        self.assertIn("ym2612", said)


class NamingNoneTest(unittest.TestCase):
    def test_building_without_naming_a_model_is_refused_naming_every_model(self) -> None:
        # Arrange
        name = None

        # Act
        said = refusal(name)

        # Assert
        self.assertEqual(
            said,
            "no model was named, and this package will not choose one for you. Name one of: s-dsp",
        )

    def test_a_named_model_is_not_refused(self) -> None:
        # Arrange
        name = "s-dsp"

        # Act
        said = refusal(name)

        # Assert
        self.assertEqual(said, "")

    def test_nothing_named_describe_or_default_model_is_published(self) -> None:
        # Arrange
        names = ("describe", "DEFAULT_MODEL")

        # Act
        published = [name for name in names if hasattr(sdsp, name)]

        # Assert
        self.assertEqual(published, [])


if __name__ == "__main__":
    unittest.main()
