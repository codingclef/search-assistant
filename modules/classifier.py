from __future__ import annotations

import json
import time as time_module
from typing import Callable
from openai import OpenAI


UNCLASSIFIED = "미분류"


def classify_articles(
    articles: list[dict],
    categories: dict,
    client: OpenAI,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[dict]:
    """
    GPT-4o-mini로 각 기사를 분류합니다.

    분류 규칙:
    - docx에 정의된 카테고리 중 가장 적합한 1개 부여
    - 어디에도 명확히 해당하지 않으면 '미분류'로 처리
    - '일람' 시트는 별도 시스템 기본 시트이므로 여기서는 다루지 않음
    """
    if not articles:
        return []

    classifiable = list(categories.keys())

    # 분류 기준 텍스트
    categories_desc = "\n".join(
        f"- {name}: {desc}" for name, desc in categories.items()
    )

    for i, article in enumerate(articles):
        if progress_callback:
            progress_callback(i, len(articles))

        if not classifiable:
            article["category"] = UNCLASSIFIED
            article["reason"] = ""
            continue

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "당신은 뉴스 기사 분류 전문가입니다. "
                            "기사 제목과 내용을 분석하여 주어진 기준 중 "
                            "가장 적합한 카테고리 하나를 선택하세요. "
                            "어느 기준에도 명확히 해당하지 않으면 '미분류'를 선택하세요."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"""다음 뉴스 기사를 분류해주세요.

검색 키워드: {article['keyword']}
기사 제목: {article['title']}
기사 내용 요약: {article['description']}

분류 기준:
{categories_desc}

선택 가능한 카테고리: {', '.join(classifiable)}, 미분류

반드시 아래 JSON 형식으로만 응답하세요:
{{
    "category": "카테고리명",
    "reason": "분류 이유를 1~2문장으로 설명"
}}

- category는 위 목록 중 하나 또는 '미분류'여야 합니다.
- 어느 기준에도 명확히 해당하지 않거나 판단이 어려우면 반드시 '미분류'로 응답하세요.""",
                    },
                ],
                response_format={"type": "json_object"},
                timeout=30,
            )

            result = json.loads(response.choices[0].message.content)
            chosen = result.get("category", "")

            # 유효한 카테고리인지 검증 (미분류 포함)
            if chosen not in classifiable and chosen != UNCLASSIFIED:
                chosen = UNCLASSIFIED

            article["category"] = chosen
            article["reason"] = result.get("reason", "")

        except Exception:
            article["category"] = UNCLASSIFIED
            article["reason"] = "분류 중 오류 발생"

        time_module.sleep(0.05)

    if progress_callback:
        progress_callback(len(articles), len(articles))

    return articles
