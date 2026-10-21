from agent import ocr


def test_available_follows_installed_package(monkeypatch):
    monkeypatch.setattr(ocr.importlib.util, "find_spec", lambda name: None)
    assert ocr.available() is False

    monkeypatch.setattr(ocr.importlib.util, "find_spec", lambda name: object() if name == "paddleocr" else None)
    assert ocr.available() is True
