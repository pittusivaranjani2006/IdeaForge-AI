import asyncio
import copy
import inspect
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

try:
    import httpx2 as httpx
except ImportError:
    import httpx

from openai import RateLimitError

from app.services import ai_service


def _make_status_error(status_code, message="provider error"):
    request = httpx.Request("POST", "https://example.test/v1/chat/completions")
    response = httpx.Response(status_code, request=request)
    return RateLimitError(message, response=response, body=None)


def _candidate(idea_id, domain="AI/ML"):
    return {
        "id": idea_id,
        "title": f"Idea {idea_id}",
        "domain": domain,
        "difficulty": "Medium",
        "short_description": f"Short description {idea_id}",
    }


def _candidates(count=3):
    domains = ["AI/ML", "IoT", "Web Development", "FinTech", "Cybersecurity"]
    return {
        idea_id: _candidate(idea_id, domains[(idea_id - 1) % len(domains)])
        for idea_id in range(1, count + 1)
    }


def _recommendation_response(candidates, ids, rationale="Strong matches"):
    by_id = {candidate["id"]: candidate for candidate in candidates}
    ideas = []
    for idea_id in ids:
        idea = copy.deepcopy(by_id[idea_id])
        idea["ignored"] = "model-generated"
        ideas.append(idea)
    return json.dumps({"ideas": ideas, "rationale": rationale})


class AIServiceF1Tests(unittest.TestCase):
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

    def test_public_signature_matches_route_contract(self):
        parameters = inspect.signature(ai_service.generate_recommendations).parameters
        self.assertEqual(
            list(parameters),
            ["user_interests", "saved_domains", "viewed_titles", "all_ideas", "limit"],
        )
        self.assertEqual(parameters["limit"].default, 6)

    def test_generate_recommendations_returns_canonical_candidates(self):
        candidates = _candidates(3)
        content = _recommendation_response(list(candidates.values()), [3, 1], "Best fits")
        completion = AsyncMock(return_value=(content, 11))

        with patch.object(ai_service, "_chat_completion", new=completion):
            result = asyncio.run(
                ai_service.generate_recommendations(
                    user_interests=["Python"],
                    saved_domains=["AI/ML"],
                    viewed_titles=["Resume Bot"],
                    all_ideas=list(candidates.values()),
                    limit=3,
                )
            )

        self.assertEqual(
            result,
            {
                "ideas": [candidates[3], candidates[1]],
                "rationale": "Best fits",
            },
        )
        for idea in result["ideas"]:
            self.assertEqual(set(idea), set(ai_service._RECOMMENDATION_FIELDS))
        self.assertEqual(completion.await_count, 1)

    def test_generate_recommendations_prompt_includes_user_context(self):
        candidates = _candidates(2)
        content = _recommendation_response(list(candidates.values()), [1])
        completion = AsyncMock(return_value=(content, 9))

        with patch.object(ai_service, "_chat_completion", new=completion):
            asyncio.run(
                ai_service.generate_recommendations(
                    user_interests=["Python"],
                    saved_domains=["IoT"],
                    viewed_titles=["Campus Parking Bot"],
                    all_ideas=list(candidates.values()),
                    limit=2,
                )
            )

        prompt = completion.await_args.args[0][1]["content"]
        self.assertIn('["Python"]', prompt)
        self.assertIn('["IoT"]', prompt)
        self.assertIn('["Campus Parking Bot"]', prompt)
        self.assertIn(candidates[1]["title"], prompt)
        self.assertIn(candidates[1]["short_description"], prompt)

    def test_generate_recommendations_handles_empty_personal_signals(self):
        candidates = _candidates(2)
        content = _recommendation_response(list(candidates.values()), [2])
        completion = AsyncMock(return_value=(content, 9))

        with patch.object(ai_service, "_chat_completion", new=completion):
            asyncio.run(
                ai_service.generate_recommendations(
                    user_interests=[],
                    saved_domains=[],
                    viewed_titles=[],
                    all_ideas=list(candidates.values()),
                    limit=2,
                )
            )

        prompt = completion.await_args.args[0][1]["content"]
        self.assertEqual(prompt.count(ai_service._EMPTY_CONTEXT), 3)
        self.assertNotIn("None provided", json.dumps(list(candidates.values())))

    def test_generate_recommendations_empty_candidates_skip_provider(self):
        completion = AsyncMock()

        with patch.object(ai_service, "_chat_completion", new=completion):
            result = asyncio.run(
                ai_service.generate_recommendations([], [], [], [], 4)
            )

        self.assertEqual(
            result,
            {
                "ideas": [],
                "rationale": "No published ideas are available right now.",
            },
        )
        completion.assert_not_called()
        self.assertEqual(self.sleep_mock.await_count, 0)

    def test_generate_recommendations_limit_normalization(self):
        candidates = _candidates(4)
        content = _recommendation_response(list(candidates.values()), [1, 2, 3, 4])
        completion = AsyncMock(return_value=(content, 15))

        with patch.object(ai_service, "_chat_completion", new=completion):
            result = asyncio.run(
                ai_service.generate_recommendations([], [], [], list(candidates.values()), 10)
            )

        self.assertEqual(len(result["ideas"]), 4)
        self.assertIn("up to 4", completion.await_args.args[0][1]["content"])

    def test_generate_recommendations_zero_limit_skips_provider(self):
        candidates = _candidates(2)
        completion = AsyncMock()

        with patch.object(ai_service, "_chat_completion", new=completion):
            result = asyncio.run(
                ai_service.generate_recommendations([], [], [], list(candidates.values()), 0)
            )

        self.assertEqual(result["ideas"], [])
        self.assertEqual(result["rationale"], "No recommendations were requested.")
        completion.assert_not_called()

    def test_generate_recommendations_validates_response_strictly(self):
        candidates = _candidates(3)
        candidate_map = {candidate["id"]: candidate for candidate in candidates.values()}
        candidate_list = list(candidates.values())
        validate = lambda parsed: ai_service._validate_recommendations(
            parsed, candidate_map, 2
        )
        valid = {"ideas": candidate_list[:2], "rationale": "Strong matches"}
        self.assertEqual(validate(valid), valid)

        missing_field_cases = []
        for field in ai_service._RECOMMENDATION_FIELDS:
            bad_idea = copy.deepcopy(candidate_list[0])
            bad_idea.pop(field)
            missing_field_cases.append({"ideas": [bad_idea], "rationale": "Why"})

        bad_ideas = [
            "not an object",
            {"id": True, "title": candidates[1]["title"], "domain": candidates[1]["domain"], "difficulty": candidates[1]["difficulty"], "short_description": candidates[1]["short_description"]},
            {"id": "1", "title": candidates[1]["title"], "domain": candidates[1]["domain"], "difficulty": candidates[1]["difficulty"], "short_description": candidates[1]["short_description"]},
            {"id": 999, "title": candidates[1]["title"], "domain": candidates[1]["domain"], "difficulty": candidates[1]["difficulty"], "short_description": candidates[1]["short_description"]},
            dict(candidate_list[0], title=123),
            dict(candidate_list[0], domain=None),
            dict(candidate_list[0], difficulty="Hard"),
            dict(candidate_list[0], short_description=[]),
        ]

        bad_responses = [
            {"rationale": "Why"},
            {"ideas": candidate_list[:2], "rationale": ""},
            {"ideas": candidate_list[:2], "rationale": None},
            {"ideas": candidate_list[:2], "rationale": 123},
            {"ideas": None, "rationale": "Why"},
            {"ideas": "not a list", "rationale": "Why"},
            {"ideas": [], "rationale": "Why"},
            {"ideas": candidate_list[:3], "rationale": "Why"},
            {"ideas": [candidate_list[0], copy.deepcopy(candidate_list[0])], "rationale": "Why"},
        ]
        bad_responses.extend({"ideas": [idea], "rationale": "Why"} for idea in bad_ideas)
        bad_responses.extend(missing_field_cases)

        for index, bad_response in enumerate(bad_responses):
            with self.subTest(index=index):
                with self.assertRaises(ai_service._RetryableResponseError):
                    validate(bad_response)

    def test_generate_recommendations_rejects_incomplete_json(self):
        incomplete = '[{"id": 1, "title": "Idea 1'
        with self.assertRaises(ai_service._RetryableResponseError):
            ai_service._safe_json_loads(incomplete, "generate_recommendations")
        self.assertIsNone(ai_service._attempt_json_recovery(incomplete))

    def test_generate_recommendations_provider_failure_uses_fallback(self):
        candidates = _candidates(3)
        error = _make_status_error(429)
        completion = AsyncMock(side_effect=[error, error, error])

        with patch.object(ai_service, "_chat_completion", new=completion):
            result = asyncio.run(
                ai_service.generate_recommendations([], [], [], list(candidates.values()), 2)
            )

        self.assertEqual(result["ideas"], [candidates[1], candidates[2]])
        self.assertIn("unavailable", result["rationale"])
        self.assertEqual(completion.await_count, ai_service._MAX_ATTEMPTS)
        self.assertEqual(self.sleep_mock.await_count, ai_service._MAX_ATTEMPTS - 1)

    def test_generate_recommendations_missing_api_key_uses_fallback(self):
        self.settings.openai_api_key = ""
        candidates = _candidates(2)
        completion = AsyncMock()

        with patch.object(ai_service, "_chat_completion", new=completion):
            result = asyncio.run(
                ai_service.generate_recommendations([], [], [], list(candidates.values()), 2)
            )

        self.assertEqual(result["ideas"], list(candidates.values()))
        self.assertIn("unavailable", result["rationale"])
        completion.assert_not_called()
        self.assertEqual(self.sleep_mock.await_count, 0)

    def test_generate_recommendations_no_sensitive_logging(self):
        candidates = _candidates(2)
        raw_secret = "RAW-RESPONSE-SECRET"
        provider_secret = "PROVIDER-EXCEPTION-SECRET"
        responses = [
            ('[{"id": ' + raw_secret, 1),
            _make_status_error(429, provider_secret),
            (_recommendation_response(list(candidates.values()), [1]), 3),
        ]

        with self.assertLogs(ai_service.logger, level="WARNING") as captured:
            with patch.object(
                ai_service, "_chat_completion", new=AsyncMock(side_effect=responses)
            ):
                result = asyncio.run(
                    ai_service.generate_recommendations(
                        [], [], [], list(candidates.values()), 2
                    )
                )

        self.assertEqual(result["ideas"], [candidates[1]])
        joined = "\n".join(captured.output)
        self.assertNotIn(raw_secret, joined)
        self.assertNotIn(provider_secret, joined)
        self.assertIn("generate_recommendations", joined)
        self.assertIn("status=429", joined)


if __name__ == "__main__":
    unittest.main()
