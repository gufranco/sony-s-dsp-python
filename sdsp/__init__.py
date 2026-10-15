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
from .errors import NotAKernel, UnknownModelError
from .memory import UNSET_SEED, Memory, SparseMemory, scramble
from .models import MODELS, Model
from .tables import COUNTER_OFFSETS, COUNTER_RATES, GAUSSIAN, check_kernel
from .version import VERSION

__version__ = VERSION


def Chip(model: str | None = None, memory: Any = None, **options: Any) -> "core.Chip":  # noqa: N802
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
    "NotAKernel",
    "SparseMemory",
    "UnknownModelError",
    "Voice",
    "__version__",
    "check_kernel",
    "scramble",
]
