"""LLM client wrapper for the generation step."""

from __future__ import annotations

from typing import Any

from groq import Groq

from finbot.config.settings import get_settings
from finbot.utils.logger import get_logger

logger = get_logger(__name__)


class LLMClient:
    """
    Wrapper around the Groq API.

    Provides a simple ``generate()`` method used by the RAG chain,
    guardrails, and evaluation modules.
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> None:
        settings = get_settings()
        self._model = model or settings.llm_model
        self._client = Groq(api_key=api_key or settings.groq_api_key)
        self._temperature = temperature
        self._max_tokens = max_tokens
        logger.info("LLMClient initialised with model='%s'", self._model)

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        history: list[dict[str, str]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """
        Generate a completion for the given prompt.

        Parameters
        ----------
        prompt : str
            The user/query prompt.
        system_prompt : str, optional
            System-level instructions.
        history : list[dict], optional
            Prior conversation turns as ``[{"role": "user", "content": "..."}, ...]``.
            Inserted between the system prompt and the current user prompt.
        temperature : float, optional
            Override default temperature.
        max_tokens : int, optional
            Override default max tokens.

        Returns
        -------
        str
            The LLM's response text.
        """
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # Inject conversation history
        if history:
            messages.extend(history)

        messages.append({"role": "user", "content": prompt})

        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=temperature or self._temperature,
            max_tokens=max_tokens or self._max_tokens,
        )

        content = response.choices[0].message.content or ""
        logger.debug(
            "LLM generated %d chars (model=%s, tokens_used=%s)",
            len(content),
            self._model,
            getattr(response.usage, "total_tokens", "unknown"),
        )
        return content

    def generate_with_context(
        self,
        query: str,
        contexts: list[str],
        system_prompt: str | None = None,
    ) -> str:
        """
        Generate a RAG response using retrieved contexts.

        Formats contexts into the prompt and delegates to ``generate()``.
        """
        context_block = "\n\n---\n\n".join(f"[Context {i+1}]:\n{ctx}" for i, ctx in enumerate(contexts))
        prompt = f"""Answer the following question using ONLY the provided contexts. If the contexts don't contain enough information, say so clearly.

CONTEXTS:
{context_block}

QUESTION: {query}

Provide a comprehensive answer with references to the source contexts. Always cite which context(s) support each claim."""

        return self.generate(prompt, system_prompt=system_prompt)
