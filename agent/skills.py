"""같은 기술의 다른 이름을 한 이름으로 묶는다 (v0.7.3 F2, F3). 사전은 agent/skill_aliases.yaml.

띄어쓰기·대소문자만 다른 이름은 사전 없이도 같게 본다. 사전에는 정말 같은 말만 둔다(SQL·MySQL처럼 다른 것은 묶지 않음).
"""

import re
from pathlib import Path

import yaml

PATH = Path(__file__).with_name("skill_aliases.yaml")


def normalize(name: str) -> str:
    """띄어쓰기를 지우고 대소문자를 무시한 비교용 글자."""
    return re.sub(r"\s+", "", name).casefold()


def load(path: Path = PATH) -> dict[str, str]:
    """{비교용 글자: 대표 이름}. 대표 이름 자신도 넣는다. 한 이름이 두 묶음에 있으면 ValueError."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    table: dict[str, str] = {}
    for canonical, aliases in data.items():
        for name in [canonical, *(aliases or [])]:
            key = normalize(str(name))
            if table.get(key, canonical) != canonical:
                raise ValueError(f"'{name}'이(가) '{table[key]}'와 '{canonical}' 두 묶음에 있음")
            table[key] = str(canonical)
    return table


ALIASES = load()


def key(name: str) -> str:
    """같은 기술이면 같은 글자. 사전에 있으면 대표 이름 기준, 없으면 띄어쓰기·대소문자만 무시."""
    normal = normalize(name)
    return normalize(ALIASES[normal]) if normal in ALIASES else normal


def display(name: str) -> str:
    """보일 이름. 사전에 있으면 대표 이름, 없으면 그대로."""
    return ALIASES.get(normalize(name), name)
