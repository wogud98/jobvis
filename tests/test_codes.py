import pytest

from agent import codes


@pytest.mark.parametrize(
    ("name", "code"),
    [
        ("백엔드/서버개발", "84"),
        ("데이터사이언티스트", "2248"),  # 코드표: "데이터 사이언티스트"
        ("python", "272"),  # 코드표: "Python"
        ("AI", "181"),  # 코드표: "AI(인공지능)"
        ("GM", "97"),  # 코드표: "GM(게임운영)"
        ("백엔드", "84"),
        ("서버", "84"),
        ("QA", "99"),
        ("테스터", "99"),
    ],
)
def test_job_name_to_code(name, code):
    assert codes.to_job_code(name) == code


def test_job_table_has_whole_it_category():
    assert len(codes.JOBS) == 260
    assert len(set(codes.JOBS.values())) == 260


def test_region_name_to_code():
    assert codes.to_region_code("서울") == "101000"
    assert codes.to_region_code(" 경기 ") == "102000"


def test_unknown_job_suggests_similar_and_lists_all():
    with pytest.raises(codes.CodeNotFoundError) as exc_info:
        codes.to_job_code("백엔드개발")

    message = str(exc_info.value)
    assert "백엔드개발" in message
    assert "혹시: 백엔드/서버개발" in message
    assert "쓸 수 있는 직무:" in message
    assert "Python" in message


def test_unknown_region_lists_all_regions():
    with pytest.raises(codes.CodeNotFoundError) as exc_info:
        codes.to_region_code("서울특별시")

    message = str(exc_info.value)
    assert "혹시: 서울" in message
    assert all(name in message for name in codes.REGIONS)


@pytest.mark.parametrize(
    ("career", "kept"),
    [
        ("신입", {1, 3, 0}),
        ("경력", {2, 3, 0}),
        (None, {1, 2, 3, 0, None}),
    ],
)
def test_matches_career(career, kept):
    for code in (1, 2, 3, 0, None):
        assert codes.matches_career(code, career) == (code in kept)
