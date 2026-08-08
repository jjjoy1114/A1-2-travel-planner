"""
API 활용 국내 여행지 추천 프로그램
------------------------------------
사용법:
    python travel_planner.py --date "2026-08-15"
    python travel_planner.py --date "2026-08-15" --refresh          # 캐시 무시하고 재호출
    python travel_planner.py --date "2026-08-15" --max-age-hours 24 # 24시간 지난 캐시는 새로

동작 흐름:
    1) 여행 날짜를 입력받아 형식/유효성 검증
    2) .env 에서 API 키 2개 로드
    3) (캐시) 같은 날짜 결과가 있으면 재사용
    4) Gemini 로 국내 여행지 2~3곳 추천 (JSON 형식)
    5) 각 도시마다 Kakao 로 맛집 검색
    6) 원본 결과(JSON)와 최종 여행 리포트(Markdown)를 results/ 에 저장

비전공자용 메모:
    - REST API = 인터넷 주소로 요청을 보내면 JSON(정리된 데이터)을 돌려주는 구조
    - Gemini = "어디로 갈지" 추천 생성 담당 (본문 데이터를 보내야 하므로 POST)
    - Kakao  = "그 도시의 맛집" 검색 담당 (데이터 조회만 하므로 GET)
"""

import argparse
import datetime
import json
import os
import sys
import time

import requests
from dotenv import load_dotenv

try:
    from google import genai
except ImportError:
    print("[오류] google-genai 라이브러리가 없습니다.")
    print("      터미널에서 아래 명령으로 설치하세요:")
    print("      pip install google-genai requests python-dotenv")
    sys.exit(1)


# 결과 JSON의 스키마 버전 (형식이 바뀌면 올린다 → 파싱 호환성 관리)
SCHEMA_VERSION = "1.0"


# ---------------------------------------------------------------------------
# 1) 날짜 입력 받기 + 검증
# ---------------------------------------------------------------------------
def parse_arguments():
    """터미널에서 옵션을 읽어온다."""
    parser = argparse.ArgumentParser(
        description="국내 여행지 추천 프로그램 (Gemini + Kakao)",
        epilog='예) python travel_planner.py --date "2026-08-15"   '
        '(잘못된 예: "2026/08/15", "2026-13-40")',
    )
    parser.add_argument(
        "--date",
        required=True,
        help='여행 날짜, 형식은 YYYY-MM-DD (예: "2026-08-15" / 잘못된 예: "2026/08/15")',
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="이미 저장된 결과가 있어도 API 를 다시 호출해 새로 만든다",
    )
    parser.add_argument(
        "--max-age-hours",
        type=float,
        default=None,
        help="캐시 유효 시간(시간). 이 시간보다 오래된 결과는 새로 만든다(기본: 무제한)",
    )
    return parser.parse_args()


def validate_date(date_text):
    """
    날짜 문자열이 'YYYY-MM-DD' 형식이고 실제로 존재하는 날짜인지 확인한다.
    입력: 문자열 (예: "2026-08-15")
    출력: datetime.date 객체 (틀리면 안내 후 종료)
    """
    try:
        # strptime 은 형식이 안 맞거나 없는 날짜(2월 30일 등)면 예외를 낸다
        parsed = datetime.datetime.strptime(date_text, "%Y-%m-%d").date()
    except ValueError:
        print(f"[오류] 날짜 형식이 올바르지 않습니다: {date_text}")
        print('       올바른 예시: --date "2026-08-15"')
        print('       잘못된 예시: "2026/08/15"(구분자), "2026-02-30"(없는 날짜)')
        sys.exit(1)
    return parsed


# ---------------------------------------------------------------------------
# 2) API 키 로드
# ---------------------------------------------------------------------------
def load_api_keys():
    """.env 파일에서 키 2개를 읽어온다. 없으면 설정 방법을 안내하고 종료."""
    load_dotenv()  # 같은 폴더의 .env 파일을 읽어 환경변수로 등록
    gemini_key = os.getenv("GEMINI_API_KEY")
    kakao_key = os.getenv("KAKAO_REST_API_KEY")

    missing = []
    if not gemini_key or gemini_key.startswith("여기에"):
        missing.append("GEMINI_API_KEY")
    if not kakao_key or kakao_key.startswith("여기에"):
        missing.append("KAKAO_REST_API_KEY")

    if missing:
        print("[오류] 다음 API 키가 설정되지 않았습니다:", ", ".join(missing))
        print("       .env 파일을 열어 아래처럼 실제 키 값을 넣어주세요:")
        print("       GEMINI_API_KEY=발급받은_키")
        print("       KAKAO_REST_API_KEY=발급받은_키")
        sys.exit(1)

    return gemini_key, kakao_key


# ---------------------------------------------------------------------------
# 3) Gemini 로 여행지 추천 (JSON)
# ---------------------------------------------------------------------------
def build_prompt(travel_date, reinforce=False):
    """
    Gemini 에게 보낼 지시문. 반드시 JSON 만 출력하도록 요청한다.
    reinforce=True 이면(=재요청 시) '이전 응답이 올바른 JSON이 아니었다'는
    안내를 앞에 붙여 프롬프트를 보강한다.
    """
    prefix = ""
    if reinforce:
        prefix = (
            "직전 응답이 올바른 JSON 이 아니었습니다. "
            "이번에는 코드블록(```)이나 설명 없이, 아래 형식의 순수 JSON 만 출력하세요.\n\n"
        )
    return prefix + f"""당신은 한국 국내 여행 플래너입니다.
여행 날짜: {travel_date}

이 날짜에 국내 여행지로 좋은 도시 2~3곳을 추천해 주세요.
반드시 아래 JSON 형식으로만 답하세요. 다른 설명, 인사말, 마크다운 표시는 절대 넣지 마세요.

{{
  "recommended_cities": [
    {{
      "city": "도시 이름 (예: 제주, 부산, 강릉)",
      "weather": "이 시기의 일반적인 날씨 요약",
      "events": ["이 시기에 어울리는 행사/축제/활동 1", "활동 2"],
      "reason": "이 도시를 추천하는 이유 2~4문장"
    }}
  ]
}}

주의:
- city 는 Kakao 지도에서 검색 가능한 실제 한국 도시/지역명으로 쓰세요.
- 반드시 2곳 이상 3곳 이하로 추천하세요.
"""


def clean_json_text(text):
    """Gemini 응답에서 코드블록 기호(```json ... ```)를 제거한다."""
    text = text.strip()
    if text.startswith("```"):
        # 첫 줄(```json)과 마지막 줄(```) 제거
        lines = text.splitlines()
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        text = "\n".join(lines).strip()
    return text


def check_recommendation(data):
    """
    Gemini 결과 구조를 검사한다.
    문제가 없으면 None 을, 있으면 '무엇이 잘못됐는지' 설명 문자열을 돌려준다.
    (어떤 키가 누락됐는지 알려주기 위함)
    """
    if not isinstance(data, dict):
        return "최상위가 JSON 객체(dict)가 아님"
    cities = data.get("recommended_cities")
    if not isinstance(cities, list) or len(cities) == 0:
        return "'recommended_cities' 가 비어 있거나 리스트가 아님"
    for i, c in enumerate(cities, start=1):
        if not isinstance(c, dict):
            return f"{i}번째 항목이 객체가 아님"
        for key in ("city", "weather", "reason"):
            if not c.get(key):
                return f"{i}번째 항목에 '{key}' 키가 누락됨"
    return None


def pick_model(client, errors):
    """
    내 계정에서 실제로 쓸 수 있는 Gemini 모델을 자동으로 하나 고른다.
    계정마다 사용 가능한 모델이 다르기 때문에, 목록을 조회해서
    선호하는 순서대로 있는지 확인하고, 없으면 아무 flash 모델이나 쓴다.
    """
    preferred = [
        "gemini-flash-latest",
        "gemini-2.0-flash",
        "gemini-2.0-flash-001",
        "gemini-1.5-flash",
    ]
    try:
        available = []
        for m in client.models.list():
            name = m.name.replace("models/", "")
            actions = getattr(m, "supported_actions", None)
            # generateContent 를 지원하는 모델만 후보로
            if actions is None or "generateContent" in actions:
                available.append(name)

        for p in preferred:
            if p in available:
                return p
        for name in available:
            if "flash" in name and "vision" not in name:
                return name
        if available:
            return available[0]
    except Exception as e:
        errors.append(f"[NETWORK] 모델 목록 조회 실패: {e}")

    return "gemini-2.0-flash"


def get_recommendations(client, travel_date, model_name, errors):
    """
    Gemini 를 호출해 추천 도시 목록을 받는다.  (HTTP 메서드: POST — 프롬프트 본문 전송)
    JSON 파싱에 실패하면 딱 1번만 재요청하며, 이때 프롬프트를 보강한다(무한 반복 금지).
    """
    for attempt in range(1, 3):  # 최대 2번 시도 (최초 + 재요청 1회)
        prompt = build_prompt(travel_date, reinforce=(attempt > 1))
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            raw_text = response.text
        except Exception as e:  # 네트워크/인증/쿼터 등 모든 호출 오류
            errors.append(f"[NETWORK] Gemini 호출 실패(시도 {attempt}): {e}")
            print(f"[경고] Gemini 호출 실패 (시도 {attempt}): {e}")
            continue

        cleaned = clean_json_text(raw_text)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            snippet = cleaned[:120].replace("\n", " ")  # 원문 앞부분(디버깅용)
            errors.append(
                f"[PARSE] Gemini JSON 파싱 실패(시도 {attempt}): {e} | 응답 원문: {snippet}"
            )
            print(f"[경고] 응답을 JSON 으로 읽지 못했습니다 (시도 {attempt}). 재요청합니다.")
            continue

        problem = check_recommendation(data)
        if problem is None:
            return data["recommended_cities"]
        errors.append(f"[PARSE] Gemini 응답 구조 오류(시도 {attempt}): {problem}")
        print(f"[경고] 추천 결과 구조 오류 (시도 {attempt}): {problem}")

    print("[오류] Gemini 추천을 받지 못했습니다. 프로그램을 종료합니다.")
    sys.exit(1)


# ---------------------------------------------------------------------------
# 4) Kakao 로 도시별 맛집 검색
# ---------------------------------------------------------------------------
def normalize_city(name):
    """
    LLM 이 준 도시 이름을 Kakao 검색에 넣기 좋게 다듬는다(최소 정규화).
    - 괄호/대괄호와 그 안 내용 제거:  '강릉(경포대)' -> '강릉',  '부산[해운대]' -> '부산'
    - 쉼표/슬래시 뒤 부가 설명 제거:  '부산, 해운대' -> '부산',  '제주 / 서귀포' -> '제주'
    - 여러 칸 공백을 한 칸으로, 앞뒤 공백 제거
    (지명 세분화·법정동 보정 등 고급 처리는 하지 않는다.)
    """
    import re

    text = str(name)
    text = re.sub(r"[\(\[（【].*?[\)\]）】]", "", text)  # 괄호류 내용 제거
    text = re.split(r"[,/]", text)[0]                    # 쉼표/슬래시 앞부분만
    text = re.sub(r"\s+", " ", text)                     # 공백 정리
    return text.strip()


def _kakao_items(documents):
    """Kakao 응답의 documents 리스트를 우리 형식의 맛집 리스트로 바꾼다."""
    restaurants = []
    for doc in documents:
        restaurants.append(
            {
                "name": doc.get("place_name", ""),
                "address": doc.get("road_address_name") or doc.get("address_name", ""),
                "category": doc.get("category_name", ""),
                "url": doc.get("place_url", ""),
                "x": doc.get("x", ""),
                "y": doc.get("y", ""),
            }
        )
    return restaurants


def search_restaurants(kakao_key, city, errors, max_count=5, retries=2):
    """
    Kakao 로컬 키워드 검색으로 '<도시> 맛집' 을 찾는다.
    - HTTP 메서드: GET (장소를 '조회'만 하므로)
    - 인증: 헤더 'Authorization: KakaoAK {REST_API_KEY}'
    - 반환: 맛집 dict 리스트 (실패/0건이면 빈 리스트, 프로그램은 계속 진행)

    네트워크 일시 오류에는 짧은 backoff 를 두고 최대 retries 번 재시도한다.
    단, 401/403(인증·권한) 오류는 재시도해도 소용없으므로 즉시 포기한다.
    """
    query_city = normalize_city(city)  # 도시명 정규화 후 검색
    url = "https://dapi.kakao.com/v2/local/search/keyword.json"
    headers = {"Authorization": f"KakaoAK {kakao_key}"}
    params = {"query": f"{query_city} 맛집", "size": max_count}

    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            resp.raise_for_status()  # 200 이 아니면 예외 발생
            return _kakao_items(resp.json().get("documents", []))
        except requests.HTTPError as e:
            code = getattr(e.response, "status_code", None)
            if code in (401, 403):
                # 401=키 자체 문제, 403=권한(카카오맵 사용설정) 문제 → 재시도 무의미
                errors.append(f"[AUTH] Kakao 인증/권한 오류({city}, HTTP {code})")
                print(f"[경고] '{city}' 검색 인증 오류(HTTP {code}) → 데이터 없음으로 진행")
                return []
            errors.append(f"[NETWORK] Kakao HTTP 오류({city}, HTTP {code}) 시도 {attempt}")
        except requests.RequestException as e:
            errors.append(f"[NETWORK] Kakao 요청 실패({city}) 시도 {attempt}: {e}")

        if attempt < retries:
            time.sleep(0.5 * attempt)  # 짧은 backoff (0.5초, 1.0초 …)

    print(f"[경고] '{city}' 맛집 검색 실패 → 데이터 없음으로 진행")
    return []


# ---------------------------------------------------------------------------
# 5) 결과 저장 (JSON 원본 + Markdown 리포트)
# ---------------------------------------------------------------------------
def save_raw_json(result, date_text):
    """원본 결과를 results/{날짜}_raw.json 으로 저장. 저장 실패 시 안내 후 종료."""
    try:
        os.makedirs("results", exist_ok=True)
        path = os.path.join("results", f"{date_text}_raw.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        return path
    except OSError as e:
        print(f"[오류] 결과 JSON 저장 실패 (폴더 권한/디스크 공간을 확인하세요): {e}")
        sys.exit(1)


def load_cached_result(date_text, max_age_hours=None):
    """
    같은 날짜의 원본 JSON 이 이미 results/ 에 있으면 불러온다(캐시).
    max_age_hours 가 주어지면 그 시간보다 오래된 캐시는 무효(None)로 본다.
    캐시 위치: results/{날짜}_raw.json  (기본 만료 정책: 없음 — 파일 삭제/‑‑refresh 로 갱신)
    """
    path = os.path.join("results", f"{date_text}_raw.json")
    if not os.path.exists(path):
        return None
    if max_age_hours is not None:
        age_hours = (time.time() - os.path.getmtime(path)) / 3600.0
        if age_hours > max_age_hours:
            print(f"[캐시] 저장된 결과가 {age_hours:.1f}시간 지나 새로 만듭니다.")
            return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def count_empty_cities(cities):
    """맛집이 하나도 없는('데이터 없음') 도시 수를 센다."""
    return sum(1 for c in cities if not c.get("restaurants"))


def build_markdown(result):
    """최종 여행 리포트를 Markdown 문자열로 만든다."""
    date_text = result["date"]
    cities = result["recommended_cities"]
    empty = count_empty_cities(cities)

    lines = []
    lines.append(f"# 🧳 {date_text} 국내 여행 추천 리포트\n")
    lines.append(f"- 추천 도시: {len(cities)}곳")
    lines.append(f"- 맛집 데이터 없음: {empty}곳\n")

    for city in cities:
        lines.append(f"\n## 📍 {city['city']}\n")
        lines.append(f"- **날씨**: {city.get('weather', '정보 없음')}")
        events = city.get("events") or []
        if events:
            lines.append(f"- **추천 활동/행사**: {', '.join(events)}")
        lines.append(f"- **추천 이유**: {city.get('reason', '')}\n")

        lines.append("### 🍽️ 추천 맛집")
        restaurants = city.get("restaurants") or []
        if not restaurants:
            lines.append("- 데이터 없음\n")
        else:
            for r in restaurants:
                name, url = r["name"], r["url"]
                addr, cat = r["address"], r["category"]
                if url:
                    lines.append(f"- [{name}]({url}) — {addr}  \n  분류: {cat}")
                else:
                    lines.append(f"- {name} — {addr}  \n  분류: {cat}")
            lines.append("")

    if result.get("errors"):
        lines.append("\n---\n")
        lines.append("### ⚠️ 처리 중 발생한 문제 기록")
        for err in result["errors"]:
            lines.append(f"- {err}")

    return "\n".join(lines)


def save_markdown(markdown_text, date_text):
    """리포트를 results/{날짜}_travel_plan.md 로 저장. 저장 실패 시 안내 후 종료."""
    try:
        os.makedirs("results", exist_ok=True)
        path = os.path.join("results", f"{date_text}_travel_plan.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(markdown_text)
        return path
    except OSError as e:
        print(f"[오류] 리포트 저장 실패 (폴더 권한/디스크 공간을 확인하세요): {e}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# 메인 흐름
# ---------------------------------------------------------------------------
def main():
    errors = []  # 진행 중 생긴 문제들을 모아둔다 (카테고리 태그: AUTH/NETWORK/PARSE)

    # 1) 날짜
    args = parse_arguments()
    travel_date = validate_date(args.date)
    date_text = travel_date.isoformat()
    print(f"[진행] 여행 날짜: {date_text}")

    # 1-b) 캐싱(보너스): 같은 날짜 결과가 이미 있으면 API 호출을 건너뛴다
    if not args.refresh:
        cached = load_cached_result(date_text, args.max_age_hours)
        if cached:
            md_path = save_markdown(build_markdown(cached), date_text)
            print("[캐시] 저장된 결과를 재사용합니다 (API 호출 생략, 비용/속도 절약).")
            print("       새로 만들려면 --refresh 옵션을 붙이세요.")
            print(f"   - 원본 데이터 : results/{date_text}_raw.json")
            print(f"   - 여행 리포트 : {md_path}")
            return

    # 2) 키
    gemini_key, kakao_key = load_api_keys()
    print("[진행] API 키 로드 완료")

    # 3) Gemini 추천
    client = genai.Client(api_key=gemini_key)
    model_name = pick_model(client, errors)
    print(f"[진행] 사용할 Gemini 모델: {model_name}")
    print("[진행] Gemini 로 여행지 추천 요청 중...")
    cities = get_recommendations(client, date_text, model_name, errors)
    print(f"[진행] 추천 도시 {len(cities)}곳: {', '.join(c['city'] for c in cities)}")

    # 4) 도시별 맛집
    for city in cities:
        print(f"[진행] '{city['city']}' 맛집 검색 중...")
        city["restaurants"] = search_restaurants(kakao_key, city["city"], errors)
        print(f"        → {len(city['restaurants'])}곳 찾음")

    # 5) 결과 정리 및 저장
    result = {
        "schema_version": SCHEMA_VERSION,
        "date": date_text,
        "recommended_cities": cities,
        "errors": errors,
    }
    json_path = save_raw_json(result, date_text)
    md_path = save_markdown(build_markdown(result), date_text)

    empty = count_empty_cities(cities)
    print("\n[완료] 결과 파일이 저장되었습니다:")
    print(f"   - 원본 데이터 : {json_path}")
    print(f"   - 여행 리포트 : {md_path}")
    print(f"   - 맛집 데이터 없음: {empty}곳 / 추천 {len(cities)}곳")
    if errors:
        print(f"\n[안내] 처리 중 {len(errors)}건의 문제가 있었지만 리포트는 정상 생성되었습니다.")


if __name__ == "__main__":
    main()
