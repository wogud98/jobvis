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
