"""실행 옵션의 이름(서울, 백엔드, 신입)을 사람인 코드로 바꾸고, 경력 조건을 판단한다."""

import difflib
import re

# 사람인 지역 코드표 1차 지역(loc_mcd), 국내만. https://oapi.saramin.co.kr/guide/code-table2 (2026-10-19 확인)
REGIONS = {
    "서울": "101000",
    "경기": "102000",
    "광주": "103000",
    "대구": "104000",
    "대전": "105000",
    "부산": "106000",
    "울산": "107000",
    "인천": "108000",
    "강원": "109000",
    "경남": "110000",
    "경북": "111000",
    "전남": "112000",  # 코드표 표기는 "전남광주전체"
    "전북": "113000",
    "충북": "114000",
    "충남": "115000",
    "제주": "116000",
    "전국": "117000",
    "세종": "118000",
}

# 사람인 직무 코드표 IT개발·데이터 전체(job_cd). https://oapi.saramin.co.kr/guide/code-table5?mcode=2 (2026-10-19 확인)
JOBS = {
    "게임개발": "80",
    "기술지원": "81",
    "데이터분석가": "82",
    "데이터엔지니어": "83",
    "백엔드/서버개발": "84",
    "보안컨설팅": "85",
    "앱개발": "86",
    "웹개발": "87",
    "웹마스터": "88",
    "유지보수": "89",
    "정보보안": "90",
    "퍼블리셔": "91",
    "프론트엔드": "92",
    "CISO": "93",
    "CPO": "94",
    "DBA": "95",
    "FAE": "96",
    "GM(게임운영)": "97",
    "IT컨설팅": "98",
    "QA/테스터": "99",
    "SE(시스템엔지니어)": "100",
    "SI개발": "101",
    "ICT컨설팅": "102",
    "검색엔진": "103",
    "네트워크": "104",
    "데이터라벨링": "105",
    "데이터마이닝": "106",
    "데이터시각화": "107",
    "딥러닝": "108",
    "머신러닝": "109",
    "모델링": "110",
    "모의해킹": "111",
    "미들웨어": "112",
    "반응형웹": "113",
    "방화벽": "114",
    "블록체인": "115",
    "빅데이터": "116",
    "빌링": "117",
    "솔루션": "118",
    "스크립트": "119",
    "신경망": "120",
    "악성코드": "121",
    "알고리즘": "122",
    "영상처리": "123",
    "웹표준·웹접근성": "124",
    "음성인식": "125",
    "이미지프로세싱": "126",
    "인프라": "127",
    "임베디드": "128",
    "자율주행": "129",
    "정보통신": "130",
    "챗봇": "131",
    "취약점진단": "132",
    "컴퓨터비전": "133",
    "크로스브라우징": "134",
    "크롤링": "135",
    "클라우드": "136",
    "텍스트마이닝": "137",
    "트러블슈팅": "138",
    "펌웨어": "139",
    "플러그인": "140",
    "핀테크": "141",
    "API": "142",
    "APM": "143",
    "AR(증강현실)": "144",
    "DBMS": "145",
    "DevOps": "146",
    "DLP": "147",
    "DW": "148",
    "ERP": "149",
    "ETL": "150",
    "FPGA": "151",
    "GIS": "152",
    "H/W": "153",
    "IDC": "154",
    "IIS": "155",
    "IoT": "156",
    "ISMS": "157",
    "MCU": "158",
    "Nginx": "159",
    "NLP(자연어처리)": "160",
    "NLU(자연어이해)": "161",
    "OCR": "162",
    "OLAP": "163",
    "RDBMS": "164",
    "RPA": "165",
    "RTOS": "166",
    "S/W": "167",
    "SAP": "168",
    "SDK": "169",
    "SOA": "170",
    "STT": "171",
    "TTS": "172",
    "UTM": "173",
    "VDI": "174",
    "VMware": "175",
    "VoIP": "176",
    "VPN": "177",
    "VR(가상현실)": "178",
    "WCF": "179",
    "아키텍쳐": "180",
    "AI(인공지능)": "181",
    "Windows": "182",
    "인터페이스": "183",
    ".NET": "184",
    "그누보드": "185",
    "라즈베리파이": "186",
    "쉘스크립트": "187",
    "액션스크립트": "188",
    "어셈블리": "189",
    "와이어샤크": "190",
    "파워빌더": "191",
    "ABAP": "192",
    "AIX": "193",
    "Ajax": "194",
    "Android": "195",
    "Angular": "196",
    "Apache": "197",
    "ArcGIS": "198",
    "ASP": "199",
    "ASP.NET": "200",
    "AWS": "201",
    "Azure": "202",
    "Bootstrap": "203",
    "C#": "204",
    "C++": "205",
    "C언어": "206",
    "CentOS": "207",
    "COBOL": "208",
    "CSS": "209",
    "CSS3": "210",
    "Delphi": "211",
    "Directx": "212",
    "Django": "213",
    "Docker": "214",
    "Eclipse": "215",
    "ECMAScript": "216",
    "ElasticStack": "217",
    "Flask": "218",
    "FLEX": "219",
    "Flutter": "220",
    "GCP": "221",
    "Git": "222",
    "GoLang": "223",
    "GraphQL": "224",
    "Groovy": "225",
    "Gulp": "226",
    "Hadoop": "227",
    "HBase": "228",
    "HTML": "229",
    "HTML5": "230",
    "IaaS": "231",
    "iBATIS": "232",
    "Ionic": "233",
    "iOS": "234",
    "Java": "235",
    "Javascript": "236",
    "Jenkins": "237",
    "JPA": "238",
    "jQuery": "239",
    "JSP": "240",
    "Kafka": "241",
    "Keras": "242",
    "Kotlin": "243",
    "Kubernetes": "244",
    "LabVIEW": "245",
    "Linux": "246",
    "Logstash": "247",
    "Lucene": "248",
    "MacOS": "249",
    "MariaDB": "250",
    "Matlab": "251",
    "Maven": "252",
    "MFC": "253",
    "MongoDB": "254",
    "MSSQL": "255",
    "MyBatis": "256",
    "MySQL": "257",
    "Node.js": "258",
    "NoSQL": "259",
    "Objective-C": "260",
    "OpenCV": "261",
    "OpenGL": "262",
    "OracleDB": "263",
    "OSS": "264",
    "PaaS": "265",
    "Pandas": "266",
    "Perl": "267",
    "PHP": "268",
    "PL/SQL": "269",
    "PostgreSQL": "270",
    "Pro-C": "271",
    "Python": "272",
    "Pytorch": "273",
    "QGIS": "274",
    "Qt": "275",
    "R": "276",
    "React": "277",
    "React-Native": "278",
    "ReactJS": "279",
    "Redis": "280",
    "Redux": "281",
    "RestAPI": "282",
    "Ruby": "283",
    "SaaS": "284",
    "SAS": "285",
    "Scala": "286",
    "Servlet": "287",
    "Solaris": "288",
    "Spark": "289",
    "Splunk": "290",
    "Spring": "291",
    "SpringBoot": "292",
    "SQL": "293",
    "SQLite": "294",
    "Storm": "295",
    "Struts": "296",
    "SVN": "297",
    "Swift": "298",
    "Sybase": "299",
    "Tensorflow": "300",
    "Tomcat": "301",
    "TypeScript": "302",
    "Ubuntu": "303",
    "Unity": "304",
    "Unix": "305",
    "Unreal": "306",
    "VB.NET": "307",
    "Verilog": "308",
    "Vert.x": "309",
    "VisualBasic": "310",
    "VisualC·C++": "311",
    "Vue.js": "312",
    "WAS": "313",
    "WebGL": "314",
    "Webpack": "315",
    "WebRTC": "316",
    "WPF": "317",
    "XML": "318",
    "아두이노": "319",
    "임베디드리눅스": "320",
    "SQA": "2229",
    "헬스케어": "2230",
    "메타버스": "2231",
    "풀스택": "2232",
    "Solidity": "2233",
    "스마트컨트랙트": "2234",
    "보안관제": "2239",
    "BI 엔지니어": "2246",
    "개발PM": "2247",
    "데이터 사이언티스트": "2248",
    "클라이언트": "2249",
    "HTTP": "2250",
    "암호화폐": "2251",
    "MMORPG": "2252",
    "Dapp": "2253",
    "DID": "2254",
    "크로스플랫폼": "2255",
    "루비온레일즈": "2256",
    "3D": "2260",
}

# 코드표 이름에 없는 줄임말
JOB_ALIASES = {
    "백엔드": "84",
    "서버": "84",
    "서버개발": "84",
    "QA": "99",
    "테스터": "99",
}

CAREERS = ("신입", "경력")

# 사람인 experience-level.code: 1 신입, 2 경력, 3 신입/경력, 0 경력무관
_CAREER_CODES = {"신입": {1, 3, 0}, "경력": {2, 3, 0}}


class CodeNotFoundError(ValueError):
    """모르는 이름. 메시지에 비슷한 이름과 쓸 수 있는 이름 전체를 담는다."""


def _normalize(name: str) -> str:
    return re.sub(r"\s+", "", name).lower()


def _lookup_table(names: dict[str, str], aliases: dict[str, str]) -> dict[str, str]:
    table = {}
    for name, code in names.items():
        table[_normalize(name)] = code
        table[_normalize(name.split("(")[0])] = code  # "AI(인공지능)" → "AI"
    for alias, code in aliases.items():
        table[_normalize(alias)] = code
    return table


_REGION_LOOKUP = _lookup_table(REGIONS, {})
_JOB_LOOKUP = _lookup_table(JOBS, JOB_ALIASES)


def _find(name: str, kind: str, names: dict[str, str], lookup: dict[str, str]) -> str:
    code = lookup.get(_normalize(name))
    if code:
        return code
    choices = sorted(names)
    similar = difflib.get_close_matches(name, choices, n=5, cutoff=0.4)
    lines = [f"'{name}'은(는) 모르는 {kind} 이름이에요."]
    if similar:
        lines.append("혹시: " + ", ".join(similar))
    lines.append(f"쓸 수 있는 {kind}: " + ", ".join(choices))
    raise CodeNotFoundError("\n".join(lines))


def to_region_code(name: str) -> str:
    return _find(name, "지역", REGIONS, _REGION_LOOKUP)


def to_job_code(name: str) -> str:
    return _find(name, "직무", JOBS, _JOB_LOOKUP)


def matches_career(code: int | None, career: str | None) -> bool:
    if career is None:
        return True
    return code in _CAREER_CODES[career]
