import unittest

from knowledge import config, rag, retrieval


class RagFallbackTests(unittest.TestCase):
    def test_build_context_skips_rag_when_hf_backend_has_no_ollama_endpoint(self):
        original_backend = config.INFERENCE_BACKEND
        original_ollama_url = config.OLLAMA_BASE_URL
        original_collection = rag._collection
        original_disabled = rag._vectorstore_disabled
        original_reason = rag._vectorstore_disable_reason

        config.INFERENCE_BACKEND = "hf_space"
        config.OLLAMA_BASE_URL = config.DEFAULT_OLLAMA_BASE_URL
        rag._collection = None
        rag._vectorstore_disabled = False
        rag._vectorstore_disable_reason = ""

        try:
            context = retrieval.build_context("Dynamic Programming")
            disabled_after_call = rag._vectorstore_disabled
        finally:
            config.INFERENCE_BACKEND = original_backend
            config.OLLAMA_BASE_URL = original_ollama_url
            rag._collection = original_collection
            rag._vectorstore_disabled = original_disabled
            rag._vectorstore_disable_reason = original_reason

        self.assertEqual(context, "")
        self.assertTrue(disabled_after_call)


if __name__ == "__main__":
    unittest.main()
