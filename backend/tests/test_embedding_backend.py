import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app import llm


class EmbeddingBackendTests(unittest.TestCase):
    def test_torch_backend_keeps_model_id_and_does_not_set_onnx_options(self):
        with (
            patch.object(llm, "MODELO_EMB", "sentence-transformers/model"),
            patch.object(llm, "MODELO_EMB_REVISION", ""),
            patch.object(llm, "MODELO_EMB_PATH", ""),
            patch.object(llm, "MODELO_EMB_BACKEND", "torch"),
            patch.object(llm, "SentenceTransformer") as sentence_transformer,
        ):
            encoder = llm.carregar_encoder()

        self.assertIs(encoder, sentence_transformer.return_value)
        sentence_transformer.assert_called_once_with(
            "sentence-transformers/model",
            backend="torch",
            model_kwargs=None,
            revision=None,
        )

    def test_onnx_backend_uses_cpu_quantized_file_and_single_thread_options(self):
        options = SimpleNamespace()
        session_options = Mock(return_value=options)
        onnxruntime = SimpleNamespace(SessionOptions=session_options)

        with (
            patch.object(llm, "MODELO_EMB", "sentence-transformers/model"),
            patch.object(
                llm,
                "MODELO_EMB_REVISION",
                "e8f8c211226b894fcb81acc59f3b34ba3efd5f42",
            ),
            patch.object(llm, "MODELO_EMB_PATH", "/app/model"),
            patch.object(llm, "MODELO_EMB_BACKEND", "onnx"),
            patch.object(llm, "MODELO_EMB_FILE_NAME", "onnx/model_quint8_avx2.onnx"),
            patch.object(llm, "SentenceTransformer") as sentence_transformer,
            patch.dict("sys.modules", {"onnxruntime": onnxruntime}),
        ):
            encoder = llm.carregar_encoder()

        self.assertIs(encoder, sentence_transformer.return_value)
        self.assertEqual(options.intra_op_num_threads, 1)
        self.assertEqual(options.inter_op_num_threads, 1)
        self.assertFalse(options.enable_cpu_mem_arena)
        call = sentence_transformer.call_args
        self.assertEqual(call.args[0], "/app/model")
        kwargs = call.kwargs
        self.assertIsNone(kwargs["revision"])
        self.assertEqual(kwargs["backend"], "onnx")
        self.assertEqual(
            kwargs["model_kwargs"]["file_name"],
            "onnx/model_quint8_avx2.onnx",
        )
        self.assertEqual(
            kwargs["model_kwargs"]["provider"],
            "CPUExecutionProvider",
        )
        self.assertFalse(kwargs["model_kwargs"]["export"])

    def test_embedding_hash_changes_when_backend_changes(self):
        with patch.object(llm, "MODELO_EMB_BACKEND", "torch"):
            torch_hash = llm.hash_indice_embeddings("base")
        with patch.object(llm, "MODELO_EMB_BACKEND", "onnx"):
            onnx_hash = llm.hash_indice_embeddings("base")

        self.assertNotEqual(torch_hash, onnx_hash)


if __name__ == "__main__":
    unittest.main()
