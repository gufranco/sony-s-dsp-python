import contextlib
import importlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "conformance"))

capture = importlib.import_module("capture")


def a_dump(registers=None, magic=capture.MAGIC):
    blob = bytearray(capture.REGISTERS_AT + capture.REGISTER_COUNT)
    blob[: len(magic)] = magic
    if registers:
        blob[capture.REGISTERS_AT : capture.REGISTERS_AT + len(registers)] = registers
    return bytes(blob)


class ReadTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="capture-")
        self.addCleanup(shutil.rmtree, self.root, True)

    def write(self, blob, name="one.spc"):
        path = Path(self.root) / name
        path.write_bytes(blob)
        return path

    def test_a_dump_gives_back_its_registers(self):
        path = self.write(a_dump(bytes([7]) * capture.REGISTER_COUNT))

        self.assertEqual(capture.registers(path), [7] * capture.REGISTER_COUNT)

    def test_a_file_that_is_not_a_dump_is_refused(self):
        path = self.write(b"not a dump" * 40)

        self.assertIsNone(capture.registers(path))

    def test_a_dump_cut_short_is_refused(self):
        path = self.write(a_dump()[:100])

        self.assertIsNone(capture.registers(path))

    def test_a_path_that_cannot_be_opened_is_refused(self):
        self.assertIsNone(capture.registers(Path(self.root)))

    def test_nothing_but_the_registers_is_read(self):
        blob = bytearray(a_dump(bytes([9]) * capture.REGISTER_COUNT))
        blob[capture.RAM_AT : capture.RAM_AT + 64] = b"\xab" * 64

        path = self.write(bytes(blob))

        self.assertNotIn(0xAB, capture.registers(path))


class CensusTest(unittest.TestCase):
    def test_a_census_counts_the_states_it_saw(self):
        found = capture.census([[0] * 128, [1] * 128])

        self.assertEqual(found["states"], 2)

    def test_a_census_records_the_sample_directory_pages_used(self):
        one = [0] * 128
        one[0x5D] = 0x40

        found = capture.census([one])

        self.assertEqual(found["directories"]["64"], 1)

    def test_a_census_records_how_many_voices_use_the_envelope(self):
        one = [0] * 128
        one[0x05] = 0x80

        found = capture.census([one])

        self.assertEqual(found["adsr_voices"], 1)

    def test_a_census_records_the_echo_delays_used(self):
        one = [0] * 128
        one[0x7D] = 0x07

        found = capture.census([one])

        self.assertEqual(found["echo_delays"]["7"], 1)

    def test_a_census_notices_pitch_modulation_and_noise(self):
        one = [0] * 128
        one[0x2D] = 0x02
        one[0x3D] = 0x01

        found = capture.census([one])

        self.assertEqual((found["pitch_modulation"], found["noise"]), (1, 1))

    def test_a_census_holds_no_audio(self):
        found = capture.census([[0] * 128])

        self.assertEqual(
            sorted(found),
            [
                "adsr_voices",
                "comment",
                "directories",
                "echo_delays",
                "echo_send",
                "flags",
                "noise",
                "pitch_modulation",
                "states",
            ],
        )


class MainTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="capture-main-")
        self.addCleanup(shutil.rmtree, self.root, True)
        for index in range(3):
            registers = bytearray(capture.REGISTER_COUNT)
            registers[0x5D] = 0x20 + index
            (Path(self.root) / f"{index}.spc").write_bytes(a_dump(bytes(registers)))

    def run_main(self, argv):
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            code = capture.main(argv)
        return code, captured.getvalue()

    def test_no_arguments_explains_how_to_call_it(self):
        code, output = self.run_main([])

        self.assertEqual(code, 2)
        self.assertIn("usage", output)

    def test_a_directory_that_is_not_there_is_reported(self):
        code, output = self.run_main([str(Path(self.root) / "absent"), "out.json"])

        self.assertEqual(code, 2)
        self.assertIn("nothing at", output)

    def test_a_directory_of_dumps_becomes_a_census(self):
        out = Path(self.root) / "census.json"

        code, output = self.run_main([str(self.root), str(out)])

        self.assertEqual(code, 0)
        self.assertIn("3 register states", output)
        self.assertEqual(json.loads(out.read_text())["states"], 3)

    def test_a_directory_with_no_dumps_says_so(self):
        empty = Path(self.root) / "empty"
        empty.mkdir()

        code, output = self.run_main([str(empty), str(Path(self.root) / "c.json")])

        self.assertEqual(code, 1)
        self.assertIn("no dumps", output)

    def test_a_limit_takes_only_the_first_few_dumps(self):
        out = Path(self.root) / "census.json"

        code, _ = self.run_main([str(self.root), str(out), "2"])

        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.read_text())["states"], 2)


if __name__ == "__main__":
    unittest.main()
