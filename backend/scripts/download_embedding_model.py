#!/usr/bin/env python3
"""Download only the pinned INT8 ONNX artifact and files needed by SentenceTransformer."""
import sys
from pathlib import Path

from huggingface_hub import snapshot_download

MODEL_ID = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MODEL_REVISION = "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"
MODEL_FILES = [
    "1_Pooling/config.json",
    "config.json",
    "config_sentence_transformers.json",
    "modules.json",
    "onnx/model_quint8_avx2.onnx",
    "sentence_bert_config.json",
    "sentencepiece.bpe.model",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "unigram.json",
]


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Uso: download_embedding_model.py <diretorio-destino>")

    destination = Path(sys.argv[1])
    snapshot_download(
        repo_id=MODEL_ID,
        revision=MODEL_REVISION,
        local_dir=destination,
        allow_patterns=MODEL_FILES,
    )

    onnx_model = destination / "onnx" / "model_quint8_avx2.onnx"
    if not onnx_model.is_file():
        raise FileNotFoundError(f"Artefato ONNX INT8 não encontrado: {onnx_model}")

    print(
        f"Modelo {MODEL_ID}@{MODEL_REVISION} pronto: "
        f"{onnx_model.stat().st_size / (1024 * 1024):.1f} MiB"
    )


if __name__ == "__main__":
    main()
