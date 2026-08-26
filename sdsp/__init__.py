"""A model of the S-DSP, the wavetable half of the SNES audio unit.

    from sdsp import Chip, Memory

    dsp = Chip(Memory(), model="s-dsp")
    dsp.render(64)

Eight voices read compressed blocks out of the same sixty four kilobytes the
SPC700 uses, resample them through a gaussian kernel, shape them with envelopes,
and mix into an echo unit carrying an eight tap filter. It all runs on a thirty
two clock schedule in which the voices are pipelined rather than sequential.

Nothing starts clean. Audio RAM holds whatever it held.
"""

from typing import Any

from . import core as core
from . import models as models
from .core import (
    ENV_ATTACK,
    ENV_DECAY,
    ENV_RELEASE,
    ENV_SUSTAIN,
    PIPELINE,
    REGISTER_COUNT,
    VOICE_COUNT,
    Voice,
)
from .errors import UnknownModelError
from .memory import UNSET_SEED, Memory, SparseMemory, scramble
from .models import MODELS, Model
from .tables import COUNTER_OFFSETS, COUNTER_RATES, GAUSSIAN
from .version import VERSION

__version__ = VERSION


def Chip(model: str | None = None, memory: Any = None, **options: Any) -> "core.Chip":  # noqa: N802
    """A chip of the named model, sharing one interface across the family.

    The model comes first because it is the thing a caller always knows, and the
    memory is the thing they often do not care about yet. Omitting it hands back
    a part with a store of its own, holding what a store holds before anything
    wrote to it.

    The same shape as `Cpu(model, memory)` on the members that run a program, and
    named for what this is rather than for what it does. This part answers
    register accesses and steps a fixed schedule; it executes nothing, and
    calling the constructor `Cpu` would say it did.
    """
    built: core.Chip = models.lookup(model).build(
        SparseMemory() if memory is None else memory, **options
    )
    return built


__all__ = [
    "COUNTER_OFFSETS",
    "COUNTER_RATES",
    "ENV_ATTACK",
    "ENV_DECAY",
    "ENV_RELEASE",
    "ENV_SUSTAIN",
    "GAUSSIAN",
    "MODELS",
    "PIPELINE",
    "REGISTER_COUNT",
    "UNSET_SEED",
    "VOICE_COUNT",
    "Chip",
    "Memory",
    "Model",
    "SparseMemory",
    "UnknownModelError",
    "Voice",
    "__version__",
    "scramble",
]
