"""Docker 빌드 때 PaddleOCR 한국어 모델을 미리 받아 둔다 (v0.6 F1, D9).

화면에서 쓰는 것과 같은 설정(agent.ocr._model)으로 만들어서, 같은 모델 파일이 이미지에 들어간다.
첫 OCR 때 각자 PC에서 모델을 내려받다 실패하는 일을 막는다.
"""

from agent import ocr

if __name__ == "__main__":
    ocr._model()
    print("OCR 모델 준비됨")
