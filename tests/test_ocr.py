import io

from agent import ocr


def test_available_follows_installed_package(monkeypatch):
    monkeypatch.setattr(ocr.importlib.util, "find_spec", lambda name: None)
    assert ocr.available() is False

    monkeypatch.setattr(ocr.importlib.util, "find_spec", lambda name: object() if name == "paddleocr" else None)
    assert ocr.available() is True


def test_off_setting_hides_installed_ocr(monkeypatch):
    monkeypatch.setattr(ocr.importlib.util, "find_spec", lambda name: object())

    monkeypatch.setenv("JOBVIS_OCR", "off")
    assert ocr.available() is False  # Mac 등 OCR이 안 도는 PC의 대비책 (v0.6 F10)

    monkeypatch.setenv("JOBVIS_OCR", "on")
    assert ocr.available() is True


# ---- 긴 이미지 나눠 읽기 (v0.7.7 F1–F3) ----


class FakeModel:
    """PaddleOCR 흉내. 받은 조각 크기를 적고, 조각마다 정해 둔 줄을 돌려준다."""

    def __init__(self, parts):
        self.parts, self.shapes = list(parts), []

    def predict(self, pixels):
        self.shapes.append(pixels.shape)
        return [{"rec_texts": self.parts.pop(0) if self.parts else []}]


def _png(width, height):
    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(out, format="PNG")
    return out.getvalue()


def test_pieces_short_image_is_one_piece():
    assert ocr.pieces(ocr.PIECE) == [(0, ocr.PIECE)]
    assert ocr.pieces(500) == [(0, 500)]


def test_pieces_cover_long_image_with_overlap():
    spans = ocr.pieces(6744)
    assert spans[0][0] == 0 and spans[-1][1] == 6744
    assert all(bottom - top <= ocr.PIECE for top, bottom in spans)
    assert all(nxt[0] == prev[1] - ocr.OVERLAP for prev, nxt in zip(spans, spans[1:], strict=False))


def test_join_lines_drops_lines_read_twice_at_overlap():
    parts = [["자격요건", "Python 3년"], ["Python 3년", "우대사항"], ["복지"]]
    assert ocr.join_lines(parts) == ["자격요건", "Python 3년", "우대사항", "복지"]
    assert ocr.join_lines([[], ["a"], []]) == ["a"]
    assert ocr.join_lines([]) == []


def test_read_long_image_reads_pieces_not_whole(monkeypatch):
    model = FakeModel([["첫 줄", "경계"], ["경계", "둘째"], ["셋째"], ["넷째"], ["다섯째"]])
    monkeypatch.setattr(ocr, "_model", lambda: model)

    text = ocr.read(_png(950, 6744))  # 2026-11-05 실제로 앱을 죽인 이미지 크기

    assert len(model.shapes) == len(ocr.pieces(6744)) > 1
    assert all(height <= ocr.PIECE and width == 950 for height, width, _ in model.shapes)
    assert text.splitlines()[:3] == ["첫 줄", "경계", "둘째"]


def test_read_wide_image_is_shrunk_first(monkeypatch):
    model = FakeModel([["글자"]])
    monkeypatch.setattr(ocr, "_model", lambda: model)

    assert ocr.read(_png(ocr.MAX_WIDTH * 2, 1000)) == "글자"
    assert model.shapes == [(500, ocr.MAX_WIDTH, 3)]  # 비율대로 줄여 한 조각


def test_read_small_image_unchanged(monkeypatch):
    model = FakeModel([["  ", "한 줄"]])
    monkeypatch.setattr(ocr, "_model", lambda: model)

    assert ocr.read(_png(800, 600)) == "한 줄"  # 빈 줄은 빼는 기존 규칙 그대로
    assert model.shapes == [(600, 800, 3)]


def test_read_empty_result(monkeypatch):
    monkeypatch.setattr(ocr, "_model", lambda: FakeModel([]))
    assert ocr.read(_png(800, 3000)) == ""
