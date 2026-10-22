"""공고 이미지 글자 읽기. PaddleOCR(선택 설치, requirements-ocr.txt)를 PC에서 돌린다 (F12, F13)."""

import functools
import importlib.util
import io
import os

MIN_SIDE = 300  # 가로나 세로가 이보다 작으면 장식으로 보고 건너뛴다 (F12)
MAX_IMAGES = 10  # 공고당 최대 장수 (F12)
INSTALL_HINT = "이미지 OCR을 쓰려면 `pip install -r requirements-ocr.txt`"


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


def read(image: bytes) -> str:
    import numpy as np
    from PIL import Image

    with Image.open(io.BytesIO(image)) as picture:
        pixels = np.array(picture.convert("RGB"))[:, :, ::-1]  # PaddleOCR은 BGR 순서를 받는다
    lines = []
    for result in _model().predict(pixels):
        lines.extend(text for text in result["rec_texts"] if text.strip())
    return "\n".join(lines)
