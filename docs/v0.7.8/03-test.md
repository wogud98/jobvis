# v0.7.8 테스트

2026-11-06 실행.

## 실행한 명령

```bash
ruff check .            # All checks passed!
ruff format --check .   # 131 files already formatted
python -m pytest        # 760 passed (750개 → 760개)
```

## 요구사항별 확인

| ID | 확인 내용 | 테스트 | 결과 |
| --- | --- | --- | --- |
| F1 | 글자 없는 PDF(10쪽)는 `ImagePdf`, `read_files`가 건너뛰지 않고 `pdfs`에 넣음. 화면에서 경고 없이 LLM으로 보내 칸 채움 | `test_image_pdf_is_not_skipped_but_sent_as_file`, `test_resume_fill_sends_image_pdf_to_llm` | 통과 |
| F2 | 글자 파일 + 그림 PDF가 한 사람 메시지(글자 블록 + PDF마다 이름·파일 블록), LLM 한 번. PDF 없으면 메시지가 전과 같음 | `test_read_files_mixes_text_and_image_pdf`, `test_messages_put_text_and_pdf_files_in_one_human_message`, `test_ask_sends_image_pdf_once`, `test_messages_without_pdf_stay_as_before` | 통과 |
| F3 | 11쪽 그림 PDF는 "10쪽 초과 (그림 PDF)"로 건너뜀 | `test_extract_bad_files[long-scan.pdf…]` | 통과 |
| F4 | 쪽 0개·깨진 PDF는 전 이유 그대로 | `test_extract_bad_files[no-pages.pdf…]`, `[broken.pdf…]`, `test_read_files_skips_bad_ones_and_cuts_text` | 통과 |
| F5 | 그림 PDF를 보낸 호출의 모르는 오류는 "이 모델은 그림 PDF를 읽지 못함 (예외 이름)", 키 오류는 키 안내. 칸 안 바꿈 | `test_resume_fill_image_pdf_model_error`(2가지) | 통과 |
| F6 | 업로드 도움말에 "글자가 그림인 PDF(10쪽까지)는 파일 전체가 전송됩니다" | `test_resume_help_says_image_pdf_is_sent_whole` | 통과 |
| N1 | 새 의존성 없음 | `requirements.txt` 그대로 | 통과 |
| N2 | 오류 문구에 예외 메시지(파일 내용) 없음 | `test_resume_fill_image_pdf_model_error`의 `secret` 확인, `test_extract_bad_files`의 `garbage` 확인 | 통과 |
| N3 | `init_chat_model(llm_model())` 그대로, 제공자 클래스 import 없음 | 코드 확인, `test_ask_calls_model_once_with_text` | 통과 |
| N4 | 실제 LLM 호출 없음 | 가짜 LLM(`FakeListChatModel`)·`resume.ask` 바꿔치기만 씀 | 통과 |

## 그 밖에 확인

- 설치된 `langchain-google-genai`의 `_parse_chat_history`에 `resume.messages(...)`를 넣어 봄(네트워크 없음): 글자 2개 + `inline_data`(`application/pdf`, 원본 바이트) 한 개로 바뀜

## 미확인

- 실제 Gemini가 그림 PDF를 읽고 프로필 칸을 채우는지(재리 PC 확인 필요)
- Claude(`langchain-anthropic`)로 바꿨을 때 같은 파일 블록이 되는지(설치·실행 안 함)
- 그림 PDF 10쪽이 무료 한도 안에서 되는지, 걸리는 시간
