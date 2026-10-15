from collections.abc import Callable, Sequence
from typing import Any, override

from sdsp.errors import UnknownModelError


class Model:
    __slots__ = (
        "aliases",
        "core",
        "name",
        "registers",
        "summary",
        "voices",
    )

    def __init__(
        self,
        name: str,
        summary: str,
        voices: int,
        registers: int,
        core: Callable[..., Any],
        aliases: Sequence[str] = (),
    ) -> None:
        self.name = name
        self.summary = summary
        self.voices = voices
        self.registers = registers
        self.core = core
        self.aliases = tuple(aliases)

    def build(self, memory: Any, **options: Any) -> Any:
        return self.core(self, memory, **options)

    @override
    def __repr__(self) -> str:
        return f"<Model {self.name}, {self.voices} voices>"


def _build_sdsp(model: "Model", memory: Any, **options: Any) -> Any:
    from .core import Chip

    dsp = Chip(memory, **options)
    dsp.model = model.name
    return dsp


_CATALOGUE = (
    Model(
        name="s-dsp",
        summary=(
            "The Sony S-DSP, the wavetable half of the SNES audio unit. Eight voices "
            "reading compressed blocks out of the same sixty four kilobytes the SPC700 "
            "uses, resampled through a gaussian kernel, shaped by envelopes, and mixed "
            "with an echo unit carrying an eight tap filter."
        ),
        voices=8,
        registers=128,
        core=_build_sdsp,
        aliases=("sdsp", "sonysdsp", "dsp", "snesdsp"),
    ),
)

MODELS = {model.name: model for model in _CATALOGUE}

_BY_ALIAS = {}
for _model in _CATALOGUE:
    _BY_ALIAS[_model.name] = _model
    for _alias in _model.aliases:
        _BY_ALIAS[_alias] = _model


def _normalise(name: str) -> str:
    return str(name).strip().lower().replace("-", "").replace("_", "")


def lookup(name: str | None) -> Model:
    if name is None:
        raise UnknownModelError(
            "no model was named, and this package will not choose one for you."
            f" Name one of: {', '.join(sorted(MODELS))}"
        )
    found = _BY_ALIAS.get(_normalise(name))
    if found is None:
        raise UnknownModelError(
            f"{name} is not a model this package covers; it has {', '.join(sorted(MODELS))}"
        )
    return found
