import asyncio
import copy
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

try:
    import httpx2 as httpx
except ImportError:
    import httpx

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    RateLimitError,
)

from app.services import ai_service


def _make_status_error(error_cls, status_code, message="provider error"):
    request = httpx.Request("POST", "https://example.test/v1/chat/completions")
    response = httpx.Response(status_code, request=request)
    return error_cls(message, response=response, body=None)


def _make_connection_error():
    request = httpx.Request("POST", "https://example.test/v1/chat/completions")
    return APIConnectionError(request=request)


def _make_timeout_error():
    request = httpx.Request("POST", "https://example.test/v1/chat/completions")
    return APITimeoutError(request=request)


def _completion(content, tokens=17):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(total_tokens=tokens),
    )


def _idea(title):
    return {
        "title": title,
        "problem_statement": "A real problem",
        "proposed_solution": "A practical solution",
        "innovation": "A novel angle",
        "real_world_applications": "Used by students",
        "target_audience": "Engineering students",
        "tech_stack": ["Python"],
        "requirements": ["A laptop"],
        "implementation_roadmap": ["Phase 1"],
        "future_enhancements": ["More features"],
        "expected_outcomes": "A working prototype",
    }


def _evaluation():
    result = {field: 75 for field in ai_service._EVALUATION_SCORE_FIELDS}
    result.update({field: ["value"] for field in ai_service._EVALUATION_LIST_FIELDS})
    return result


def _tech_stack():
    return {
        "recommendations": [
            {
                "category": "Frontend",
                "technologies": ["React"],
                "reason": "Easy to learn",
                "beginner_alternative": "HTML and CSS",
            }
        ],
        "summary": "A suitable beginner stack.",
    }


def _roadmap():
    return {
        "title": "Project Roadmap",
        "description": "A complete roadmap",
        "total_weeks": 4,
        "technologies": ["Python"],
        "learning_resources": ["Official documentation"],
        "tasks": [
            {
                "title": "Set up the project",
                "description": "Create the repository",
                "week_number": 1,
                "order_index": 0,
                "phase": "Planning",
                "estimated_hours": 5,
                "technologies": ["Python"],
                "is_milestone": False,
            }
        ],
    }


class AIServiceF4Tests(unittest.TestCase):
    def setUp(self):
        self.settings = SimpleNamespace(
            openai_api_key="test-key",
            ai_base_url="https://api.openai.com/v1",
            ai_model="test-model",
        )
        settings_patch = patch.object(ai_service, "settings", self.settings)
        settings_patch.start()
        self.addCleanup(settings_patch.stop)

        sleep_patch = patch.object(ai_service.asyncio, "sleep", new=AsyncMock())
        self.sleep_mock = sleep_patch.start()
        self.addCleanup(sleep_patch.stop)

    def test_get_client_disables_sdk_retries_and_sets_timeout(self):
        with patch.object(ai_service, "AsyncOpenAI") as client_cls:
            ai_service._get_client()

        client_cls.assert_called_once_with(
            api_key="test-key",
            base_url="https://api.openai.com/v1",
            max_retries=0,
            timeout=60.0,
        )
        self.assertEqual(ai_service._MAX_ATTEMPTS, 3)

    def test_incomplete_json_is_never_recovered(self):
        malformed_payloads = [
            '[{"title": "One"}, {"title": "Two"',
            '[{"title": "One"})',
            '[{"title": "One", "value": "unterminated}]',
            '"scalar"',
            "null",
        ]
        for payload in malformed_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(ai_service._RetryableResponseError):
                    ai_service._safe_json_loads(payload, "generate_ideas")
                self.assertIsNone(ai_service._attempt_json_recovery(payload))

        complete = '[{"title": "One", "note": "with { braces }"}]'
        self.assertEqual(
            ai_service._safe_json_loads(complete, "generate_ideas"),
            [{"title": "One", "note": "with { braces }"}],
        )
        fenced = '```json\n[{"title": "Fenced"}]\n```'
        self.assertEqual(
            ai_service._safe_json_loads(fenced, "generate_ideas"),
            [{"title": "Fenced"}],
        )

    def test_generate_ideas_retries_malformed_json(self):
        good = _idea("Good Idea")
        responses = [
            ('[{"title": "Broken"', 5),
            (json.dumps([good]), 12),
        ]

        with patch.object(
            ai_service, "_chat_completion", new=AsyncMock(side_effect=responses)
        ) as completion:
            result = asyncio.run(ai_service.generate_ideas({"count": 1}))

        self.assertEqual(result, [good])
        self.assertEqual(completion.await_count, 2)
        self.assertEqual(self.sleep_mock.await_count, 1)

    def test_generate_ideas_retries_validation_failure_and_unwraps(self):
        good = _idea("Wrapped Idea")
        responses = [
            ('[{"unexpected": true}]', 5),
            (json.dumps({"ideas": [good]}), 9),
        ]

        with patch.object(
            ai_service, "_chat_completion", new=AsyncMock(side_effect=responses)
        ) as completion:
            result = asyncio.run(ai_service.generate_ideas({"count": 1}))

        self.assertEqual(result, [good])
        self.assertEqual(completion.await_count, 2)

    def test_evaluate_idea_retries_validation_failure(self):
        good = _evaluation()
        invalid = dict(good, overall_score=150)
        responses = [
            (json.dumps(invalid), 5),
            (json.dumps(good), 21),
        ]

        with patch.object(
            ai_service, "_chat_completion", new=AsyncMock(side_effect=responses)
        ) as completion:
            result = asyncio.run(ai_service.evaluate_idea("Title", "Description"))

        self.assertEqual(result, good)
        self.assertEqual(completion.await_count, 2)

    def test_recommend_tech_stack_retries_malformed_json(self):
        good = _tech_stack()
        responses = [
            ("```json\n" + json.dumps(good)[:-10] + "\n", 3),
            (json.dumps(good), 18),
        ]

        with patch.object(
            ai_service, "_chat_completion", new=AsyncMock(side_effect=responses)
        ) as completion:
            result = asyncio.run(ai_service.recommend_tech_stack("A project"))

        self.assertEqual(result, good)
        self.assertEqual(completion.await_count, 2)

    def test_generate_roadmap_retries_validation_failure(self):
        good = _roadmap()
        responses = [
            (json.dumps({"tasks": "not a list"}), 4),
            (json.dumps(good), 30),
        ]

        with patch.object(
            ai_service, "_chat_completion", new=AsyncMock(side_effect=responses)
        ) as completion:
            result = asyncio.run(ai_service.generate_roadmap({"title": "Project"}))

        self.assertEqual(result, good)
        self.assertEqual(completion.await_count, 2)

    def test_mentor_chat_returns_tuple_and_retries_empty_reply(self):
        responses = [("", 3), (" Let's start. ", 22)]

        with patch.object(
            ai_service, "_chat_completion", new=AsyncMock(side_effect=responses)
        ) as completion:
            result = asyncio.run(ai_service.mentor_chat("Hello", []))

        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        self.assertEqual(result, (" Let's start. ", 22))
        self.assertEqual(completion.await_count, 2)

    def test_chat_completion_makes_exactly_one_provider_call(self):
        create = AsyncMock(
            side_effect=[_make_status_error(RateLimitError, 429), _completion("ok", 33)]
        )
        client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create))
        )

        with patch.object(ai_service, "_get_client", return_value=client):
            with self.assertRaises(RateLimitError):
                asyncio.run(
                    ai_service._chat_completion([{"role": "user", "content": "hi"}])
                )

        self.assertEqual(create.await_count, 1)
        self.assertEqual(self.sleep_mock.await_count, 0)

    def test_public_call_retries_transient_error_from_completion_wrapper(self):
        rate_limit = _make_status_error(RateLimitError, 429)
        completion = AsyncMock(
            side_effect=[rate_limit, (json.dumps([_idea("Recovered")]), 7)]
        )

        with patch.object(ai_service, "_chat_completion", new=completion):
            result = asyncio.run(ai_service.generate_ideas({"count": 1}))

        self.assertEqual(result[0]["title"], "Recovered")
        self.assertEqual(completion.await_count, 2)

    def test_public_call_retries_only_approved_statuses(self):
        good = _idea("Recovered")
        for status in (429, 500, 502, 503):
            with self.subTest(status=status):
                self.sleep_mock.reset_mock()
                error_cls = RateLimitError if status == 429 else APIStatusError
                error = _make_status_error(error_cls, status)
                completion = AsyncMock(
                    side_effect=[error, (json.dumps([good]), 7)]
                )

                with patch.object(ai_service, "_chat_completion", new=completion):
                    result = asyncio.run(ai_service.generate_ideas({"count": 1}))

                self.assertEqual(result, [good])
                self.assertEqual(completion.await_count, 2)
                self.assertEqual(self.sleep_mock.await_count, 1)

    def test_permanent_errors_are_not_retried(self):
        errors = [
            _make_status_error(AuthenticationError, 401),
            _make_connection_error(),
            _make_timeout_error(),
            _make_status_error(APIStatusError, 408),
            _make_status_error(APIStatusError, 504),
        ]
        for error in errors:
            with self.subTest(error_type=type(error).__name__):
                self.sleep_mock.reset_mock()
                completion = AsyncMock(side_effect=error)

                with patch.object(ai_service, "_chat_completion", new=completion):
                    with self.assertRaises(ValueError):
                        asyncio.run(ai_service.generate_ideas({"count": 1}))

                self.assertEqual(completion.await_count, 1)
                self.assertEqual(self.sleep_mock.await_count, 0)

    def test_public_call_makes_at_most_three_provider_calls_for_mixed_failures(self):
        side_effect = [
            _make_status_error(RateLimitError, 429),
            ("[", 1),
            (json.dumps({"unexpected": True}), 2),
            (json.dumps([_idea("Too Late")]), 3),
        ]
        completion = AsyncMock(side_effect=side_effect)

        with patch.object(ai_service, "_chat_completion", new=completion):
            with self.assertRaises(ValueError):
                asyncio.run(ai_service.generate_ideas({"count": 1}))

        self.assertEqual(completion.await_count, 3)
        self.assertEqual(self.sleep_mock.await_count, 2)

    def test_public_call_exhaustion_for_each_public_function(self):
        cases = [
            (lambda: ai_service.generate_ideas({"count": 1}), "["),
            (lambda: ai_service.evaluate_idea("Title", "Description"), "["),
            (lambda: ai_service.recommend_tech_stack("A project"), "["),
            (lambda: ai_service.generate_roadmap({"title": "Project"}), "["),
            (lambda: ai_service.mentor_chat("Hello", []), ""),
        ]
        for call, invalid_response in cases:
            with self.subTest(call=call):
                self.sleep_mock.reset_mock()
                completion = AsyncMock(return_value=(invalid_response, 1))

                with patch.object(ai_service, "_chat_completion", new=completion):
                    with self.assertRaises(ValueError):
                        asyncio.run(call())

                self.assertEqual(completion.await_count, ai_service._MAX_ATTEMPTS)
                self.assertEqual(
                    self.sleep_mock.await_count, ai_service._MAX_ATTEMPTS - 1
                )

    def test_missing_configuration_is_not_retried(self):
        self.settings.openai_api_key = ""
        calls = [
            lambda: ai_service.generate_ideas({}),
            lambda: ai_service.evaluate_idea("Title", "Description"),
            lambda: ai_service.recommend_tech_stack("A project"),
            lambda: ai_service.generate_roadmap({"title": "Project"}),
            lambda: ai_service.mentor_chat("Hello", []),
        ]

        with patch.object(ai_service, "_get_client") as get_client:
            for call in calls:
                with self.subTest(call=call):
                    with self.assertRaises(ValueError):
                        asyncio.run(call())

        get_client.assert_not_called()
        self.assertEqual(self.sleep_mock.await_count, 0)

    def test_idea_requires_every_field_with_expected_type(self):
        good = _idea("Good Idea")
        self.assertEqual(ai_service._validate_ideas([good]), [good])

        for field in ai_service._IDEA_TEXT_FIELDS:
            missing = dict(good)
            missing.pop(field)
            with self.subTest(field=field, case="missing"):
                with self.assertRaises(ai_service._RetryableResponseError):
                    ai_service._validate_ideas([missing])
            for value in (None, 123, "   "):
                bad = dict(good, **{field: value})
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ai_service._RetryableResponseError):
                        ai_service._validate_ideas([bad])

        for field in ai_service._IDEA_LIST_FIELDS:
            missing = dict(good)
            missing.pop(field)
            with self.subTest(field=field, case="missing"):
                with self.assertRaises(ai_service._RetryableResponseError):
                    ai_service._validate_ideas([missing])
            for value in (None, "not a list", [1]):
                bad = dict(good, **{field: value})
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ai_service._RetryableResponseError):
                        ai_service._validate_ideas([bad])

    def test_evaluation_requires_every_field_with_expected_type(self):
        good = _evaluation()
        self.assertEqual(ai_service._validate_evaluation(good), good)

        for field in ai_service._EVALUATION_SCORE_FIELDS:
            missing = dict(good)
            missing.pop(field)
            with self.subTest(field=field, case="missing"):
                with self.assertRaises(ai_service._RetryableResponseError):
                    ai_service._validate_evaluation(missing)
            for value in (None, True, -1, 101, "75"):
                bad = dict(good, **{field: value})
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ai_service._RetryableResponseError):
                        ai_service._validate_evaluation(bad)

        for field in ai_service._EVALUATION_LIST_FIELDS:
            missing = dict(good)
            missing.pop(field)
            with self.subTest(field=field, case="missing"):
                with self.assertRaises(ai_service._RetryableResponseError):
                    ai_service._validate_evaluation(missing)
            for value in (None, "not a list", [1]):
                bad = dict(good, **{field: value})
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ai_service._RetryableResponseError):
                        ai_service._validate_evaluation(bad)

    def test_tech_stack_requires_fields_but_allows_optional_beginner_alternative(self):
        good = _tech_stack()
        self.assertEqual(ai_service._validate_tech_stack(good), good)

        top_level_bad_values = {
            "summary": (None, 123, []),
            "recommendations": (None, "not a list", 123),
        }
        for field, values in top_level_bad_values.items():
            for value in values:
                bad = copy.deepcopy(good)
                bad[field] = value
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ai_service._RetryableResponseError):
                        ai_service._validate_tech_stack(bad)

        for field in ("category", "technologies", "reason"):
            for value in (None, 123, [1]):
                bad = copy.deepcopy(good)
                bad["recommendations"][0][field] = value
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ai_service._RetryableResponseError):
                        ai_service._validate_tech_stack(bad)

        bad_optional = copy.deepcopy(good)
        bad_optional["recommendations"][0]["beginner_alternative"] = 123
        with self.assertRaises(ai_service._RetryableResponseError):
            ai_service._validate_tech_stack(bad_optional)

        absent_optional = copy.deepcopy(good)
        absent_optional["recommendations"][0].pop("beginner_alternative")
        self.assertEqual(
            ai_service._validate_tech_stack(absent_optional), absent_optional
        )

        null_optional = copy.deepcopy(good)
        null_optional["recommendations"][0]["beginner_alternative"] = None
        self.assertEqual(ai_service._validate_tech_stack(null_optional), null_optional)

        with_extra = copy.deepcopy(good)
        with_extra["disclaimer"] = "ignored"
        self.assertEqual(ai_service._validate_tech_stack(with_extra), with_extra)

    def test_roadmap_requires_fields_and_task_fields(self):
        good = _roadmap()
        self.assertEqual(ai_service._validate_roadmap(good), good)

        top_level_bad_values = {
            "title": 1,
            "description": None,
            "total_weeks": 0,
            "technologies": "Python",
            "learning_resources": None,
            "tasks": "not a list",
        }
        for field, value in top_level_bad_values.items():
            missing = copy.deepcopy(good)
            missing.pop(field)
            with self.subTest(field=field, case="missing"):
                with self.assertRaises(ai_service._RetryableResponseError):
                    ai_service._validate_roadmap(missing)

            bad = copy.deepcopy(good)
            bad[field] = value
            with self.subTest(field=field, value=value):
                with self.assertRaises(ai_service._RetryableResponseError):
                    ai_service._validate_roadmap(bad)

        task_bad_values = {
            "title": 1,
            "description": None,
            "week_number": good["total_weeks"] + 1,
            "order_index": -1,
            "phase": 1,
            "estimated_hours": 0,
            "technologies": "Python",
            "is_milestone": "yes",
        }
        for field, value in task_bad_values.items():
            missing = copy.deepcopy(good)
            missing["tasks"][0].pop(field)
            with self.subTest(field=field, case="missing"):
                with self.assertRaises(ai_service._RetryableResponseError):
                    ai_service._validate_roadmap(missing)

            bad = copy.deepcopy(good)
            bad["tasks"][0][field] = value
            with self.subTest(field=field, value=value):
                with self.assertRaises(ai_service._RetryableResponseError):
                    ai_service._validate_roadmap(bad)

    def test_mentor_reply_and_token_count_validation(self):
        self.assertEqual(ai_service._validate_mentor_reply(" Let's start. "), " Let's start. ")
        for value in ("", "   ", None, 123):
            with self.subTest(value=value):
                with self.assertRaises(ai_service._RetryableResponseError):
                    ai_service._validate_mentor_reply(value)

        self.assertEqual(ai_service._validate_token_count(0), 0)
        for value in (-1, True, "5", None):
            with self.subTest(value=value):
                with self.assertRaises(ai_service._RetryableResponseError):
                    ai_service._validate_token_count(value)

    def test_no_sensitive_logging(self):
        raw_secret = "RAW-RESPONSE-SECRET"
        provider_secret = "PROVIDER-EXCEPTION-SECRET"
        responses = [
            ('[{"title": "' + raw_secret, 1),
            _make_status_error(RateLimitError, 429, provider_secret),
            (json.dumps([_idea("Done")]), 3),
        ]

        with self.assertLogs(ai_service.logger, level="WARNING") as captured:
            with patch.object(
                ai_service, "_chat_completion", new=AsyncMock(side_effect=responses)
            ):
                result = asyncio.run(ai_service.generate_ideas({"count": 1}))

        self.assertEqual(result[0]["title"], "Done")
        joined = "\n".join(captured.output)
        self.assertNotIn(raw_secret, joined)
        self.assertNotIn(provider_secret, joined)
        self.assertIn("generate_ideas", joined)
        self.assertIn("status=429", joined)


if __name__ == "__main__":
    unittest.main()
