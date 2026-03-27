# 📰 ニュースモニタリングアシスタント

[한국어](README.md) | **[日本語]** | [English](README.en.md)

NaverとDaumのニュースを収集し、GPT AIが記事を自動分類してExcelに出力するWebアプリケーションです。
Streamlitで動作し、韓国語・日本語のUIに対応しています。

---

## 主な機能

| 機能 | 説明 |
|------|------|
| 記事収集 | Naver検索API（キーワードあたり最大1,000件）、Daumニューススクレイピング（キーワードあたり最大約200〜300件） |
| AI分類 | GPT-4o-miniがユーザー定義の分類基準に従って各記事を自動分類 |
| Excel出力 | 一覧・ユーザー分類シート・保留・該当なしの4種構成の.xlsxファイル生成 |
| プリセット | キーワード・分類基準・時間・検索エンジン設定をGoogle Sheetsに保存/読み込み |
| フィードバック | 分類結果をアプリ内で直接修正 → Google Sheetsに保存 → 次回実行からAIに反映 |
| 多言語 | 韓国語 / 日本語 切り替え対応 |

---

## 処理フロー

```
ユーザー入力
(キーワード・分類基準・時間範囲・検索エンジン)
    │
    ▼
STEP 1. 記事収集
    Naver API ───┐
                 ├──▶ 全件合算
    Daumスクレイピング┘      │
                              ▼
                       URL重複排除
                       (同一記事はキーワード統合)
                              │
                              ▼
                       検索エンジン別・時刻昇順ソート
    │
    ▼
STEP 2. AI分類 (GPT-4o-mini)
    過去のフィードバックをfew-shot例として含める
    記事ごとの分類結果:
      ├ ユーザー定義カテゴリのいずれか (確信できる場合)
      ├ 保留 — 判断が曖昧または困難な記事
      └ 該当なし — どの基準にも明らかに該当しない記事
    │
    ▼
STEP 3. Excel生成
    シート構成:
      1. 一覧       (収集した全記事)
      2. カテゴリ別 (ユーザー定義分類)
      3. 保留       (曖昧な記事)
      4. 該当なし   (無関連記事)
    │
    ▼
結果表示 & フィードバック
    アプリ内タブで分類結果を修正
    → Google Sheetsに保存
    → 次回実行時のAI分類に反映
```

---

## フィードバックループ

AIの分類精度は使用するほど向上します。

```
モニタリング実行
    │
    ▼
結果確認 (アプリ内分類タブ)
    │
    ▼
誤分類された記事 → 分類結果セルで正しいシートに修正
    │
    ▼
[フィードバック保存] ボタンをクリック
    │
    ▼
Google Sheets「피드백」シートに保存
    │
    ▼
次回実行時にGPTプロンプトへfew-shot例として含める → 精度向上
```

---

## プリセット

よく使う検索条件をプリセットとして保存しておけば、毎回入力する手間が省けます。

**保存項目:** キーワード・分類基準（シート名+条件）・開始/終了時間・検索エンジン選択

プリセットデータはGoogle Sheetsの`프리셋`シートに保存されます。

---

## モジュール構成

```
search-assistant/
├── app.py                  # Streamlit UI および全体フロー管理
└── modules/
    ├── i18n.py             # 韓国語/日本語文字列辞書
    ├── naver_search.py     # Naver検索API連携
    ├── daum_search.py      # DaumニュースHTMLスクレイピング
    ├── classifier.py       # GPT-4o-mini記事分類
    ├── excel_writer.py     # openpyxl Excelファイル生成
    ├── sheets.py           # Google Sheetsプリセット/フィードバック管理
    └── file_parser.py      # .docxファイルからキーワード/分類基準を抽出 (GPT)
```

---

## インストールと実行

```bash
pip install -r requirements.txt
streamlit run app.py
```

### 必要なSecrets

Streamlit CloudのSecretsまたはローカルの`.streamlit/secrets.toml`に設定します。

```toml
OPENAI_API_KEY      = "sk-..."
NAVER_CLIENT_ID     = "..."
NAVER_CLIENT_SECRET = "..."
GOOGLE_SHEET_ID     = "..."
APP_PASSWORD        = "..."   # オプション

[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "..."
client_email = "..."
# ... (Googleサービスアカウント JSONフィールド)
```

---

## 技術スタック

| 区分 | 使用技術 |
|------|----------|
| UIフレームワーク | Streamlit |
| AI分類 | OpenAI GPT-4o-mini |
| ニュース収集 | Naver Search API, BeautifulSoup (Daum) |
| Excel出力 | openpyxl |
| プリセット/フィードバック保存 | Google Sheets (gspread) |
| データ処理 | pandas |
