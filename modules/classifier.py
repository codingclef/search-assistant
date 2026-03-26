from __future__ import annotations

import json
import time as time_module
from typing import Callable
from openai import OpenAI


UNCLASSIFIED = "보류"
UNCATEGORIZED = "해당없음"


def classify_articles(
    articles: list[dict],
    categories: dict,
    client: OpenAI,
    progress_callback: Callable[[int, int], None] | None = None,
    feedback_examples: list[dict] | None = None,
) -> list[dict]:
    """
    GPT-4o-mini로 각 기사를 분류합니다.

    분류 규칙:
    - 정의된 카테고리 중 가장 적합한 1개 부여
    - 어디에도 명확히 해당하지 않으면 '보류'로 처리
    - '일람' 시트는 별도 시스템 기본 시트이므로 여기서는 다루지 않음
    """
    if not articles:
        return []

    classifiable = list(categories.keys())
    valid_special = [UNCLASSIFIED, UNCATEGORIZED]

    # 분류 기준 텍스트
    categories_desc = "\n".join(
        f"- {name}: {desc}" for name, desc in categories.items()
    )

    # 피드백 예시 텍스트 (루프 바깥에서 한 번만 생성)
    examples_block = ""
    if feedback_examples:
        lines = ["[참고 분류 예시 - 이전 피드백 기반]"]
        for ex in feedback_examples[:20]:
            lines.append(f'- 제목: "{ex["title"]}" → {ex["category"]}')
        examples_block = "\n".join(lines) + "\n\n"

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
                            "해당 카테고리에 완전히 확신할 수 없거나 "
                            "조금이라도 판단이 애매한 경우에는 반드시 '보류'를 선택하세요. "
                            "확실한 경우에만 카테고리를 지정하세요."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"""다음 뉴스 기사를 분류해주세요.

검색 키워드: {article['keyword']}
기사 제목: {article['title']}
기사 내용 요약: {article['description']}

{examples_block}분류 기준:
{categories_desc}

선택 가능한 카테고리: {', '.join(classifiable)}, 보류, 해당없음

반드시 아래 JSON 형식으로만 응답하세요:
{{
    "category": "카테고리명",
    "reason": "분류 이유를 1~2문장으로 설명"
}}

- category는 위 목록 중 하나 또는 '보류' 또는 '해당없음'이어야 합니다.
- 카테고리에 완전히 확신하는 경우에만 해당 카테고리를 선택하세요.
- 조금이라도 판단이 애매하거나 확신하기 어려우면 반드시 '보류'로 응답하세요.
- 어떤 카테고리에도 해당하지 않고 애매하지도 않은 명백한 무관련 기사는 '해당없음'으로 응답하세요.""",
                    },
                ],
                response_format={"type": "json_object"},
                timeout=30,
            )

            result = json.loads(response.choices[0].message.content)
            chosen = result.get("category", "")

            # 유효한 카테고리인지 검증
            if chosen not in classifiable and chosen not in valid_special:
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
