import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import sdsp  # noqa: E402
from sdsp import doctor  # noqa: E402

SOURCE = ROOT / "sdsp" / "doctor.py"

VERDICT = re.compile(r"^  (\d+ checks, nothing to report|\d+ of \d+ checks did not pass)$")


def a_finding(
    name: str = "something", ok: bool = True, detail: str = "detail", advice: str | None = None
) -> Any:
    return doctor.Finding(name, ok, detail, advice)


class ReportTest(unittest.TestCase):
    def test_the_report_has_a_line_for_every_finding(self) -> None:
        # Arrange
        found = doctor.examine()

        # Act
        lines = doctor.report(found)

        # Assert
        self.assertEqual([one.report in lines for one in found], [True] * len(found))

    def test_it_opens_with_something_that_says_what_it_is(self) -> None:
        # Arrange
        found = [a_finding()]

        # Act
        lines = doctor.report(found)

        # Assert
        self.assertTrue(lines[0].startswith(f"sdsp {sdsp.__version__} on "))

    def test_an_unhealthy_run_says_how_many_did_not_pass(self) -> None:
        # Arrange
        found = [a_finding(ok=False), a_finding(ok=True)]

        # Act
        lines = doctor.report(found)

        # Assert
        self.assertEqual(lines[-1], "  1 of 2 checks did not pass")

    def test_a_healthy_run_says_there_is_nothing_to_report(self) -> None:
        # Arrange
        found = [a_finding(ok=True)]

        # Act
        lines = doctor.report(found)

        # Assert
        self.assertEqual(lines[-1], "  1 checks, nothing to report")


class EntryTest(unittest.TestCase):
    def test_a_healthy_run_reports_success_and_prints_its_report(self) -> None:
        # Arrange
        said: list[str] = []

        # Act
        code = doctor.main([], examine=lambda **_: [a_finding(ok=True)], say=said.append)

        # Assert
        self.assertEqual((code, said[-1]), (0, "  1 checks, nothing to report"))

    def test_an_unhealthy_one_reports_failure(self) -> None:
        # Arrange
        said: list[str] = []

        # Act
        code = doctor.main([], examine=lambda **_: [a_finding(ok=False)], say=said.append)

        # Assert
        self.assertEqual((code, said[-1]), (1, "  1 of 1 checks did not pass"))

    def test_a_real_run_says_something_about_this_machine(self) -> None:
        # Arrange
        said: list[str] = []

        # Act
        doctor.main([], say=said.append)

        # Assert
        self.assertIn("  the machine", said)


class TheDoctorRunsWhereThePackageMightNotImportTest(unittest.TestCase):
    def test_a_root_that_is_not_on_the_path_is_put_there(self) -> None:
        # Arrange
        path: list[str] = []

        # Act
        added = doctor.reachable(Path("/somewhere"), path)

        # Assert
        self.assertEqual((added, path), (True, ["/somewhere"]))

    def test_a_root_already_on_the_path_is_left_alone(self) -> None:
        # Arrange
        path = ["/somewhere"]

        # Act
        added = doctor.reachable(Path("/somewhere"), path)

        # Assert
        self.assertEqual((added, path), (False, ["/somewhere"]))


class TheDoctorRunsAsTheReadmeSaysTest(unittest.TestCase):
    def test_running_it_as_a_file_from_elsewhere_prints_a_report_rather_than_a_traceback(
        self,
    ) -> None:
        # Arrange
        elsewhere = tempfile.mkdtemp()
        environ = {name: value for name, value in os.environ.items() if name != "PYTHONPATH"}

        # Act
        finished = subprocess.run(
            [sys.executable, str(SOURCE)],
            capture_output=True,
            text=True,
            cwd=elsewhere,
            env=environ,
            check=False,
        )

        # Assert
        self.assertEqual(
            (finished.returncode in (0, 1), "Traceback" in finished.stderr),
            (True, False),
        )
        self.assertRegex(finished.stdout.splitlines()[-1], VERDICT)

    def test_the_readme_names_the_invocation_that_works(self) -> None:
        # Arrange
        readme = ROOT / "README.md"

        # Act
        said = readme.read_text()

        # Assert
        self.assertIn("python3 sdsp/doctor.py", said)


if __name__ == "__main__":
    unittest.main()
