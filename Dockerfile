# Public demo of the Project Originality Portal (Render, Hugging Face Spaces or any Docker host).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.cache/huggingface \
    OMP_NUM_THREADS=1 \
    TOKENIZERS_PARALLELISM=false

WORKDIR /app

# CPU-only PyTorch keeps the image and memory use small.
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu
COPY portal/requirements.txt portal/requirements.txt
RUN pip install -r portal/requirements.txt gunicorn

COPY portal portal
COPY css css
COPY fonts fonts

# Download the model and embed the seed repository at build time, so the first request is fast.
RUN python -c "from sentence_transformers import SentenceTransformer as S; S('sentence-transformers/all-MiniLM-L6-v2')" \
 && python -c "import portal.wsgi" \
 && useradd -m -u 1000 appuser && chown -R appuser /app
USER appuser

EXPOSE 7860
CMD gunicorn --bind 0.0.0.0:${PORT:-7860} --workers 1 --threads 4 --timeout 120 portal.wsgi:app
