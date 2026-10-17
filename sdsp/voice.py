import random

from .memory import UNSET_SEED

BRR_BUFFER = 12
BRR_GROUP = 4
BRR_FIRST_PAIR = 1
BRR_PAIRS = 4

ENV_RELEASE = 0
ENV_ATTACK = 1
ENV_DECAY = 2
ENV_SUSTAIN = 3
ENV_MODES = 4

KEY_ON_DELAY = 5

BYTE = 0x100
WORD = 0x10000
INTERPOLATION_SPAN = 0x8000
ENVELOPE_SPAN = 0x800


def signed_draw(scrambled: random.Random, span: int) -> int:
    return scrambled.randrange(span) - span // 2


class Voice:
    __slots__ = (
        "base",
        "bit",
        "brr_address",
        "brr_offset",
        "buffer",
        "buffer_position",
        "envelope",
        "envelope_mode",
        "envelope_out",
        "hidden_envelope",
        "index",
        "interpolation",
        "key_on_delay",
    )

    def __init__(self, index: int, seed: int = UNSET_SEED) -> None:
        self.index = index
        self.bit = 1 << index
        self.base = index * 0x10
        scrambled = random.Random(seed)
        decoded = [signed_draw(scrambled, WORD) for _ in range(BRR_BUFFER)]
        self.buffer = decoded + decoded
        self.buffer_position = scrambled.randrange(BRR_BUFFER // BRR_GROUP) * BRR_GROUP
        self.interpolation = scrambled.randrange(INTERPOLATION_SPAN)
        self.brr_address = scrambled.randrange(WORD)
        self.brr_offset = BRR_FIRST_PAIR + scrambled.randrange(BRR_PAIRS) * 2
        self.key_on_delay = scrambled.randrange(KEY_ON_DELAY + 1)
        self.envelope_mode = scrambled.randrange(ENV_MODES)
        self.envelope = scrambled.randrange(ENVELOPE_SPAN)
        self.hidden_envelope = scrambled.randrange(ENVELOPE_SPAN)
        self.envelope_out = scrambled.randrange(BYTE)

    def reset(self) -> None:
        self.buffer = [0] * (BRR_BUFFER * 2)
        self.buffer_position = 0
        self.interpolation = 0
        self.brr_address = 0
        self.brr_offset = BRR_FIRST_PAIR
        self.key_on_delay = 0
        self.envelope_mode = ENV_RELEASE
        self.envelope = 0
        self.hidden_envelope = 0
        self.envelope_out = 0
