# v0.5.5 설계

기준 문서: [01-requirements.md](01-requirements.md) (2026-10-22 확정, F1–F3, N1). 바뀌는 곳은 `app.py`의 프로필 탭뿐.

## 모듈 다이어그램

```mermaid
classDiagram
    direction LR
    class app {
        +CLEARED  session_state 키: 비운 칸 set
        +GENERATION  session_state 키: 칸별 번호
        +field_key(field, default) str
        +clear_field(keys)
        +clear_all()
        +confirm_clear_all() st.dialog
        +show_field(field, default, taken)
        +show_field_with_clear(field, default, taken)
        +show_profile()
    }
    class profile_form {
        +FIELDS
        +to_form(data) dict
        +from_form(values) dict
    }
    app --> profile_form
```

- 빈 값은 `profile_form.to_form(None)`에서 가져와 칸 종류마다 따로 정하지 않음.
- `pick_key`를 `field_key`로 바꾸고 모든 입력란에 key를 줌. key는 `field-{칸}-{번호}-{기본값 해시}`. 기본값이 바뀌거나(파일·이력서) 번호가 오르면(↺) 새 key라 새 값으로 그려짐. 전에는 고르기 칸만 key가 있고 나머지는 key 없이 기본값으로 다시 그렸음(v0.5 F21). key 없는 입력란은 이미 빈 칸을 다시 비울 때 값이 바뀌지 않아 key로 바꿈.
- 예전 key 지우기는 고르기 칸만 함. 고르기 칸은 값을 session_state에 직접 넣기 때문.

## 흐름

```mermaid
sequenceDiagram
    participant U as 사용자
    participant A as app
    participant S as session_state
    participant F as profile.yaml
    U->>A: ↺ (칸 하나)
    A->>S: clear_field: CLEARED에 칸 추가, 번호 +1
    A->>A: 다시 그리기: 기본값 = 파일 값, CLEARED 칸은 빈 값
    U->>A: 전체 초기화
    A->>U: 확인 창
    U->>A: 비우기
    A->>S: clear_all(콜백): 모든 칸 clear_field, 이력서 채운 값 버림
    U->>A: 💾 저장
    A->>F: 화면 값 저장
    A->>S: CLEARED 버림 (이제 파일 값 = 화면 값)
```

- 확인 창 버튼은 `on_click=clear_all` 콜백에서 비움. 확인 창은 창 안만 다시 그려지므로 콜백이어야 값이 확실히 바뀜.
- 이력서로 채우면 CLEARED를 버림. 채운 값이 비운 표시에 가려지지 않게.
- ↺는 입력란 오른쪽 좁은 열의 tertiary 버튼. CSS로 테두리·그림자를 지우고 흐린 글자, 마우스를 올리면 초록.
