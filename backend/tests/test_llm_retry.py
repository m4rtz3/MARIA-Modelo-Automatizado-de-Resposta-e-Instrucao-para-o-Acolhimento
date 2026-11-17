import unittest
from unittest.mock import Mock, patch

from google.api_core.exceptions import NotFound, ResourceExhausted, ServiceUnavailable

from app import llm


class LlmRetryTests(unittest.TestCase):
    def test_quota_and_not_found_errors_are_not_retried(self):
        for error in (
            NotFound("model not found"),
            ResourceExhausted("daily quota exceeded"),
        ):
            with self.subTest(error=type(error).__name__):
                chamada = Mock(side_effect=error)
                with patch("app.llm.time.sleep") as dormir:
                    with self.assertRaises(type(error)):
                        llm._chama_com_retry(chamada)

                chamada.assert_called_once_with()
                dormir.assert_not_called()

    def test_transient_service_error_is_retried(self):
        chamada = Mock(side_effect=[ServiceUnavailable("temporarily unavailable"), "ok"])

        with patch("app.llm.time.sleep") as dormir:
            resultado = llm._chama_com_retry(chamada)

        self.assertEqual(resultado, "ok")
        self.assertEqual(chamada.call_count, 2)
        dormir.assert_called_once_with(2)

    def test_stream_disables_sdk_retries_for_quota_errors(self):
        model = Mock()
        with (
            patch.object(llm, "_cria_modelo", return_value=model),
            patch.object(llm, "_chama_com_retry", side_effect=lambda chamada: chamada()),
        ):
            llm.llm_stream("pergunta")

        request_options = model.generate_content.call_args.kwargs["request_options"]
        self.assertIsNone(request_options.retry)
        self.assertEqual(request_options.timeout, llm.TIMEOUT_REQUEST_S)


if __name__ == "__main__":
    unittest.main()
