import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def load_module(name: str, where: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, where)
    assert spec is not None and spec.loader is not None, "no loader for that path"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


environment = load_module("environment", Path(__file__).resolve().parent / "environment.py")


def nested(where: Path, top: str, leaf: str) -> None:
    deep = where.joinpath(*filter(None, (top, "a" * 120, "b" * 120)))
    deep.mkdir(parents=True)
    (deep / leaf).write_bytes(b"")


class ObservationTest(unittest.TestCase):
    def test_an_observation_carries_what_was_looked_at(self) -> None:
        # Arrange
        name = "thing"

        # Act
        one = environment.Observation(name, True, "found", None)

        # Assert
        self.assertEqual(one.name, "thing")

    def test_a_failing_one_may_carry_what_to_do_about_it(self) -> None:
        # Arrange
        advice = "install it"

        # Act
        one = environment.Observation("thing", False, "missing", advice)

        # Assert
        self.assertEqual(one.advice, "install it")


class InterpreterTest(unittest.TestCase):
    def test_the_command_that_runs_is_the_one_reported(self) -> None:
        # Arrange
        def look(name: str) -> bool:
            return name == "python3"

        # Act
        found = environment.interpreter(look=look)

        # Assert
        self.assertIn("python3", found.detail)

    def test_a_machine_with_only_python_says_to_use_python(self) -> None:
        # Arrange
        def look(name: str) -> bool:
            return name == "python"

        # Act
        found = environment.interpreter(look=look)

        # Assert
        self.assertEqual(("python" in found.detail, "python3" in found.detail), (True, False))

    def test_windows_py_launcher_is_reported_when_it_is_all_there_is(self) -> None:
        # Arrange
        def look(name: str) -> bool:
            return name == "py"

        # Act
        found = environment.interpreter(look=look)

        # Assert
        self.assertIn("py -3", found.detail)

    def test_a_machine_where_none_of_them_resolve_is_not_ok(self) -> None:
        # Arrange
        def look(_name: str) -> bool:
            return False

        # Act
        found = environment.interpreter(look=look)

        # Assert
        self.assertFalse(found.ok)

    def test_and_says_what_to_do_about_it(self) -> None:
        # Arrange
        def look(_name: str) -> bool:
            return False

        # Act
        found = environment.interpreter(look=look)

        # Assert
        self.assertIsInstance(found.advice, str)
        self.assertNotEqual(found.advice, "")


class EncodingTest(unittest.TestCase):
    def test_utf8_output_is_fine(self) -> None:
        # Arrange
        encoding = "utf-8"

        # Act
        found = environment.output_encoding(encoding=encoding)

        # Assert
        self.assertTrue(found.ok)

    def test_a_legacy_windows_codepage_is_not(self) -> None:
        # Arrange
        encoding = "cp1252"

        # Act
        found = environment.output_encoding(encoding=encoding)

        # Assert
        self.assertFalse(found.ok)

    def test_and_the_advice_names_the_switch_that_fixes_it(self) -> None:
        # Arrange
        encoding = "cp1252"

        # Act
        found = environment.output_encoding(encoding=encoding)

        # Assert
        self.assertIn("PYTHONUTF8", found.advice)

    def test_an_unknown_encoding_is_reported_rather_than_guessed(self) -> None:
        # Arrange
        encoding = None

        # Act
        found = environment.output_encoding(encoding=encoding)

        # Assert
        self.assertFalse(found.ok)


class LineEndingTest(unittest.TestCase):
    def test_a_tree_whose_text_files_use_line_feeds_is_fine(self) -> None:
        # Arrange
        where = Path(tempfile.mkdtemp())
        (where / "a.md").write_bytes(b"one\ntwo\n")

        # Act
        found = environment.line_endings(where)

        # Assert
        self.assertTrue(found.ok)

    def test_a_tree_that_git_converted_to_carriage_returns_is_not(self) -> None:
        # Arrange
        where = Path(tempfile.mkdtemp())
        (where / "a.md").write_bytes(b"one\r\ntwo\r\n")

        # Act
        found = environment.line_endings(where)

        # Assert
        self.assertFalse(found.ok)

    def test_and_the_advice_names_the_setting_that_caused_it(self) -> None:
        # Arrange
        where = Path(tempfile.mkdtemp())
        (where / "a.md").write_bytes(b"one\r\n")

        # Act
        found = environment.line_endings(where)

        # Assert
        self.assertIn("autocrlf", found.advice)

    def test_a_tree_with_nothing_to_read_says_so_rather_than_passing(self) -> None:
        # Arrange
        where = Path(tempfile.mkdtemp())

        # Act
        found = environment.line_endings(where)

        # Assert
        self.assertIn("nothing", found.detail)

    def test_a_sample_that_fills_up_stops_reading(self) -> None:
        # Arrange
        where = Path(tempfile.mkdtemp())
        for n in range(3):
            (where / f"{n}.md").write_bytes(b"one\n")

        # Act
        found = environment.line_endings(where, sample=1)

        # Assert
        self.assertIn("1 sampled", found.detail)

    def test_a_file_it_cannot_read_is_passed_over_rather_than_counted(self) -> None:
        # Arrange
        where = Path(tempfile.mkdtemp())
        (where / "a.md").write_bytes(b"one\n")
        bad = where / "b.md"
        bad.write_bytes(b"two\r\n")
        bad.chmod(0o000)
        self.addCleanup(bad.chmod, 0o600)

        # Act
        found = environment.line_endings(where)

        # Assert
        self.assertTrue(found.ok)


class CaseTest(unittest.TestCase):
    def test_a_case_sensitive_filesystem_is_reported_as_such(self) -> None:
        # Arrange
        where = Path(tempfile.mkdtemp())

        # Act
        found = environment.filesystem_case(where)

        # Assert
        self.assertIn("sensitive", found.detail)

    def test_the_check_never_fails_a_machine_for_its_filesystem(self) -> None:
        # Arrange
        where = Path(tempfile.mkdtemp())

        # Act
        found = environment.filesystem_case(where)

        # Assert
        self.assertTrue(found.ok)


class PathBudgetTest(unittest.TestCase):
    def test_a_short_path_on_windows_is_fine(self) -> None:
        # Arrange
        root = Path("C:/a")

        # Act
        found = environment.path_budget(root, windows=True, longest=80)

        # Assert
        self.assertTrue(found.ok)

    def test_a_path_past_the_windows_limit_is_not(self) -> None:
        # Arrange
        root = Path("C:/a")

        # Act
        found = environment.path_budget(root, windows=True, longest=300)

        # Assert
        self.assertFalse(found.ok)

    def test_and_the_advice_names_the_setting_that_lifts_it(self) -> None:
        # Arrange
        root = Path("C:/a")

        # Act
        found = environment.path_budget(root, windows=True, longest=300)

        # Assert
        self.assertIn("LongPathsEnabled", found.advice)

    def test_the_same_length_elsewhere_is_still_reported(self) -> None:
        # Arrange
        root = Path("/a")

        # Act
        found = environment.path_budget(root, windows=False, longest=300)

        # Assert
        self.assertFalse(found.ok)

    def test_because_the_tree_is_shared_rather_than_local_to_one_machine(self) -> None:
        # Arrange
        roots = ((Path("/a"), False), (Path("C:/a"), True))

        # Act
        found = [environment.path_budget(root, windows=on, longest=300).ok for root, on in roots]

        # Assert
        self.assertEqual(found, [False, False])

    def test_the_headroom_a_windows_checkout_would_have_is_reported(self) -> None:
        # Arrange
        root = Path("/a")

        # Act
        found = environment.path_budget(root, windows=False, longest=100)

        # Assert
        self.assertIn("160", found.detail)

    def test_a_tree_that_leaves_no_room_for_a_checkout_path_is_flagged_anywhere(self) -> None:
        # Arrange
        root = Path("/a")

        # Act
        found = environment.path_budget(root, windows=False, longest=250)

        # Assert
        self.assertFalse(found.ok)

    def test_and_the_advice_says_it_is_about_windows_rather_than_here(self) -> None:
        # Arrange
        root = Path("/a")

        # Act
        found = environment.path_budget(root, windows=False, longest=250)

        # Assert
        self.assertIn("Windows", found.advice)

    def test_a_tree_with_room_to_spare_passes_on_every_system(self) -> None:
        # Arrange
        systems = (True, False)

        # Act
        found = [environment.path_budget(Path("/a"), windows=on, longest=100).ok for on in systems]

        # Assert
        self.assertEqual(found, [True, True])

    def test_a_generated_directory_is_reported_without_failing_the_check(self) -> None:
        # Arrange
        where = Path(tempfile.mkdtemp())
        nested(where, "node_modules", "c.js")

        # Act
        found = environment.path_budget(where)

        # Assert
        self.assertTrue(found.ok)

    def test_but_the_same_depth_in_tracked_content_does_fail_it(self) -> None:
        # Arrange
        where = Path(tempfile.mkdtemp())
        nested(where, "", "c.py")

        # Act
        found = environment.path_budget(where)

        # Assert
        self.assertFalse(found.ok)

    def test_and_a_generated_one_is_still_named_so_it_is_not_a_surprise(self) -> None:
        # Arrange
        where = Path(tempfile.mkdtemp())
        nested(where, "node_modules", "c.js")

        # Act
        found = environment.path_budget(where)

        # Assert
        self.assertIn("node_modules", found.detail)


if __name__ == "__main__":
    unittest.main()
