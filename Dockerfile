# JOBVIS 반 배포 이미지 (v0.6 F1, D9). 실행은 docker-compose.yml을 쓴다.
FROM python:3.12-slim

# paddle은 libgomp, opencv는 libGL·glib가 있어야 import된다 (v0.6 설계 시험 빌드)
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app
WORKDIR /app

COPY requirements.txt requirements-ocr.txt ./
RUN pip install -r requirements.txt -r requirements-ocr.txt

# OCR 한국어 모델을 이미지에 미리 넣는다. 첫 OCR 때 내려받지 않게 (F1)
COPY agent/__init__.py agent/ocr.py agent/
COPY scripts/warm_ocr.py scripts/
RUN python scripts/warm_ocr.py

COPY . .

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health')"
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501", \
    "--server.headless=true", "--browser.gatherUsageStats=false"]
