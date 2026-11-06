"""공고 이미지 글자 읽기. PaddleOCR(선택 설치, requirements-ocr.txt)를 PC에서 돌린다 (F12, F13).

세로로 아주 긴 이미지를 한 번에 읽으면 메모리를 7GB 넘게 써서 앱이 강제 종료됐다(v0.7.7).
넓은 이미지는 줄이고, 긴 이미지는 조각으로 잘라 차례로 읽는다 (v0.7.7 F1–F3).
"""

import functools
import importlib.util
import io
import os

MIN_SIDE = 300  # 가로나 세로가 이보다 작으면 장식으로 보고 건너뛴다 (F12)
MAX_IMAGES = 10  # 공고당 최대 장수 (F12)
MAX_WIDTH = 1280  # 이보다 넓으면 비율대로 줄인다 (v0.7.7 F2)
PIECE = 1600  # 세로로 이보다 길면 이 높이씩 잘라 읽는다 (v0.7.7 F1)
OVERLAP = 80  # 자른 경계에 걸친 줄이 끊기지 않게 조각끼리 겹치는 높이 (v0.7.7 F1)
OCR_EXTRA = "약 560MB"  # OCR 이미지를 고르면 더 받는 크기 (v0.6.2 N2, 03-test.md 실측)


def install_hint() -> str:
    """OCR이 없을 때 할 일. 시작 파일로 받은 기본 이미지면 OCR 포함 이미지를 고르라고 한다 (v0.6.2 F7, D5)."""
    if os.getenv("JOBVIS_IMAGE", "").strip().lower() == "base":
        return f"OCR을 쓰려면 `JOBVIS 시작.bat`을 다시 열고 OCR 포함을 고르세요({OCR_EXTRA} 더 받음)"
    return "이미지 OCR을 쓰려면 `pip install -r requirements-ocr.txt`"


INSTALL_HINT = install_hint()


def available() -> bool:
    if os.getenv("JOBVIS_OCR", "").strip().lower() == "off":  # 꺼 두면 설치 안 된 것과 같다 (v0.6 F10)
        return False
    return importlib.util.find_spec("paddleocr") is not None


def size(image: bytes) -> tuple[int, int]:
    from PIL import Image  # PaddleOCR이 함께 설치한다

    with Image.open(io.BytesIO(image)) as picture:
        return picture.size


@functools.cache
def _model():
    from paddleocr import PaddleOCR

    # 윈도우에서 가속 옵션(mkldnn) 오류가 나서 끈다. 모델은 처음 부를 때 한 번만 만든다.
    return PaddleOCR(
        lang="korean",
        enable_mkldnn=False,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
    )


def pieces(height: int) -> list[tuple[int, int]]:
    """세로 height 이미지를 자를 (위, 아래) 구간들. 조각끼리 OVERLAP만큼 겹친다 (v0.7.7 F1)."""
    if height <= PIECE:
        return [(0, height)]
    spans, top = [], 0
    while True:
        bottom = min(top + PIECE, height)
        spans.append((top, bottom))
        if bottom == height:
            return spans
        top = bottom - OVERLAP


def join_lines(parts: list[list[str]]) -> list[str]:
    """조각별 글자 줄을 잇는다. 겹친 곳에서 두 번 읽힌 줄(앞 조각 끝 세 줄에 있는 첫 줄들)은 한 번만 (v0.7.7 F3)."""
    lines: list[str] = []
    for part in parts:
        tail = lines[-3:]
        start = 0
        while start < len(part) and part[start] in tail:
            start += 1
        lines.extend(part[start:])
    return lines


def read(image: bytes) -> str:
    import numpy as np
    from PIL import Image

    with Image.open(io.BytesIO(image)) as picture:
        picture = picture.convert("RGB")
        if picture.width > MAX_WIDTH:  # 넓은 이미지는 비율대로 줄인다 (F2)
            height = max(1, round(picture.height * MAX_WIDTH / picture.width))
            picture = picture.resize((MAX_WIDTH, height))
        crops = [picture.crop((0, top, picture.width, bottom)) for top, bottom in pieces(picture.height)]
    parts = []
    for crop in crops:  # 한 조각씩 읽어 메모리를 조각 크기만큼만 쓴다 (F1)
        pixels = np.array(crop)[:, :, ::-1]  # PaddleOCR은 BGR 순서를 받는다
        lines = []
        for result in _model().predict(pixels):
            lines.extend(text for text in result["rec_texts"] if text.strip())
        parts.append(lines)
    return "\n".join(join_lines(parts))
