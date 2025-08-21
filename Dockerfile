# 构建阶段
FROM python:3.12-slim-bookworm AS builder
WORKDIR /app
RUN echo "" > /etc/apt/sources.list.d/debian.sources && \
    echo "deb http://deb.debian.org/debian bookworm main" > /etc/apt/sources.list && \
    echo "deb http://deb.debian.org/debian-security bookworm-security main" >> /etc/apt/sources.list && \
    export http_proxy="" https_proxy="" no_proxy="localhost,127.0.0.1" && \
    apt-get update && apt-get install -y \
    tesseract-ocr tesseract-ocr-eng tesseract-ocr-chi-sim \
    libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

# 运行阶段
FROM python:3.12-slim-bookworm
WORKDIR /app
RUN echo "" > /etc/apt/sources.list.d/debian.sources && \
    echo "deb http://deb.debian.org/debian bookworm main" > /etc/apt/sources.list && \
    echo "deb http://deb.debian.org/debian-security bookworm-security main" >> /etc/apt/sources.list && \
    apt-get update && apt-get install -y \
    tesseract-ocr tesseract-ocr-eng tesseract-ocr-chi-sim \
    libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*
COPY --from=builder /app/.venv /app/.venv
COPY models/EasyOCR /root/.EasyOCR
RUN chmod -R 755 /root/.EasyOCR
COPY app/ app/
COPY templates/ templates/
COPY static/ static/
ENV TESSERACT_CMD=/usr/bin/tesseract
ENV EASYOCR_MODULE_PATH=/root/.EasyOCR
EXPOSE 8000
CMD ["/app/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
