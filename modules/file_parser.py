from __future__ import annotations

from docx import Document
from openai import OpenAI
import json
import io


def parse_input_file(file: io.BytesIO, client: OpenAI) -> dict:
    """
    .docx 파일을 GPT로 해석하여 키워드와 분류 기준을 추출합니다.

    반환값:
    {
        "keywords": ["삼성전자", "이재용"],
        "categories": {
            "일람": "키워드가 포함된 기사 전부",
            "단순언급": "...",
            ...
        },
        "all_inclusive_category": "일람"  # 모든 기사가 들어가는 카테고리명
    }
    """
    doc = Document(file)
    text = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])

    if not text.strip():
        raise ValueError("파일 내용이 비어 있습니다.")

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You are a document parser that extracts keywords and classification categories from Korean documents. Always respond in valid JSON only."
            },
            {
                "role": "user",
                "content": f"""아래 문서에서 뉴스 모니터링용 키워드 목록과 분류 기준을 추출해주세요.

문서 내용:
{text}

다음 JSON 형식으로만 응답해주세요:
{{
    "keywords": ["키워드1", "키워드2"],
    "categories": {{
        "카테고리명1": "분류 기준 설명",
        "카테고리명2": "분류 기준 설명"
    }},
    "all_inclusive_category": "모든 기사를 포함하는 카테고리명 (없으면 null)"
}}

주의사항:
- keywords는 검색에 사용할 키워드 배열
- categories의 순서는 문서에 나온 순서 그대로
- 카테고리명은 원문 그대로 사용 (번역하지 말 것)
- all_inclusive_category는 '키워드가 포함된 기사 전부' 같은 조건의 카테고리명 (예: 일람)"""
            }
        ],
        response_format={"type": "json_object"}
    )

    result = json.loads(response.choices[0].message.content)

    # all_inclusive_category가 없으면 첫 번째 카테고리를 사용
    if not result.get("all_inclusive_category"):
        category_names = list(result.get("categories", {}).keys())
        result["all_inclusive_category"] = category_names[0] if category_names else None

    return result
