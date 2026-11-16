FROM python:3.11-slim

WORKDIR /app

# Cria pasta de cache gravável para o Hugging Face baixar o modelo MiniLM
ENV HF_HOME=/tmp/huggingface

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# O Hugging Face Spaces usa a porta 7860 por padrão
EXPOSE 7860

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]