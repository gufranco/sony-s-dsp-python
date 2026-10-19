import random
from collections.abc import Callable, Sequence
from typing import Protocol

from .echo import Echo
from .memory import UNSET_SEED
from .state import REG_FLG, next_noise
from .tables import COUNTER_OFFSETS, COUNTER_RANGE, COUNTER_RATES, GAUSSIAN, check_kernel
from .voice import (
    BRR_BUFFER,
    ENV_ATTACK,
    ENV_DECAY,
    ENV_RELEASE,
    ENV_SUSTAIN,
    KEY_ON_DELAY,
    Voice,
)
from .words import clamp16, signed8, signed16

Step = Callable[["Chip"], None]


class MemoryLike(Protocol):
    def read8(self, address: int) -> int: ...

    def write8(self, address: int, value: int) -> None: ...


BRR_BLOCK_BYTES = 9

REG_PMON = 0x2D
REG_NON = 0x3D
REG_EON = 0x4D
REG_DIR = 0x5D
REG_KON = 0x4C
REG_KOFF = 0x5C
REG_ENDX = 0x7C

V_VOLL = 0x00
V_PITCHL = 0x02
V_PITCHH = 0x03
V_SRCN = 0x04
V_ADSR0 = 0x05
V_ADSR1 = 0x06
V_GAIN = 0x07
V_ENVX = 0x08
V_OUTX = 0x09

FLG_RESET = 0x80

UNSIGNED = 0xFFFFFFFF

BEND = 0x600


class Chip(Echo):
    __slots__ = (
        "gaussian",
        "memory",
        "model",
        "rendered",
    )

    def __init__(
        self,
        memory: MemoryLike,
        seed: int = UNSET_SEED,
        gaussian: Sequence[int] | None = None,
    ) -> None:
        self.memory = memory
        self.model = "s-dsp"
        self.gaussian = GAUSSIAN if gaussian is None else check_kernel(gaussian)
        self.rendered = []
        self._power_on(random.Random(seed))

    def reset(self) -> "Chip":
        self._define()
        return self

    def read(self, address: int) -> int:
        return self.registers[address & 0x7F]

    def write(self, address: int, value: int) -> None:
        address &= 0x7F
        value &= 0xFF
        self.registers[address] = value
        if address == REG_KON:
            self.new_kon = value
        elif address == REG_ENDX:
            self.registers[REG_ENDX] = 0
            self.endx_buffer = 0

    def _voice_register(self, voice: Voice, offset: int) -> int:
        return self.registers[voice.base + offset]

    def _read_counter(self, rate: int) -> bool:
        if rate == 0:
            return True
        return bool((self.counter + COUNTER_OFFSETS[rate]) % COUNTER_RATES[rate])

    def _run_counters(self) -> None:
        self.counter = (self.counter - 1) % COUNTER_RANGE

    def _interpolate(self, voice: Voice) -> int:
        position = voice.interpolation
        at = (position >> 12) + voice.buffer_position
        offset = position >> 4 & 0xFF
        forward = 255 - offset
        reverse = offset

        kernel = self.gaussian

        out = (kernel[forward] * voice.buffer[at]) >> 11
        out += (kernel[forward + 256] * voice.buffer[at + 1]) >> 11
        out += (kernel[reverse + 256] * voice.buffer[at + 2]) >> 11
        out = signed16(out)
        out += (kernel[reverse] * voice.buffer[at + 3]) >> 11
        return clamp16(out) & ~1

    def _decode_brr(self, voice: Voice) -> None:
        nybbles = self.t_brr_byte * 0x100 + self.memory.read8(
            (voice.brr_address + voice.brr_offset + 1) & 0xFFFF
        )
        header = self.t_brr_header

        at = voice.buffer_position
        voice.buffer_position += 4
        if voice.buffer_position >= BRR_BUFFER:
            voice.buffer_position = 0

        for _ in range(4):
            sample = signed16(nybbles) >> 12
            nybbles = (nybbles << 4) & 0xFFFFF

            shift = header >> 4
            if shift <= 12:
                sample = (sample << shift) >> 1
            else:
                sample &= ~0x7FF

            first = voice.buffer[at + BRR_BUFFER - 1]
            second = voice.buffer[at + BRR_BUFFER - 2] >> 1
            kind = header & 0x0C
            if kind >= 8:
                sample += first
                sample -= second
                if kind == 8:
                    sample += second >> 4
                    sample += (first * -3) >> 6
                else:
                    sample += (first * -13) >> 7
                    sample += (second * 3) >> 4
            elif kind:
                sample += first >> 1
                sample += (-first) >> 5

            sample = signed16(clamp16(sample) * 2)
            voice.buffer[at] = sample
            voice.buffer[at + BRR_BUFFER] = sample
            at += 1

    def _run_envelope(self, voice: Voice) -> None:
        envelope = voice.envelope
        if voice.envelope_mode == ENV_RELEASE:
            envelope -= 0x8
            voice.envelope = max(envelope, 0)
            return

        data = self._voice_register(voice, V_ADSR1)
        if self.t_adsr0 & 0x80:
            if voice.envelope_mode >= ENV_DECAY:
                envelope -= 1
                envelope -= envelope >> 8
                rate = data & 0x1F
                if voice.envelope_mode == ENV_DECAY:
                    rate = (self.t_adsr0 >> 3 & 0x0E) + 0x10
            else:
                rate = (self.t_adsr0 & 0x0F) * 2 + 1
                envelope += 0x20 if rate < 31 else 0x400
        else:
            data = self._voice_register(voice, V_GAIN)
            mode = data >> 5
            if mode < 4:
                envelope = data * 0x10
                rate = 31
            else:
                rate = data & 0x1F
                if mode == 4:
                    envelope -= 0x20
                elif mode < 6:
                    envelope -= 1
                    envelope -= envelope >> 8
                else:
                    envelope += 0x20
                    if mode > 6 and voice.hidden_envelope & UNSIGNED >= BEND:
                        envelope += 0x8 - 0x20

        if (envelope >> 8) == (data >> 5) and voice.envelope_mode == ENV_DECAY:
            voice.envelope_mode = ENV_SUSTAIN

        voice.hidden_envelope = envelope

        if not 0 <= envelope <= 0x7FF:
            envelope = 0 if envelope < 0 else 0x7FF
            if voice.envelope_mode == ENV_ATTACK:
                voice.envelope_mode = ENV_DECAY

        if not self._read_counter(rate):
            voice.envelope = envelope

    def voice_1(self, voice: Voice) -> None:
        self.t_dir_address = (self.t_dir * 0x100 + self.t_srcn * 4) & 0xFFFF
        self.t_srcn = self._voice_register(voice, V_SRCN)

    def voice_2(self, voice: Voice) -> None:
        entry = self.t_dir_address
        if not voice.key_on_delay:
            entry += 2
        self.t_brr_next_address = self.memory.read8(entry & 0xFFFF) | (
            self.memory.read8((entry + 1) & 0xFFFF) << 8
        )
        self.t_adsr0 = self._voice_register(voice, V_ADSR0)
        self.t_pitch = self._voice_register(voice, V_PITCHL)

    def voice_3a(self, voice: Voice) -> None:
        self.t_pitch += (self._voice_register(voice, V_PITCHH) & 0x3F) << 8

    def voice_3b(self, voice: Voice) -> None:
        self.t_brr_byte = self.memory.read8((voice.brr_address + voice.brr_offset) & 0xFFFF)
        self.t_brr_header = self.memory.read8(voice.brr_address & 0xFFFF)

    def voice_3c(self, voice: Voice) -> None:
        if self.t_pmon & voice.bit:
            self.t_pitch += ((self.t_output >> 5) * self.t_pitch) >> 10

        if voice.key_on_delay:
            if voice.key_on_delay == KEY_ON_DELAY:
                voice.brr_address = self.t_brr_next_address
                voice.brr_offset = 1
                voice.buffer_position = 0
                self.t_brr_header = 0
                self.kon_check = True

            voice.envelope = 0
            voice.hidden_envelope = 0
            voice.interpolation = 0
            voice.key_on_delay -= 1
            if voice.key_on_delay & 3:
                voice.interpolation = 0x4000
            self.t_pitch = 0

        output = self._interpolate(voice)
        if self.t_non & voice.bit:
            output = signed16(self.noise * 2)

        self.t_output = (output * voice.envelope) >> 11 & ~1
        voice.envelope_out = (voice.envelope >> 4) & 0xFF

        if self.registers[REG_FLG] & FLG_RESET or (self.t_brr_header & 3) == 1:
            voice.envelope_mode = ENV_RELEASE
            voice.envelope = 0

        if self.every_other_sample:
            if self.t_koff & voice.bit:
                voice.envelope_mode = ENV_RELEASE
            if self.kon & voice.bit:
                voice.key_on_delay = KEY_ON_DELAY
                voice.envelope_mode = ENV_ATTACK

        if not voice.key_on_delay:
            self._run_envelope(voice)

    def _voice_output(self, voice: Voice, channel: int) -> None:
        amplitude = (self.t_output * signed8(self._voice_register(voice, V_VOLL + channel))) >> 7
        self.main_out[channel] = clamp16(self.main_out[channel] + amplitude)
        if self.t_eon & voice.bit:
            self.echo_out[channel] = clamp16(self.echo_out[channel] + amplitude)

    def voice_4(self, voice: Voice) -> None:
        self.t_looped = 0
        if voice.interpolation >= 0x4000:
            self._decode_brr(voice)
            voice.brr_offset += 2
            if voice.brr_offset >= BRR_BLOCK_BYTES:
                voice.brr_address = (voice.brr_address + BRR_BLOCK_BYTES) & 0xFFFF
                if self.t_brr_header & 1:
                    voice.brr_address = self.t_brr_next_address
                    self.t_looped = voice.bit
                voice.brr_offset = 1

        voice.interpolation = (voice.interpolation & 0x3FFF) + self.t_pitch
        voice.interpolation = min(voice.interpolation, 0x7FFF)
        self._voice_output(voice, 0)

    def voice_5(self, voice: Voice) -> None:
        self._voice_output(voice, 1)
        endx = self.registers[REG_ENDX] | self.t_looped
        if voice.key_on_delay == KEY_ON_DELAY:
            endx &= ~voice.bit
        self.endx_buffer = endx & 0xFF

    def voice_6(self, voice: Voice) -> None:
        self.outx_buffer = (self.t_output >> 8) & 0xFF

    def voice_7(self, voice: Voice) -> None:
        self.registers[REG_ENDX] = self.endx_buffer
        self.envx_buffer = voice.envelope_out

    def voice_8(self, voice: Voice) -> None:
        self.registers[voice.base + V_OUTX] = self.outx_buffer

    def voice_9(self, voice: Voice) -> None:
        self.registers[voice.base + V_ENVX] = self.envx_buffer

    def voice_3(self, voice: Voice) -> None:
        self.voice_3a(voice)
        self.voice_3b(voice)
        self.voice_3c(voice)

    def misc_27(self) -> None:
        self.t_pmon = self.registers[REG_PMON] & 0xFE

    def misc_28(self) -> None:
        self.t_non = self.registers[REG_NON]
        self.t_eon = self.registers[REG_EON]
        self.t_dir = self.registers[REG_DIR]

    def misc_29(self) -> None:
        self.every_other_sample ^= 1
        if self.every_other_sample:
            self.new_kon &= ~self.kon & 0xFF

    def misc_30(self) -> None:
        if self.every_other_sample:
            self.kon = self.new_kon
            self.t_koff = self.registers[REG_KOFF]
        self._run_counters()
        if not self._read_counter(self.registers[REG_FLG] & 0x1F):
            self.noise = next_noise(self.noise)

    def clock(self) -> None:
        for step in SCHEDULE[self.phase]:
            step(self)
        self.phase = (self.phase + 1) & 31

    def run(self, clocks: int) -> None:
        for _ in range(clocks):
            self.clock()

    def render(self, samples: int) -> list[int]:
        self.rendered = []
        self.run(samples * 32)
        return list(self.rendered)


def _voice_step(name: str, index: int) -> "Step":
    def run(dsp: "Chip") -> None:
        getattr(dsp, name)(dsp.voices[index])

    return run


def _plain_step(name: str) -> "Step":
    def run(dsp: "Chip") -> None:
        getattr(dsp, name)()

    return run


PIPELINE: dict[int, list[str | tuple[str, int]]] = {
    0: [("voice_5", 0), ("voice_2", 1)],
    1: [("voice_6", 0), ("voice_3", 1)],
    2: [("voice_7", 0), ("voice_1", 3), ("voice_4", 1)],
    3: [("voice_8", 0), ("voice_5", 1), ("voice_2", 2)],
    4: [("voice_9", 0), ("voice_6", 1), ("voice_3", 2)],
    5: [("voice_7", 1), ("voice_1", 4), ("voice_4", 2)],
    6: [("voice_8", 1), ("voice_5", 2), ("voice_2", 3)],
    7: [("voice_9", 1), ("voice_6", 2), ("voice_3", 3)],
    8: [("voice_7", 2), ("voice_1", 5), ("voice_4", 3)],
    9: [("voice_8", 2), ("voice_5", 3), ("voice_2", 4)],
    10: [("voice_9", 2), ("voice_6", 3), ("voice_3", 4)],
    11: [("voice_7", 3), ("voice_1", 6), ("voice_4", 4)],
    12: [("voice_8", 3), ("voice_5", 4), ("voice_2", 5)],
    13: [("voice_9", 3), ("voice_6", 4), ("voice_3", 5)],
    14: [("voice_7", 4), ("voice_1", 7), ("voice_4", 5)],
    15: [("voice_8", 4), ("voice_5", 5), ("voice_2", 6)],
    16: [("voice_9", 4), ("voice_6", 5), ("voice_3", 6)],
    17: [("voice_1", 0), ("voice_7", 5), ("voice_4", 6)],
    18: [("voice_8", 5), ("voice_5", 6), ("voice_2", 7)],
    19: [("voice_9", 5), ("voice_6", 6), ("voice_3", 7)],
    20: [("voice_1", 1), ("voice_7", 6), ("voice_4", 7)],
    21: [("voice_8", 6), ("voice_5", 7), ("voice_2", 0)],
    22: [("voice_3a", 0), ("voice_9", 6), ("voice_6", 7), "echo_22"],
    23: [("voice_7", 7), "echo_23"],
    24: [("voice_8", 7), "echo_24"],
    25: [("voice_3b", 0), ("voice_9", 7), "echo_25"],
    26: ["echo_26"],
    27: ["misc_27", "echo_27"],
    28: ["misc_28", "echo_28"],
    29: ["misc_29", "echo_29"],
    30: ["misc_30", ("voice_3c", 0), "echo_30"],
    31: [("voice_4", 0), ("voice_1", 2)],
}

SCHEDULE = tuple(
    tuple(
        _plain_step(entry) if isinstance(entry, str) else _voice_step(*entry)
        for entry in PIPELINE[clock]
    )
    for clock in range(32)
)
