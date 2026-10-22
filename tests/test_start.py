"""시작 파일 묶음(start/)과 이미지 나누기 (v0.6.2). .bat은 Windows에서만 돌아 여기서는 내용만 본다 (N1)."""

from pathlib import Path

import yaml

from agent import ocr

ROOT = Path(__file__).parent.parent
START = ROOT / "start"
BATS = [START / "JOBVIS 시작.bat", START / "JOBVIS 끄기.bat"]


def compose(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_start_compose_pulls_image_without_source():
    """묶음은 소스 없이 GHCR 이미지를 받는다. 태그는 jobvis.env의 JOBVIS_TAG (F2, D2, D6)."""
    app = compose(START / "compose.yml")["services"]["app"]

    assert "build" not in app
    assert app["image"] == "ghcr.io/wogud98/jobvis:${JOBVIS_TAG:-latest}"
    assert app["ports"] == ["127.0.0.1:8501:8501"]  # 이 PC에서만 (v0.6 D10)


def test_start_compose_shares_data_with_repo_compose():
    """두 compose 모두 name: jobvis라 폴더가 달라도 같은 볼륨을 쓴다. DB·환경 설정도 같다 (D7)."""
    start, repo = compose(START / "compose.yml"), compose(ROOT / "docker-compose.yml")

    assert start["name"] == repo["name"] == "jobvis"
    assert start["volumes"] == repo["volumes"]
    assert start["services"]["db"] == repo["services"]["db"]
    assert start["services"]["app"]["volumes"] == repo["services"]["app"]["volumes"]
    shared = {key: value for key, value in repo["services"]["app"]["environment"].items() if key != "JOBVIS_OCR"}
    assert start["services"]["app"]["environment"] == shared


def test_repo_compose_still_builds_ocr_image():
    """저장소에서 직접 빌드하면 v0.6처럼 OCR 포함 (F10, D1)."""
    assert compose(ROOT / "docker-compose.yml")["services"]["app"]["build"] == {"context": ".", "target": "ocr"}


def test_no_key_in_compose_files():
    for path in (START / "compose.yml", ROOT / "docker-compose.yml"):
        environment = compose(path)["services"]["app"]["environment"]
        assert not any("KEY" in name or "SECRET" in name for name in environment)  # v0.6.1 F13


def test_bat_files_use_crlf_and_utf8():
    """LF면 cmd가 줄을 잘못 읽는다. 한국어는 chcp 65001로 (D11)."""
    for path in BATS:
        data = path.read_bytes()
        assert not data.startswith(b"\xef\xbb\xbf")  # BOM이 있으면 첫 줄 @echo off가 깨짐
        assert data.count(b"\n") == data.count(b"\r\n") > 0
        assert data.decode("utf-8").splitlines()[1] == "chcp 65001 >nul"


def test_start_bat_steps_and_failures():
    """Docker 확인 → OCR 묻기 → 포트 확인 → 받기 → 켜기 → 브라우저. 실패하면 창을 닫지 않는다 (F1, F2, F4, F5, F6)."""
    text = BATS[0].read_text(encoding="utf-8")

    steps = ["docker info", ":ask_ocr", ":8501", "pull", "up -d --wait", 'start "" http://localhost:8501']
    positions = [text.index(step) for step in steps]
    assert positions == sorted(positions)
    assert "Docker Desktop을 켠 뒤 다시 실행하세요" in text
    assert "JOBVIS_TAG=ocr" in text and "JOBVIS_TAG=latest" in text
    assert "choice /c YN /t 5 /d N" in text  # 다시 열면 5초 동안 바꿀 기회 (F6)
    assert text.count("goto fail") == 5  # compose.yml 없음, Docker, 포트, 받기, 켜기
    assert "pause" in text.split("\n:fail\n", 1)[1]
    assert f"({ocr.OCR_EXTRA} 더)" in text  # 묻는 문구의 크기가 화면 안내와 같음 (N2)


def test_bat_files_use_only_compose_file_next_to_them():
    """compose.yml이 없으면 Docker가 위 폴더의 직접 빌드용 compose를 읽어 받기가 실패했음 (v0.6.2 F19)."""
    for path in BATS:
        text = path.read_text(encoding="utf-8")
        calls = [line for line in text.splitlines() if line.strip().startswith("docker compose")]
        assert calls and all(line.strip().startswith("docker compose -f compose.yml ") for line in calls)
    start = BATS[0].read_text(encoding="utf-8")
    assert start.index('if not exist "compose.yml"') < start.index("docker info")


def test_bat_files_never_touch_keys():
    for path in BATS:
        text = path.read_text(encoding="utf-8")
        assert "--env-file" in text
        assert not any(word in text for word in ("API_KEY", "GOOGLE_", "settings.env", "set /p"))


def test_install_hint_points_to_start_file_on_base_image(monkeypatch):
    monkeypatch.setenv("JOBVIS_IMAGE", "base")
    assert (
        ocr.install_hint() == f"OCR을 쓰려면 `JOBVIS 시작.bat`을 다시 열고 OCR 포함을 고르세요({ocr.OCR_EXTRA} 더 받음)"
    )

    monkeypatch.delenv("JOBVIS_IMAGE")
    assert "requirements-ocr.txt" in ocr.install_hint()  # 파이썬으로 직접 실행하는 사람 (F10)

    monkeypatch.setenv("JOBVIS_IMAGE", "ocr")
    assert "requirements-ocr.txt" in ocr.install_hint()


def test_env_setting_file_is_ignored_by_git():
    assert "start/jobvis.env" in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "*.bat text eol=crlf" in (ROOT / ".gitattributes").read_text(encoding="utf-8")
