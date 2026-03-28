"""
Tests for modules/classifier.py

OpenAI API calls are mocked throughout.
"""
import json
from unittest.mock import MagicMock, call

import pytest

from modules.classifier import classify_articles, UNCLASSIFIED, UNCATEGORIZED


# ── helpers ──────────────────────────────────────────────────────────────────

def _article(title="테스트 기사", category="", reason=""):
    return {
        "keyword": "테스트",
        "title": title,
        "description": "테스트 설명",
        "link": "https://example.com",
        "published_at": None,
        "search_engine": "네이버",
        "source": "테스트신문",
        "category": category,
        "reason": reason,
    }


def _mock_client(category: str, reason: str = "테스트 이유"):
    """OpenAI 클라이언트를 모킹하여 항상 고정된 category를 반환하도록 함."""
    content = json.dumps({"category": category, "reason": reason})
    mock_msg = MagicMock()
    mock_msg.content = content
    mock_choice = MagicMock()
    mock_choice.message = mock_msg
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    client = MagicMock()
    client.chat.completions.create.return_value = mock_response
    return client


# ── constants ─────────────────────────────────────────────────────────────────

def test_unclassified_constant():
    assert UNCLASSIFIED == "보류"


def test_uncategorized_constant():
    assert UNCATEGORIZED == "해당없음"


# ── empty input ───────────────────────────────────────────────────────────────

def test_empty_articles_returns_empty_list():
    result = classify_articles([], {"카테고리": "조건"}, MagicMock())
    assert result == []


def test_empty_articles_does_not_call_api():
    client = MagicMock()
    classify_articles([], {"카테고리": "조건"}, client)
    client.chat.completions.create.assert_not_called()


# ── valid classification ──────────────────────────────────────────────────────

def test_assigns_valid_user_category():
    articles = [_article()]
    client = _mock_client("부정기사")
    result = classify_articles(articles, {"부정기사": "부정적 기사"}, client)
    assert result[0]["category"] == "부정기사"


def test_assigns_reason_from_gpt():
    articles = [_article()]
    client = _mock_client("중요기사", reason="임원 인터뷰 기사")
    result = classify_articles(articles, {"중요기사": "중요한 기사"}, client)
    assert result[0]["reason"] == "임원 인터뷰 기사"


def test_holdup_is_valid_category():
    articles = [_article()]
    client = _mock_client(UNCLASSIFIED)
    result = classify_articles(articles, {"카테고리": "조건"}, client)
    assert result[0]["category"] == UNCLASSIFIED


def test_uncategorized_is_valid_category():
    articles = [_article()]
    client = _mock_client(UNCATEGORIZED)
    result = classify_articles(articles, {"카테고리": "조건"}, client)
    assert result[0]["category"] == UNCATEGORIZED


def test_multiple_articles_all_classified():
    articles = [_article(f"기사{i}") for i in range(5)]
    client = _mock_client("중요기사")
    result = classify_articles(articles, {"중요기사": "중요한 기사"}, client)
    assert len(result) == 5
    assert all(a["category"] == "중요기사" for a in result)


def test_original_list_is_mutated_in_place():
    articles = [_article()]
    client = _mock_client("카테고리")
    result = classify_articles(articles, {"카테고리": "조건"}, client)
    assert result is articles  # 같은 객체


# ── fallback behavior ─────────────────────────────────────────────────────────

def test_invalid_category_from_gpt_falls_back_to_unclassified():
    articles = [_article()]
    client = _mock_client("존재하지않는카테고리")
    result = classify_articles(articles, {"부정기사": "조건"}, client)
    assert result[0]["category"] == UNCLASSIFIED


def test_api_exception_sets_unclassified():
    articles = [_article()]
    client = MagicMock()
    client.chat.completions.create.side_effect = Exception("API 오류")
    result = classify_articles(articles, {"카테고리": "조건"}, client)
    assert result[0]["category"] == UNCLASSIFIED


def test_api_exception_sets_error_reason():
    articles = [_article()]
    client = MagicMock()
    client.chat.completions.create.side_effect = Exception("timeout")
    result = classify_articles(articles, {"카테고리": "조건"}, client)
    assert result[0]["reason"] != ""


def test_no_categories_skips_api_and_sets_unclassified():
    articles = [_article()]
    client = MagicMock()
    result = classify_articles(articles, {}, client)
    assert result[0]["category"] == UNCLASSIFIED
    client.chat.completions.create.assert_not_called()


# ── progress callback ─────────────────────────────────────────────────────────

def test_progress_callback_called_per_article():
    n = 3
    articles = [_article(f"기사{i}") for i in range(n)]
    client = _mock_client("카테고리")
    calls = []
    classify_articles(
        articles, {"카테고리": "조건"}, client,
        progress_callback=lambda cur, total: calls.append((cur, total)),
    )
    # 각 기사 처리 전(0~n-1) + 완료(n) = n+1회
    assert len(calls) == n + 1
    assert calls[-1] == (n, n)


def test_progress_callback_total_is_correct():
    articles = [_article(), _article()]
    client = _mock_client("카테고리")
    totals = []
    classify_articles(
        articles, {"카테고리": "조건"}, client,
        progress_callback=lambda cur, total: totals.append(total),
    )
    assert all(t == 2 for t in totals)


# ── feedback examples ─────────────────────────────────────────────────────────

def test_feedback_examples_appear_in_prompt():
    articles = [_article()]
    client = _mock_client("카테고리")
    feedback = [
        {"title": "피드백 예시 기사", "category": "중요기사"},
    ]
    classify_articles(articles, {"카테고리": "조건"}, client, feedback_examples=feedback)
    call_args = client.chat.completions.create.call_args
    user_content = call_args.kwargs["messages"][1]["content"]
    assert "피드백 예시 기사" in user_content


def test_feedback_examples_capped_at_20():
    articles = [_article()]
    client = _mock_client("카테고리")
    feedback = [{"title": f"기사{i}", "category": "카테고리"} for i in range(30)]
    classify_articles(articles, {"카테고리": "조건"}, client, feedback_examples=feedback)
    call_args = client.chat.completions.create.call_args
    user_content = call_args.kwargs["messages"][1]["content"]
    # 20번째 피드백은 포함, 21번째는 미포함
    assert "기사19" in user_content
    assert "기사20" not in user_content


def test_no_feedback_examples_no_block_in_prompt():
    articles = [_article()]
    client = _mock_client("카테고리")
    classify_articles(articles, {"카테고리": "조건"}, client, feedback_examples=None)
    call_args = client.chat.completions.create.call_args
    user_content = call_args.kwargs["messages"][1]["content"]
    assert "참고 분류 예시" not in user_content
