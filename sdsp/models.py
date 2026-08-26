"""Which parts this package covers, and what each one is.

The S-DSP is one part with one behaviour. Sony built it into the S-SMP beside
the SPC700 and never sold it separately, so there is no family of revisions to
model. The catalogue exists for the same reason it exists in the sibling
repositories: a hardware difference discovered later should mean adding an entry
rather than restructuring the package around it.
"""

from collections.abc import Callable, Sequence
from typing import Any, override

from sdsp.errors import UnknownModelError


class Model:
    """One part: what it is, what it carries, and how to build it."""

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
    """The model of that name, however it happens to be written.

    Naming nothing is refused rather than filled in. A default would be the one
    implicit thing in the call that builds a part, and it is worst where it looks
    most harmless: a caller who learns to leave the model out against a member
    covering one part writes the same call against a member covering sixteen.
    The refusal names every model there is, so somebody who did not know what to
    pass learns it here rather than from the source.

    Not exported from the package. What a caller wants is the part, and the part
    carries its own model; handing back a description of a part nobody built
    reads like a test fixture rather than an interface.
    """
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
