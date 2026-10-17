import random
from typing import TYPE_CHECKING

from .tables import COUNTER_RANGE
from .voice import BYTE, WORD, Voice, signed_draw

if TYPE_CHECKING:  # pragma: no cover
    from .core import MemoryLike

REGISTER_COUNT = 128
VOICE_COUNT = 8
CLOCKS = 32
STEREO = 2
SEED_BITS = 32

REG_FLG = 0x6C
RESET_FLAGS = 0xE0

NOISE_SPAN = 0x8000
NOISE_RESET = 0x4000
NOISE_TAP = 0x4000

PITCH_SPAN = 0x4000
ECHO_HISTORY = 8
ECHO_DELAY_STEP = 0x800
ECHO_DELAYS = 16


def next_noise(noise: int) -> int:
    feedback = (noise << 13) ^ (noise << 14)
    return (feedback & NOISE_TAP) ^ (noise >> 1)


def _pair(scrambled: random.Random, span: int) -> list[int]:
    return [signed_draw(scrambled, span) for _ in range(STEREO)]


class State:
    __slots__ = (
        "counter",
        "echo_enabled",
        "echo_history",
        "echo_history_position",
        "echo_in",
        "echo_length",
        "echo_offset",
        "echo_out",
        "echo_pointer",
        "endx_buffer",
        "envx_buffer",
        "every_other_sample",
        "kon",
        "kon_check",
        "main_out",
        "new_kon",
        "noise",
        "outx_buffer",
        "phase",
        "registers",
        "t_adsr0",
        "t_brr_byte",
        "t_brr_header",
        "t_brr_next_address",
        "t_dir",
        "t_dir_address",
        "t_eon",
        "t_esa",
        "t_koff",
        "t_looped",
        "t_non",
        "t_output",
        "t_pitch",
        "t_pmon",
        "t_srcn",
        "voices",
    )

    memory: "MemoryLike"
    rendered: list[int]

    def _power_on(self, scrambled: random.Random) -> None:
        self.registers = bytearray(scrambled.randbytes(REGISTER_COUNT))
        self.voices = [
            Voice(index, scrambled.getrandbits(SEED_BITS)) for index in range(VOICE_COUNT)
        ]
        self.phase = scrambled.randrange(CLOCKS)
        self.counter = scrambled.randrange(COUNTER_RANGE)
        self.noise = scrambled.randrange(1, NOISE_SPAN)
        self.every_other_sample = scrambled.randrange(2)
        self.kon = scrambled.randrange(BYTE)
        self.new_kon = scrambled.randrange(BYTE)
        self.kon_check = bool(scrambled.randrange(2))
        self.echo_offset = scrambled.randrange(WORD)
        self.echo_length = scrambled.randrange(ECHO_DELAYS) * ECHO_DELAY_STEP
        history = [_pair(scrambled, WORD // 2) for _ in range(ECHO_HISTORY)]
        self.echo_history = [list(pair) for pair in history + history]
        self.echo_history_position = scrambled.randrange(ECHO_HISTORY)
        self.main_out = _pair(scrambled, WORD)
        self.echo_out = _pair(scrambled, WORD)
        self.echo_in = _pair(scrambled, WORD)
        self.echo_pointer = scrambled.randrange(WORD)
        self.echo_enabled = scrambled.randrange(BYTE)
        self._power_on_latches(scrambled)

    def _power_on_latches(self, scrambled: random.Random) -> None:
        self.t_pmon = scrambled.randrange(BYTE)
        self.t_non = scrambled.randrange(BYTE)
        self.t_eon = scrambled.randrange(BYTE)
        self.t_dir = scrambled.randrange(BYTE)
        self.t_koff = scrambled.randrange(BYTE)
        self.t_esa = scrambled.randrange(BYTE)
        self.t_srcn = scrambled.randrange(BYTE)
        self.t_dir_address = scrambled.randrange(WORD)
        self.t_brr_next_address = scrambled.randrange(WORD)
        self.t_adsr0 = scrambled.randrange(BYTE)
        self.t_pitch = scrambled.randrange(PITCH_SPAN)
        self.t_brr_byte = scrambled.randrange(BYTE)
        self.t_brr_header = scrambled.randrange(BYTE)
        self.t_output = signed_draw(scrambled, WORD)
        self.t_looped = scrambled.randrange(BYTE)
        self.endx_buffer = scrambled.randrange(BYTE)
        self.outx_buffer = scrambled.randrange(BYTE)
        self.envx_buffer = scrambled.randrange(BYTE)

    def _define(self) -> None:
        self.registers[:] = bytes(REGISTER_COUNT)
        self.registers[REG_FLG] = RESET_FLAGS
        for voice in self.voices:
            voice.reset()
        self.phase = 0
        self.counter = 0
        self.noise = NOISE_RESET
        self.every_other_sample = 1
        self.kon = 0
        self.new_kon = 0
        self.kon_check = False
        self.echo_offset = 0
        self.echo_length = 0
        self.echo_history = [[0, 0] for _ in range(ECHO_HISTORY * 2)]
        self.echo_history_position = 0
        self.main_out = [0, 0]
        self.echo_out = [0, 0]
        self.echo_in = [0, 0]
        self.echo_pointer = 0
        self.echo_enabled = 0
        self._define_latches()

    def _define_latches(self) -> None:
        self.t_pmon = 0
        self.t_non = 0
        self.t_eon = 0
        self.t_dir = 0
        self.t_koff = 0
        self.t_esa = 0
        self.t_srcn = 0
        self.t_dir_address = 0
        self.t_brr_next_address = 0
        self.t_adsr0 = 0
        self.t_pitch = 0
        self.t_brr_byte = 0
        self.t_brr_header = 0
        self.t_output = 0
        self.t_looped = 0
        self.endx_buffer = 0
        self.outx_buffer = 0
        self.envx_buffer = 0
