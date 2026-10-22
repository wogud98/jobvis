"""받은함: 사람이 넣은 공고 이미지를 OCR로 읽어 본문을 채운다 (v0.5 F37–F45, F47–F49).

robots 금지라 프로그램이 받지 못한 이미지를 사람이 브라우저에서 저장해 data/inbox/에 넣는다. 우회가 아니다 (N7).
그래프로 만들지 않는다. LLM도 갈림길도 없는 파일 반복이라 함수 하나로 충분하다 (v0.5 설계).
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from agent import ocr, postings, sheets, store

DIR = Path("data/inbox")  # data/는 .gitignore에 있음 (N7)
DONE = DIR / "done"
EXTENSIONS = ("png", "jpg", "jpeg", "webp")
MAX_UPLOAD = 10 * 1024 * 1024  # 화면에서 넣는 파일 최대 크기 (F49)
SOURCES = ("saramin", "jobkorea")

# 출처_공고ID[_번호].확장자 (F38). 번호가 없으면 1번.
_NAME = re.compile(r"^(saramin|jobkorea)_([0-9A-Za-z]+?)(?:_(\d+))?\.([0-9A-Za-z]+)$", re.I)


class UploadError(Exception):
    """화면에서 넣은 파일을 저장하지 않음 (F49)."""


@dataclass
class InboxResult:
    read: int = 0  # 읽은 파일 수
    filled: list[dict] = field(default_factory=list)  # 본문을 고친 공고 {"source", "id", "company", "status"}
    skipped: list[dict] = field(default_factory=list)  # {"file", "reason"}


def parse_name(name: str) -> tuple[str, str, int] | None:
    """파일 이름에서 (출처, 공고ID, 번호). 이름 형식이 틀리면 None. 확장자 검사는 따로 한다."""
    found = _NAME.match(name)
    if not found:
        return None
    source, job_id, number, _ = found.groups()
    return source.lower(), job_id, int(number) if number else 1


def _extension_ok(name: str) -> bool:
    return Path(name).suffix.lower().lstrip(".") in EXTENSIONS


def scan() -> tuple[dict[tuple[str, str], list[Path]], list[dict]]:
    """받은함 파일을 공고별로 묶어 번호순으로. 이름 형식이 틀리거나 모르는 확장자는 건너뛴다 (F38, F43)."""
    groups: dict[tuple[str, str], list[tuple[int, str, Path]]] = {}
    skipped = []
    files = sorted(p for p in DIR.iterdir() if p.is_file()) if DIR.is_dir() else []
    for file in files:
        parsed = parse_name(file.name)
        if parsed is None:
            skipped.append({"file": file.name, "reason": "이름 형식"})
        elif not _extension_ok(file.name):
            skipped.append({"file": file.name, "reason": "모르는 확장자"})
        else:
            source, job_id, number = parsed
            groups.setdefault((source, job_id), []).append((number, file.name, file))
    return {key: [file for _, _, file in sorted(items)] for key, items in sorted(groups.items())}, skipped


def _free_name(folder: Path, stem: str, suffix: str, also: Path | None = None) -> Path:
    """folder(와 also)에 없는 이름. 있으면 stem_2, stem_3 … 처럼 번호를 올린다."""
    number = 1
    while True:
        name = f"{stem}{suffix}" if number == 1 else f"{stem}_{number}{suffix}"
        if not (folder / name).exists() and not (also and (also / name).exists()):
            return folder / name
        number += 1


def _move_done(file: Path) -> None:
    DONE.mkdir(parents=True, exist_ok=True)
    file.replace(_free_name(DONE, file.stem, file.suffix))


def run(rows: list[dict]) -> InboxResult:
    """받은함 이미지를 읽어 원문 파일과 시트 "본문" 칸을 고친다. OCR이 설치돼 있는지는 부르기 전에 확인한다 (F44)."""
    result = InboxResult()
    groups, result.skipped = scan()
    by_key = {(sheets.source_code(row["source"]), row["id"]): row for row in rows if row.get("id")}
    for (source, job_id), files in groups.items():
        row = by_key.get((source, job_id))
        if row is None:
            result.skipped += [{"file": file.name, "reason": "시트에 없는 공고"} for file in files]
            continue
        texts, read_files = [], []
        for file in files:  # 크기 하한·장수 상한 없음. 사람이 고른 이미지라서 (F42)
            try:
                texts.append(ocr.read(file.read_bytes()))
            except Exception as e:  # 그 파일만 건너뛰고 받은함에 남긴다 (F43)
                result.skipped.append({"file": file.name, "reason": f"OCR 실패({type(e).__name__})"})
                continue
            read_files.append(file)
        if not read_files:
            continue
        # 원문 저장 → 시트 → 파일 옮기기 순서. 중간에 멈추면 이미지가 받은함에 남아 다시 처리된다.
        content = postings.add_ocr(postings.load(source, job_id), texts)
        postings.save(source, job_id, content)
        text, ocr_texts = postings.split(content)
        # 사람이 이미지를 넣었으니 못 읽은 이미지는 0으로 본다 (v0.5 설계)
        status = postings.status(text, ocr_texts, 0)
        if status != row["body"]:
            # 본문이 바뀐 줄은 "평가"를 켜서 다음 --score에서 다시 평가되게 한다 (F40)
            store.update_cells(row["row"], {"본문": status, "평가": True})
            row["body"] = status
        result.read += len(read_files)
        result.filled.append({"source": source, "id": job_id, "company": row["company"], "status": status})
        for file in read_files:
            try:
                _move_done(file)  # 같은 이미지가 두 번 붙지 않게 (F41)
            except OSError as e:
                result.skipped.append({"file": file.name, "reason": f"옮기기 실패({type(e).__name__})"})
    return result


def save_upload(source: str, job_id: str, name: str, data: bytes) -> Path:
    """화면에서 넣은 이미지를 받은함에 F38 이름으로 저장한다. OCR은 하지 않는다 (F47–F49)."""
    extension = Path(name).suffix.lower()
    if extension.lstrip(".") not in EXTENSIONS:
        raise UploadError(f"{name}: png, jpg, jpeg, webp만 넣을 수 있음")
    if len(data) > MAX_UPLOAD:
        raise UploadError(f"{name}: 10MB를 넘음")
    if source not in SOURCES:
        raise UploadError(f"{name}: 출처를 알 수 없음")
    DIR.mkdir(parents=True, exist_ok=True)
    # 이미 처리해 done으로 옮긴 이미지와 이름이 겹치지 않게 둘 다 본다
    target = _free_name(DIR, f"{source}_{job_id}", extension, also=DONE)
    target.write_bytes(data)
    return target
