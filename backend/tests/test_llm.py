from __future__ import annotations

import unittest
from unittest.mock import patch

import httpx

from backend.app import llm


def make_response(json_body):
    def _json():
        return json_body

    def _raise_for_status():
        return None

    response = unittest.mock.Mock()
    response.json = _json
    response.raise_for_status = _raise_for_status
    return response


def openai_body(text):
    return {"choices": [{"message": {"content": text}}]}


def anthropic_body(text):
    return {"content": [{"text": text}]}


class ProviderSelectionTests(unittest.TestCase):
    def test_unconfigured_returns_none(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertIsNone(llm.llm_provider())
            self.assertFalse(llm.llm_available())
            self.assertIsNone(llm.complete_text("hi"))
            self.assertIsNone(llm.complete_json("hi"))

    def test_only_openai_key_selects_openai(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=True):
            self.assertEqual(llm.llm_provider(), "openai")
            self.assertTrue(llm.llm_available())

    def test_only_anthropic_key_selects_anthropic(self):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant"}, clear=True):
            self.assertEqual(llm.llm_provider(), "anthropic")
            self.assertTrue(llm.llm_available())

    def test_openai_preferred_when_both_keys_present(self):
        env = {"OPENAI_API_KEY": "sk-test", "ANTHROPIC_API_KEY": "sk-ant"}
        with patch.dict("os.environ", env, clear=True):
            self.assertEqual(llm.llm_provider(), "openai")

    def test_override_selects_anthropic_when_both_keys_present(self):
        env = {
            "LLM_PROVIDER": "anthropic",
            "OPENAI_API_KEY": "sk-test",
            "ANTHROPIC_API_KEY": "sk-ant",
        }
        with patch.dict("os.environ", env, clear=True):
            self.assertEqual(llm.llm_provider(), "anthropic")

    def test_override_selects_openai_when_both_keys_present(self):
        env = {
            "LLM_PROVIDER": "openai",
            "OPENAI_API_KEY": "sk-test",
            "ANTHROPIC_API_KEY": "sk-ant",
        }
        with patch.dict("os.environ", env, clear=True):
            self.assertEqual(llm.llm_provider(), "openai")

    def test_override_without_matching_key_is_unconfigured(self):
        env = {"LLM_PROVIDER": "openai", "ANTHROPIC_API_KEY": "sk-ant"}
        with patch.dict("os.environ", env, clear=True):
            self.assertIsNone(llm.llm_provider())


class OpenAICompleteTextTests(unittest.TestCase):
    def test_returns_text_with_default_model_and_bearer_header(self):
        captured = {}

        def fake_post(url, *, headers, json, timeout):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return make_response(openai_body("hello world"))

        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=True):
            with patch.object(httpx, "post", side_effect=fake_post):
                result = llm.complete_text("say hi", system="be terse")

        self.assertEqual(result, "hello world")
        self.assertEqual(captured["url"], llm.OPENAI_CHAT_URL)
        self.assertEqual(captured["json"]["model"], "gpt-5.5")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer sk-test")
        roles = [message["role"] for message in captured["json"]["messages"]]
        self.assertEqual(roles, ["system", "user"])

    def test_respects_llm_model_override(self):
        env = {"OPENAI_API_KEY": "sk-test", "LLM_MODEL": "gpt-4o"}
        captured = {}

        def fake_post(url, *, headers, json, timeout):
            captured["json"] = json
            return make_response(openai_body("ok"))

        with patch.dict("os.environ", env, clear=True):
            with patch.object(httpx, "post", side_effect=fake_post):
                llm.complete_text("hi")

        self.assertEqual(captured["json"]["model"], "gpt-4o")

    def test_no_system_message_when_omitted(self):
        captured = {}

        def fake_post(url, *, headers, json, timeout):
            captured["json"] = json
            return make_response(openai_body("ok"))

        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=True):
            with patch.object(httpx, "post", side_effect=fake_post):
                llm.complete_text("hi")

        roles = [message["role"] for message in captured["json"]["messages"]]
        self.assertEqual(roles, ["user"])


class AnthropicCompleteTextTests(unittest.TestCase):
    def test_returns_text_with_default_model_and_headers(self):
        captured = {}

        def fake_post(url, *, headers, json, timeout):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return make_response(anthropic_body("anthropic reply"))

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant"}, clear=True):
            with patch.object(httpx, "post", side_effect=fake_post):
                result = llm.complete_text("say hi", system="be terse")

        self.assertEqual(result, "anthropic reply")
        self.assertEqual(captured["url"], llm.ANTHROPIC_MESSAGES_URL)
        self.assertEqual(captured["json"]["model"], "claude-sonnet-4-6")
        self.assertEqual(captured["headers"]["x-api-key"], "sk-ant")
        self.assertEqual(captured["headers"]["anthropic-version"], "2023-06-01")
        self.assertEqual(captured["json"]["system"], "be terse")


class CompleteJsonTests(unittest.TestCase):
    def test_parses_fenced_json_body(self):
        body = "```json\n{\"plan\": [1, 2], \"ok\": true}\n```"

        def fake_post(url, *, headers, json, timeout):
            return make_response(openai_body(body))

        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=True):
            with patch.object(httpx, "post", side_effect=fake_post):
                result = llm.complete_json("make a plan")

        self.assertEqual(result, {"plan": [1, 2], "ok": True})

    def test_parses_plain_json_body(self):
        def fake_post(url, *, headers, json, timeout):
            return make_response(anthropic_body('{"a": 1}'))

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant"}, clear=True):
            with patch.object(httpx, "post", side_effect=fake_post):
                result = llm.complete_json("make a plan")

        self.assertEqual(result, {"a": 1})

    def test_returns_none_when_body_not_json(self):
        def fake_post(url, *, headers, json, timeout):
            return make_response(openai_body("this is not json at all"))

        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=True):
            with patch.object(httpx, "post", side_effect=fake_post):
                result = llm.complete_json("make a plan")

        self.assertIsNone(result)

    def test_returns_none_when_json_is_not_object(self):
        def fake_post(url, *, headers, json, timeout):
            return make_response(openai_body("[1, 2, 3]"))

        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=True):
            with patch.object(httpx, "post", side_effect=fake_post):
                result = llm.complete_json("make a list")

        self.assertIsNone(result)

    def test_openai_json_mode_sets_response_format_and_keyword(self):
        captured = {}

        def fake_post(url, *, headers, json, timeout):
            captured["json"] = json
            return make_response(openai_body('{"ok": true}'))

        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=True):
            with patch.object(httpx, "post", side_effect=fake_post):
                llm.complete_json("make a plan", system="be terse")

        self.assertEqual(captured["json"]["response_format"], {"type": "json_object"})
        system_message = captured["json"]["messages"][0]
        self.assertEqual(system_message["role"], "system")
        self.assertIn("json", system_message["content"].lower())


class ErrorHandlingTests(unittest.TestCase):
    def test_openai_http_error_returns_none(self):
        def fake_post(*args, **kwargs):
            raise httpx.HTTPError("boom")

        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=True):
            with patch.object(httpx, "post", side_effect=fake_post):
                self.assertIsNone(llm.complete_text("hi"))
                self.assertIsNone(llm.complete_json("hi"))

    def test_anthropic_http_error_returns_none(self):
        def fake_post(*args, **kwargs):
            raise httpx.HTTPError("boom")

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant"}, clear=True):
            with patch.object(httpx, "post", side_effect=fake_post):
                self.assertIsNone(llm.complete_text("hi"))
                self.assertIsNone(llm.complete_json("hi"))

    def test_raise_for_status_error_returns_none(self):
        def fake_post(*args, **kwargs):
            response = unittest.mock.Mock()
            response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "401", request=None, response=None
            )
            return response

        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=True):
            with patch.object(httpx, "post", side_effect=fake_post):
                self.assertIsNone(llm.complete_text("hi"))

    def test_missing_fields_returns_none(self):
        def fake_post(*args, **kwargs):
            return make_response({"unexpected": "shape"})

        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=True):
            with patch.object(httpx, "post", side_effect=fake_post):
                self.assertIsNone(llm.complete_text("hi"))


if __name__ == "__main__":
    unittest.main()
