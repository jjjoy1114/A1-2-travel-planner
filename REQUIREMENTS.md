# ✅ 과제 요구사항 충족표 — API 활용 국내 여행지 추천 프로그램

> 과제지시서(기능 요구사항·결과물·보너스·과제 목표) 대비 실제 구현 결과를 정리한 표입니다.
> 근거는 실제 파일·함수 기준이며, 저장소: `github.com/jjjoy1114/A1-2-travel-planner`

## 1. 기능 요구사항

| # | 요구사항 | 구현 내용 | 근거 (파일·함수) | 충족 |
|---|---|---|---|:---:|
| 1 | **CLI 인터페이스** (argparse, 필수 `--date`, 입력 검증) | `--date` 필수 옵션, `YYYY-MM-DD` 형식·유효성 검증, 틀리면 사용법 안내 후 종료 | `parse_arguments()`, `validate_date()` | ✅ |
| 2 | **API 제공자 선택** (LLM 택1 / 지도 택1) | LLM = Google Gemini, 지도 = Kakao Local | `get_recommendations()`, `search_restaurants()` | ✅ |
| 3 | **LLM 연동 — JSON 구조화 출력** (city·weather·events·reason) | "JSON만 출력" 프롬프트로 강제, 파싱·검증 | `build_prompt()`, `check_recommendation()` | ✅ |
| 4 | **지도 API 연동 — 맛집 검색** (도시별 N곳, name·address·category·url·x/y, 헤더 인증, 0건도 계속) | 도시별 최대 5곳, 헤더 `Authorization: KakaoAK`, 0건이면 "데이터 없음" | `search_restaurants()` | ✅ |
| 5 | **최종 리포트(Markdown)** — 추천지+이유·날씨·행사·맛집(0건 표기)·**1일 일정(오전/오후/저녁)** | 지역별 정리 + 오전/오후/저녁 일정 제안 포함 | `build_markdown()`, 프롬프트의 `itinerary` | ✅ |
| 6 | **에러 처리** (try-except, 재시도 1회, errors 기록) | 인증·권한·쿼터·네트워크·파싱 오류 대응, 파싱 실패 시 1회 재요청, `errors` 태그 기록 | `get_recommendations()`, `search_restaurants()` | ✅ |
| 7 | **API 키 보안** (.env/환경변수, 제출물 미노출) | `.env` 분리 + `.gitignore` 제외, 공유용 `.env.example` | `load_api_keys()`, `.gitignore` | ✅ |
| 8 | **결과 저장** (`results/`, 원본 JSON + Markdown, JSON에 추천·맛집·errors) | `results/{날짜}_raw.json` + `{날짜}_travel_plan.md` 저장 | `save_raw_json()`, `save_markdown()` | ✅ |

## 2. 최종 결과물

| 결과물 | 구현 내용 | 충족 |
|---|---|:---:|
| CLI 기반 Python 프로그램 | `travel_planner.py` — 터미널에서 `--date`로 실행 | ✅ |
| 실행 결과 데이터 | `results/`에 원본 JSON 1개 + 리포트 Markdown 1개 | ✅ |
| README.md | 개요·실행법·키 설정·결과 확인·보안 주의 포함 | ✅ |

## 3. 보너스 과제 (2개 모두 수행)

| 보너스 | 구현 내용 | 근거 | 충족 |
|---|---|---|:---:|
| ① 복수 지역 추천 | 도시 2~3곳 추천(`recommended_cities`) + 지역별 반복 검색·정리 | `build_prompt()`, main 루프 | ✅ |
| ② 결과 캐싱 | 같은 날짜 재실행 시 API 생략·재사용, `--refresh`/`--max-age-hours` | `load_cached_result()` | ✅ |

## 4. 과제 목표 (스스로 설명 가능)

| 목표 | 설명할 수 있는 내용 | 충족 |
|---|---|:---:|
| REST API 요청/응답 + GET/POST | 요청→JSON 응답 구조, 조회=GET(카카오)·전송=POST(제미나이) | ✅ |
| LLM 출력 JSON → 다음 단계 입력 | 추천 JSON의 도시명을 맛집 검색 입력으로 자동 연결 | ✅ |
| 외부 API 대표 오류와 대응 | 인증·권한·쿼터·네트워크·파싱 오류를 "안 죽는 설계"로 처리 | ✅ |
| API 키 `.env` 관리 이유 | 실수 공개 방지·키 교체 편의·요금 사고 예방 | ✅ |

---

**요약: 기능 요구사항 8/8 · 결과물 3/3 · 보너스 2/2 · 과제 목표 4/4 — 전 항목 충족**
(AI 사전평가 결과 17/17 항목 통과 = 100%)
