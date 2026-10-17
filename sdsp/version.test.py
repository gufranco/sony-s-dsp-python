import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sdsp

HERE = Path(__file__).resolve().parent

STAMPED = re.compile(r'^VERSION = "([^"]+)"$', re.M)


def stamped() -> str:
    found = STAMPED.search((HERE / "version.py").read_text())
    return found.group(1) if found else ""


class VersionTest(unittest.TestCase):
    def test_the_version_is_three_numbers(self) -> None:
        # Arrange
        version = sdsp.__version__

        # Act
        parts = version.split(".")

        # Assert
        self.assertEqual([part.isdigit() for part in parts], [True, True, True])

    def test_the_package_reports_the_version_the_release_job_stamped(self) -> None:
        # Arrange
        written = stamped()

        # Act
        reported = sdsp.__version__

        # Assert
        self.assertEqual(reported, written)


if __name__ == "__main__":
    unittest.main()
