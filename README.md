# 🧳 API 활용 국내 여행지 추천 프로그램

여행 날짜를 입력하면, **Google Gemini**가 그 시기에 어울리는 국내 여행 도시 2~3곳을 추천하고,
각 도시의 맛집을 **Kakao 로컬 API**로 찾아 하나의 여행 리포트로 정리해 주는 터미널(CLI) 프로그램입니다.

## 📌 주요 기능

- 여행 날짜(`--date`)를 입력받아 형식·유효성 검증
- Gemini로 국내 여행지 **복수 지역(2~3곳)** 추천 (날씨·추천 활동·추천 이유 포함)
- 추천된 각 도시마다 Kakao로 맛집 최대 5곳 검색 (이름·주소·분류·지도 링크)
- 결과를 **원본 JSON** + **읽기 좋은 Markdown 리포트**로 저장
- 외부 API가 실패해도 프로그램이 멈추지 않고 "데이터 없음"으로 계속 진행

## 🗂 폴더 구조

```text
travel-planner/
├── travel_planner.py     # 메인 프로그램
├── requirements.txt      # 필요한 라이브러리 목록
├── README.md             # 사용 설명서 (이 파일)
├── .env                  # 실제 API 키 (Git에 올리지 않음)
├── .env.example          # 키 입력용 빈 템플릿 (공유용)
├── .gitignore            # .env, results 등을 Git에서 제외
└── results/              # 실행 결과(JSON·MD)가 저장되는 폴더
```

## 🛠 준비물

- Python 3.10 이상
- API 키 2개
  - **Gemini API 키** — [Google AI Studio](https://aistudio.google.com/apikey)에서 발급
  - **Kakao REST API 키** — [Kakao Developers](https://developers.kakao.com)에서 앱 생성 후 발급

## 🔑 API 키 발급 및 설정

### 1) Gemini 키

1. [Google AI Studio](https://aistudio.google.com/apikey) 접속 → 로그인
2. **Create API key** 클릭 → 생성된 키 복사
3. (참고) 최근 발급되는 키는 `AQ.`로 시작하는 새 형식이며 정상 동작합니다.

### 2) Kakao REST API 키

1. [Kakao Developers](https://developers.kakao.com) → **내 애플리케이션** → 앱 생성
2. **앱 → 플랫폼 키**에서 **REST API 키** 복사
3. ⚠️ **중요**: **제품 설정 → 카카오맵 → 사용 설정(상태)** 을 **ON**으로 켜야
   로컬(맛집) 검색이 동작합니다. (끄면 `403 Forbidden` 발생)

### 3) `.env` 파일에 키 입력

`.env` 파일을 열어 아래처럼 복사한 키를 넣습니다. (따옴표·공백 없이)

```env
GEMINI_API_KEY=발급받은_Gemini_키
KAKAO_REST_API_KEY=발급받은_Kakao_REST_API_키
```

## ▶️ 실행 방법

```bash
# 1) 라이브러리 설치 (최초 1회)
pip install -r requirements.txt

# 2) 실행 (날짜는 YYYY-MM-DD 형식)
python travel_planner.py --date "2026-08-15"
```

정상 실행되면 아래처럼 진행 로그가 출력되고, 마지막에 결과 파일 위치를 알려줍니다.

```text
[진행] 여행 날짜: 2026-08-15
[진행] API 키 로드 완료
[진행] 사용할 Gemini 모델: gemini-flash-latest
[진행] 추천 도시 3곳: 강릉, 평창, 부산
[진행] '강릉' 맛집 검색 중...
        → 5곳 찾음
...
[완료] 결과 파일이 저장되었습니다:
   - 원본 데이터 : results/2026-08-15_raw.json
   - 여행 리포트 : results/2026-08-15_travel_plan.md
```

> 💡 계정마다 사용 가능한 Gemini 모델이 다르기 때문에, 프로그램이 실행 시
> 사용 가능한 모델을 **자동으로 선택**합니다. 모델 이름을 직접 고칠 필요가 없습니다.

## 📄 결과물 확인

실행이 끝나면 `results/` 폴더에 두 파일이 생깁니다.

- `YYYY-MM-DD_raw.json` — 추천 도시 + 도시별 맛집 + 처리 중 오류 기록이 담긴 원본 데이터
- `YYYY-MM-DD_travel_plan.md` — 사람이 읽기 좋은 최종 여행 리포트 (지역별 정리)

Markdown 파일은 VS Code의 **미리보기**로 열면 깔끔하게 렌더링되어 보입니다.

## 🧯 오류 처리 방식

프로그램은 잘못된 입력이나 외부 API 실패에도 안전하게 동작합니다.

| 상황 | 처리 방식 |
|---|---|
| 날짜 형식/유효성 오류 (예: `2026/08/15`, `2026-02-30`) | 안내 메시지 출력 후 종료 |
| API 키 누락 | 설정 방법 안내 후 종료 |
| Gemini JSON 파싱 실패 | **1회만** 재요청 (무한 반복 방지) |
| Kakao 검색 실패 / 결과 0건 | 해당 도시는 "데이터 없음"으로 표시하고 계속 진행 |

## 🔐 API 키 보안 주의사항

- 실제 키는 **`.env` 파일에만** 저장하며, 코드에 직접 쓰지 않습니다.
- `.gitignore`에 `.env`가 포함되어 있어 **GitHub에 키가 올라가지 않습니다.**
- 공유·제출 시에는 값이 비어 있는 `.env.example`만 올립니다.
- 혹시라도 키가 외부에 노출되면 **즉시 재발급**하세요.

## 🧩 사용 기술 요약

- **Python** (argparse, requests, json, datetime)
- **Google Gemini API** (`google-genai`) — 여행지 추천 생성
- **Kakao 로컬 API** — 도시별 맛집 검색
- **python-dotenv** — API 키를 `.env`로 안전하게 분리
