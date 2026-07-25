"""``Renderable`` — turn a component into safe, factual text for a prompt.

A renderable produces **facts only** — field names, descriptions, allowed values,
blocker reasons, workflow structure. Never instructions, never business policy
(no ``metadata.prompts``), never a call to a model. The text is declarative
("Missing values: email"), deterministic, and safe to concatenate into any prompt.

Implement ``to_llm_extended()``; ``to_markdown()`` defaults to it (override for
real markdown). The set is intentionally small and open to extension.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class Renderable(ABC):
    """A component that can render itself to safe, factual, prompt-ready text."""

    @abstractmethod
    def to_llm_extended(self) -> str:
        """Factual text enriched with descriptions, ready to drop into a prompt."""

    def to_markdown(self) -> str:
        """The same facts as Markdown. Defaults to the plain extended text."""
        return self.to_llm_extended()
