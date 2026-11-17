FROM python:3.11-slim AS embedding-model

WORKDIR /model-download

RUN python -m pip install --no-cache-dir "huggingface-hub>=0.20.0"
COPY backend/scripts/download_embedding_model.py .
RUN python download_embedding_model.py /model

FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    MODELO_EMB_REVISION=e8f8c211226b894fcb81acc59f3b34ba3efd5f42 \
    MODELO_EMB_PATH=/app/models/paraphrase-multilingual-MiniLM-L12-v2 \
    MODELO_EMB_BACKEND=onnx \
    MODELO_EMB_FILE_NAME=onnx/model_quint8_avx2.onnx

COPY backend/requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY --from=embedding-model /model /app/models/paraphrase-multilingual-MiniLM-L12-v2
COPY backend/ .

EXPOSE 8000

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]