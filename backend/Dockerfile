FROM python:3.12-slim

WORKDIR /app

# System dependencies for psycopg (libpq), bcrypt (gcc), and spaCy
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    g++ \
    ffmpeg \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only PyTorch first to avoid pulling the ~2 GB CUDA build
RUN pip install --no-cache-dir \
    torch --index-url https://download.pytorch.org/whl/cpu

# Install remaining Python dependencies (layer cached separately from torch)
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# Download the spaCy English model used for NER
RUN python -m spacy download en_core_web_sm

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
