"""모든 테스트에 쓰는 준비."""

import pytest

from agent import runner


@pytest.fixture(autouse=True)
def running_mark(monkeypatch, tmp_path):
    """실행 중 표시 파일을 저장소 data/ 대신 임시 폴더에 둔다 (v0.7.7 F4)."""
    path = tmp_path / "data" / "running.txt"
    monkeypatch.setattr(runner, "RUNNING", path)
    return path
