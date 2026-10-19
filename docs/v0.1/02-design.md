# v0.1 설계

## 유스케이스

사용자는 터미널에서 한 가지 일만 합니다. 외부 시스템 3개가 관여합니다.

```mermaid
flowchart LR
    user(["사용자"])
    subgraph JOBVIS
        uc1(["키워드로 공고 수집"])
        uc2(["자격요건 요약"])
        uc3(["시트에 저장"])
    end
    saramin[("사람인 API")]
    llm[("LLM<br>Gemini / Claude")]
    sheet[("구글 시트")]

    user --> uc1
    uc1 -. include .-> uc2
    uc2 -. include .-> uc3
    uc1 --> saramin
    uc2 --> llm
    uc3 --> sheet
```

## 모듈(클래스) 다이어그램

클래스 대신 모듈 단위로 나눴습니다. `State`는 노드들이 주고받는 데이터 구조입니다.

```mermaid
classDiagram
    direction LR
    class main {
        +main()
    }
    class graph {
        +fetch(state) State
        +summarize(state) State
        +save(state) State
        +build_graph() CompiledGraph
    }
    class State {
        <<TypedDict>>
        keyword: str
        location: str | None
        job: dict
        requirements: str
    }
    class saramin {
        +fetch_jobs(keyword, location, count) list
        -_to_row(job) dict
    }
    class sheets {
        +HEADER: list
        +append_row(values)
    }
    main ..> graph : build_graph().invoke()
    graph *-- State
    graph ..> saramin : fetch에서 호출
    graph ..> sheets : save에서 호출
```

## 시퀀스 다이어그램

```mermaid
sequenceDiagram
    actor U as 사용자
    participant M as main.py
    participant G as graph (LangGraph)
    participant S as saramin.py
    participant API as 사람인 API
    participant L as LLM
    participant SH as sheets.py
    participant GS as 구글 시트

    U->>M: python main.py --keyword "백엔드 신입"
    M->>G: invoke({keyword, location})
    G->>S: fetch_jobs(keyword, location, 1)
    S->>API: GET /job-search
    API-->>S: 공고 JSON
    S-->>G: {job}
    G->>L: 프롬프트 + 공고 정보
    L-->>G: 자격요건 한 줄
    G->>SH: append_row([...])
    SH->>GS: 제목 줄 확인 후 한 줄 추가
    G-->>M: 최종 State
    M-->>U: 저장 완료 출력
```

## 상태(그래프) 다이어그램

LangGraph에 등록된 실제 흐름입니다. 각 노드는 바뀐 칸만 돌려주고 LangGraph가 State에 합칩니다.

```mermaid
stateDiagram-v2
    direction LR
    [*] --> fetch: keyword, location
    fetch --> summarize: + job
    fetch --> [*]: 공고 없음 (종료)
    summarize --> save: + requirements
    save --> [*]
```

## 설계 결정

| 결정 | 이유 | 다시 볼 시점 |
| --- | --- | --- |
| LangGraph로 단계 연결 | 이후 조건 분기(적합도 낮으면 저장 안 함)와 반복을 노드 수정 없이 추가 | - |
| `init_chat_model` + `LLM_MODEL` 설정 | 유료 Claude 대신 무료 Gemini로 개발하고, 설정 한 줄로 교체 | - |
| 시트 저장은 gspread 직접 호출 | MCP 서버 설치·인증 없이 파이썬만으로 동작해 입문 단계에 단순 | v0.4에서 MCP 전환 |
| 공고 1건만 처리 | 최소 동작부터 확인 | v0.2 |
| 자격요건은 API 필드(경력·학력·키워드)로 요약 | 사람인 API 검색 결과에는 상세 본문이 없음 | v0.3 적합도 설계 때 |
