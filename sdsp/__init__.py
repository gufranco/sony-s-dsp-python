"""A model of the S-DSP, the wavetable half of the SNES audio unit.

    from sdsp import Sdsp, Memory

    dsp = Sdsp(Memory(), model="s-dsp")
    dsp.render(64)

Eight voices read compressed blocks out of the same sixty four kilobytes the
SPC700 uses, resample them through a gaussian kernel, shape them with envelopes,
and mix into an echo unit carrying an eight tap filter. It all runs on a thirty
two clock schedule in which the voices are pipelined rather than sequential.

Nothing starts clean. Audio RAM holds whatever it held.
"""

from typing import Any

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
from .core import Dsp as Core
from .memory import UNSET_SEED, Memory, SparseMemory, scramble
from .models import MODELS, UnknownModelError, describe
from .tables import COUNTER_OFFSETS, COUNTER_RATES, GAUSSIAN
from .version import VERSION

__version__ = VERSION

DEFAULT_MODEL = "s-dsp"


def Sdsp(memory: Any, model: str = DEFAULT_MODEL, **options: Any) -> Any:  # noqa: N802
    """A chip of the named model, sharing one interface across the family."""
    return describe(model).build(memory, **options)


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
    "Core",
    "Memory",
    "Sdsp",
    "SparseMemory",
    "UnknownModelError",
    "Voice",
    "__version__",
    "describe",
    "scramble",
]
