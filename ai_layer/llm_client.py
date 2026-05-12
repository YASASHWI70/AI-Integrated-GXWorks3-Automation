"""
ai_layer/llm_client.py — Claude API Client
===========================================

Wraps the Anthropic Claude API and provides a single `ask()` interface
used by the rest of the system.

Providers:
  • anthropic — Claude via the official Anthropic Python SDK
  • mock       — Hard-coded responses for offline development/testing

SYSTEM PROMPT:
    Instructs Claude to act as a PLC ladder logic expert and respond
    exclusively with valid JSON matching the LadderProgram schema.
"""

from __future__ import annotations
import json
import logging
from typing import Optional

import config

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# SYSTEM PROMPT
# ──────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """
You are an expert Mitsubishi PLC (Programmable Logic Controller) ladder logic engineer.
Your task is to convert user descriptions of automation requirements into structured
ladder logic programs for Mitsubishi GX Works3 software.

RULES:
1. Respond ONLY with a valid JSON object — no markdown, no explanation text.
2. The JSON must match this exact schema:
   {
     "name": "MAIN",
     "description": "...",
     "rungs": [
       {
         "id": 1,
         "comment": "...",
         "elements": [
           {
             "type": "contact_no|contact_nc|coil|coil_set|coil_reset|timer_on",
             "address": "X0",
             "label": "START_BUTTON",
             "position": {"row": 0, "col": 0},
             "preset": null
           }
         ]
       }
     ]
   }
3. Use Mitsubishi address conventions: X=inputs, Y=outputs, M=internal relays,
   T=timers, C=counters.
4. For a start-stop circuit: use X0=START (NO), X1=STOP (NC), Y0=MOTOR coil,
   add Y0 self-latch contact in parallel with START.
5. Timer preset values are in 100 ms units (e.g. 5 seconds = preset: 50).
6. Position col is 0-based horizontal position; row is 0 for main rung,
   1+ for parallel branches.
""".strip()


class LLMClient:
    """
    Claude API client.

    Usage:
        client = LLMClient()
        response = client.ask("Create a start-stop motor circuit for X0, X1, Y0")
    """

    def __init__(self, provider: Optional[str] = None) -> None:
        self.provider = (provider or config.LLM_PROVIDER).lower()
        if self.provider not in ("anthropic", "mock"):
            raise ValueError(
                f"Unknown LLM provider: '{self.provider}'. "
                "Valid options: 'anthropic', 'mock'."
            )
        logger.info("LLMClient initialised — provider=%s  model=%s",
                    self.provider,
                    config.ANTHROPIC_MODEL if self.provider == "anthropic" else "n/a")

    def ask(self, user_prompt: str) -> str:
        """
        Send a prompt and return the raw text response from Claude.

        Args:
            user_prompt: The user's request in natural language.

        Returns:
            The model's response (expected to be a JSON string).
        """
        logger.info("LLM (%s) → prompt length=%d chars", self.provider, len(user_prompt))

        if self.provider == "anthropic":
            return self._ask_claude(user_prompt)
        return self._mock_response(user_prompt)

    # ── Anthropic Claude ──────────────────────────────────────

    def _ask_claude(self, user_prompt: str) -> str:
        """Call the Anthropic Messages API using the configured Claude model."""
        if not config.ANTHROPIC_API_KEY:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY is not set. "
                "Add it to your .env file or set LLM_PROVIDER=mock for offline testing."
            )
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
            message = client.messages.create(
                model=config.ANTHROPIC_MODEL,
                max_tokens=4096,
                temperature=0.1,      # Low temperature = consistent JSON output
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            response_text = message.content[0].text
            logger.debug(
                "Claude response: tokens_in=%d tokens_out=%d",
                message.usage.input_tokens,
                message.usage.output_tokens,
            )
            return response_text
        except Exception as exc:
            logger.error("Anthropic API error: %s", exc)
            raise

    # ── Mock (development / testing) ──────────────────────────

    def _mock_response(self, user_prompt: str) -> str:
        """
        Return a pre-built JSON response without calling any real API.

        Detects keywords in the prompt and returns an appropriate template.
        Good for testing the full pipeline without API credentials.
        """
        prompt_lower = user_prompt.lower()

        if any(kw in prompt_lower for kw in ["start", "stop", "motor", "latch"]):
            return json.dumps({
                "name": "MAIN",
                "description": "Start-Stop Motor Control (mock generated)",
                "rungs": [
                    {
                        "id": 1,
                        "comment": "Motor Start-Stop circuit with self-latch",
                        "elements": [
                            {"type": "contact_no", "address": "X0",
                             "label": "START", "position": {"row": 0, "col": 0}},
                            {"type": "contact_no", "address": "Y0",
                             "label": "MOTOR_LATCH", "position": {"row": 1, "col": 0}},
                            {"type": "contact_nc", "address": "X1",
                             "label": "STOP", "position": {"row": 0, "col": 1}},
                            {"type": "coil", "address": "Y0",
                             "label": "MOTOR", "position": {"row": 0, "col": 2}},
                        ],
                    }
                ],
            })

        if any(kw in prompt_lower for kw in ["timer", "delay", "time"]):
            return json.dumps({
                "name": "MAIN",
                "description": "Timer circuit (mock generated)",
                "rungs": [
                    {
                        "id": 1,
                        "comment": "Input X0 triggers 5-second ON-delay timer T0",
                        "elements": [
                            {"type": "contact_no", "address": "X0",
                             "label": "TRIGGER", "position": {"row": 0, "col": 0}},
                            {"type": "timer_on", "address": "T0",
                             "label": "DELAY_5S", "preset": 50,
                             "position": {"row": 0, "col": 1}},
                        ],
                    },
                    {
                        "id": 2,
                        "comment": "Timer T0 contact drives output Y0",
                        "elements": [
                            {"type": "contact_no", "address": "T0",
                             "label": "TIMER_DONE", "position": {"row": 0, "col": 0}},
                            {"type": "coil", "address": "Y0",
                             "label": "OUTPUT", "position": {"row": 0, "col": 1}},
                        ],
                    },
                ],
            })

        # Generic fallback: simple contact-coil
        return json.dumps({
            "name": "MAIN",
            "description": "Simple contact-coil (mock generated)",
            "rungs": [
                {
                    "id": 1,
                    "comment": "Basic I/O mapping",
                    "elements": [
                        {"type": "contact_no", "address": "X0",
                         "label": "INPUT", "position": {"row": 0, "col": 0}},
                        {"type": "coil", "address": "Y0",
                         "label": "OUTPUT", "position": {"row": 0, "col": 1}},
                    ],
                }
            ],
        })
