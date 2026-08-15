"""Tests for named LLM model profiles."""

import unittest

from pydantic import ValidationError
from react_agent.utils.settings import Settings


class LlmModelProfileTest(unittest.TestCase):
    def test_gpt_5_mini_profile_preserves_existing_defaults(self) -> None:
        settings = Settings(llm_model_profile="gpt_5_mini")

        self.assertEqual("gpt-5-mini-2025-08-07", settings.llm_model)
        self.assertEqual(1.0, settings.llm_temperature)
        self.assertEqual("minimal", settings.llm_reasoning_effort)
        self.assertIsNone(settings.llm_seed)

    def test_gpt_5_6_luna_profile_uses_its_supported_parameters(self) -> None:
        settings = Settings(llm_model_profile="gpt_5_6_luna")

        self.assertEqual("gpt-5.6-luna", settings.llm_model)
        self.assertEqual(0.0, settings.llm_temperature)
        self.assertEqual("none", settings.llm_reasoning_effort)
        self.assertEqual(42, settings.llm_seed)

    def test_unknown_profile_is_rejected_at_startup(self) -> None:
        with self.assertRaises(ValidationError):
            Settings(llm_model_profile="unknown")
