# 📰 뉴스 모니터링 어시스턴트

**[한국어]** | [日本語](README.ja.md) | [English](README.en.md)

네이버·다음 뉴스를 수집하고, GPT AI가 기사를 자동 분류하여 엑셀로 출력하는 웹 애플리케이션입니다.
Streamlit으로 구동되며, 한국어·일본어 UI를 지원합니다.

---

## 주요 기능

| 기능 | 설명 |
|------|------|
| 기사 수집 | 네이버 검색 API (키워드당 최대 1,000건), 다음 뉴스 스크래핑 (키워드당 최대 약 200~300건) |
| AI 분류 | GPT-4o-mini가 사용자 정의 분류 기준에 따라 각 기사를 자동 분류 |
| 엑셀 출력 | 일람 · 사용자 분류 시트 · 보류 · 해당없음 4종 구성의 .xlsx 파일 생성 |
| 프리셋 | 키워드·분류 기준·시간·검색엔진 설정을 Google Sheets에 저장/불러오기 |
| 피드백 | 분류 결과를 앱 내에서 직접 수정 → Google Sheets에 저장 → 다음 실행부터 AI에 반영 |
| 다국어 | 한국어 / 일본어 전환 지원 |

---

## 처리 흐름

```
사용자 입력
(키워드 · 분류 기준 · 시간 범위 · 검색엔진)
    │
    ▼
STEP 1. 기사 수집
    네이버 API + 다음 스크래핑 → 전체 합산
    → URL 중복 제거 (동일 기사는 키워드 병합)
    → 검색엔진별 · 시간 오름차순 정렬
    │
    ▼
STEP 2. AI 분류 (GPT-4o-mini)
    이전 피드백을 few-shot 예시로 포함
    기사별 분류 결과:
      · 사용자 정의 카테고리 중 하나 (확신할 수 있는 경우)
      · 보류 — 애매하거나 판단이 어려운 기사
      · 해당없음 — 어떤 기준에도 명백히 해당하지 않는 기사
    │
    ▼
STEP 3. 엑셀 생성
    시트 구성:
      1. 일람       (수집된 모든 기사)
      2. 카테고리별 (사용자 정의 분류)
      3. 보류       (애매한 기사)
      4. 해당없음   (무관련 기사)
    │
    ▼
결과 표시 & 피드백
    앱 내 탭에서 분류결과 수정
    → Google Sheets에 저장
    → 다음 실행 시 AI 분류에 반영
```

---

## 피드백 루프

AI의 분류 정확도는 사용 할수록 향상됩니다.

```
모니터링 실행
    │
    ▼
결과 확인 (앱 내 분류 탭)
    │
    ▼
잘못 분류된 기사 → 분류결과 셀에서 올바른 시트로 수정
    │
    ▼
[피드백 저장] 버튼 클릭
    │
    ▼
Google Sheets '피드백' 시트에 저장
    │
    ▼
다음 실행 시 GPT 프롬프트에 few-shot 예시로 포함 → 정확도 향상
```

---

## 프리셋

자주 사용하는 검색 조건을 프리셋으로 저장해두면 매번 입력할 필요가 없습니다.

**저장 항목:** 키워드 · 분류 기준 (시트명 + 조건) · 시작/종료 시간 · 검색엔진 선택

프리셋 데이터는 Google Sheets의 `프리셋` 시트에 저장됩니다.

---

## 모듈 구성

```
search-assistant/
├── app.py                  # Streamlit UI 및 전체 흐름 조율
└── modules/
    ├── i18n.py             # 한국어/일본어 문자열 사전
    ├── naver_search.py     # 네이버 검색 API 연동
    ├── daum_search.py      # 다음 뉴스 HTML 스크래핑
    ├── classifier.py       # GPT-4o-mini 기사 분류
    ├── excel_writer.py     # openpyxl 엑셀 파일 생성
    ├── sheets.py           # Google Sheets 프리셋/피드백 관리
    └── file_parser.py      # .docx 파일에서 키워드/분류 기준 추출 (GPT)
```

---

## 설치 및 실행

```bash
pip install -r requirements.txt
streamlit run app.py
```

### 필요한 Secrets

Streamlit Cloud의 Secrets 또는 로컬의 `.streamlit/secrets.toml`에 설정합니다.

```toml
OPENAI_API_KEY      = "sk-..."
NAVER_CLIENT_ID     = "..."
NAVER_CLIENT_SECRET = "..."
GOOGLE_SHEET_ID     = "..."
APP_PASSWORD        = "..."   # 선택사항

[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "..."
client_email = "..."
# ... (Google 서비스 계정 JSON 필드)
```

---

## 기술 스택

| 구분 | 사용 기술 |
|------|-----------|
| UI 프레임워크 | Streamlit |
| AI 분류 | OpenAI GPT-4o-mini |
| 뉴스 수집 | Naver Search API, BeautifulSoup (Daum) |
| 엑셀 출력 | openpyxl |
| 프리셋/피드백 저장 | Google Sheets (gspread) |
| 데이터 처리 | pandas |
