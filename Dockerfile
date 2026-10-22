# JOBVIS 반 배포 이미지 (v0.6 F1, v0.6.2 D1). 실행은 docker-compose.yml 또는 start/compose.yml을 쓴다.
# 두 이미지: base(OCR 없음, 기본), ocr(OCR 포함). 그냥 빌드하면 맨 끝 ocr 단계라 v0.6과 같다.
#   docker build --target base -t jobvis:base .
# 코드가 바뀌어도 라이브러리·OCR 모델 층은 다시 만들지 않게 의존성 단계와 코드 단계를 나눈다.
FROM python:3.12-slim AS deps

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app
WORKDIR /app

COPY requirements.txt ./
RUN pip install -r requirements.txt


FROM deps AS deps-ocr

# paddle은 libgomp, opencv는 libGL·glib가 있어야 import된다 (v0.6 설계 시험 빌드)
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-ocr.txt ./
RUN pip install -r requirements-ocr.txt

# OCR 한국어 모델을 이미지에 미리 넣는다. 첫 OCR 때 내려받지 않게 (v0.6 F1)
COPY agent/__init__.py agent/ocr.py agent/
COPY scripts/warm_ocr.py scripts/
RUN python scripts/warm_ocr.py


FROM deps AS base
ENV JOBVIS_IMAGE=base
COPY . .
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health')"
# 예상 못 한 오류는 화면에 종류만 보인다. 자세한 내용은 docker compose logs app (v0.6.1 F12)
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501", \
    "--server.headless=true", "--browser.gatherUsageStats=false", "--client.showErrorDetails=type"]


FROM deps-ocr AS ocr
ENV JOBVIS_IMAGE=ocr
COPY . .
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health')"
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501", \
    "--server.headless=true", "--browser.gatherUsageStats=false", "--client.showErrorDetails=type"]
