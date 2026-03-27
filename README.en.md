# 📰 News Monitoring Assistant

[한국어](README.md) | [日本語](README.ja.md) | **[English]**

A web application that collects news from Naver and Daum, automatically classifies articles using GPT AI, and exports the results to Excel.
Built with Streamlit and supports Korean and Japanese UI.

---

## Features

| Feature | Description |
|---------|-------------|
| Article Collection | Naver Search API (up to 1,000 articles per keyword), Daum news scraping (approx. 200–300 articles per keyword) |
| AI Classification | GPT-4o-mini automatically classifies each article according to user-defined criteria |
| Excel Export | Generates a .xlsx file with 4 sheets: Overview, User-defined categories, Pending, and Not Applicable |
| Presets | Save and load keyword, classification criteria, time range, and search engine settings to/from Google Sheets |
| Feedback | Correct classifications directly in the app → saved to Google Sheets → reflected in AI on next run |
| Multilingual | Korean / Japanese UI toggle |

---

## Processing Flow

```
User Input
(Keywords · Classification criteria · Time range · Search engine)
    │
    ▼
STEP 1. Article Collection
    Naver API ───┐
                 ├──▶ Merge all results
    Daum Scraper─┘       │
                         ▼
                  Deduplicate by URL
                  (same article: merge keywords)
                         │
                         ▼
                  Sort by search engine, then datetime ascending
    │
    ▼
STEP 2. AI Classification (GPT-4o-mini)
    Previous feedback included as few-shot examples
    Per-article result:
      ├ One of the user-defined categories (when confident)
      ├ Pending     — ambiguous or hard-to-judge articles
      └ Not Applicable — articles clearly unrelated to any criteria
    │
    ▼
STEP 3. Excel Generation
    Sheet structure:
      1. Overview       (all collected articles)
      2. By Category    (user-defined classifications)
      3. Pending        (ambiguous articles)
      4. Not Applicable (unrelated articles)
    │
    ▼
Results & Feedback
    Correct classifications in the in-app tabs
    → Saved to Google Sheets
    → Reflected in AI classification on next run
```

---

## Feedback Loop

Classification accuracy improves with each use.

```
Run monitoring
    │
    ▼
Review results (classification tabs in app)
    │
    ▼
Misclassified articles → correct the category in the cell
    │
    ▼
Click [Save Feedback] button
    │
    ▼
Saved to Google Sheets "피드백" sheet
    │
    ▼
Included as few-shot examples in GPT prompt on next run → improved accuracy
```

---

## Presets

Save frequently used search conditions as presets to avoid re-entering them each time.

**Saved items:** Keywords · Classification criteria (sheet name + conditions) · Start/end time · Search engine selection

Preset data is stored in the `프리셋` sheet of your Google Sheets.

---

## Module Structure

```
search-assistant/
├── app.py                  # Streamlit UI and overall flow orchestration
└── modules/
    ├── i18n.py             # Korean/Japanese string dictionary
    ├── naver_search.py     # Naver Search API integration
    ├── daum_search.py      # Daum news HTML scraping
    ├── classifier.py       # GPT-4o-mini article classification
    ├── excel_writer.py     # openpyxl Excel file generation
    ├── sheets.py           # Google Sheets preset/feedback management
    └── file_parser.py      # Extract keywords/criteria from .docx files (GPT)
```

---

## Installation & Setup

```bash
pip install -r requirements.txt
streamlit run app.py
```

### Required Secrets

Configure in Streamlit Cloud Secrets or locally in `.streamlit/secrets.toml`.

```toml
OPENAI_API_KEY      = "sk-..."
NAVER_CLIENT_ID     = "..."
NAVER_CLIENT_SECRET = "..."
GOOGLE_SHEET_ID     = "..."
APP_PASSWORD        = "..."   # Optional

[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "..."
client_email = "..."
# ... (Google service account JSON fields)
```

---

## Tech Stack

| Category | Technology |
|----------|------------|
| UI Framework | Streamlit |
| AI Classification | OpenAI GPT-4o-mini |
| News Collection | Naver Search API, BeautifulSoup (Daum) |
| Excel Export | openpyxl |
| Preset/Feedback Storage | Google Sheets (gspread) |
| Data Processing | pandas |
