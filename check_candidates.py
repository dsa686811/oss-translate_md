import json
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client()

# AI가 답변할 데이터의 구조
candidate_schema = {
    "type": "object",
    "properties": {
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "word": {"type": "string"},
                    "reading": {"type": "string"},
                    "meaning": {"type": "string"},
                },
                "required": ["word", "reading", "meaning"],
            },
        },
    },
    "required": ["candidates"],
}

text = input("검색할 단어: ")

response = client.models.generate_content(
    model="gemini-3.5-flash-lite",
    contents=f"""
한국인을 위한 일본어 단어 검색이야.
입력에 해당하는 일본어 단어 후보를 찾아줘.

규칙:
- 일본어, 한국어 뜻, 한국어로 적은 일본어 발음을 처리해.
- 명확한 단어는 후보 1개만 반환해.
- 모호한 입력은 흔히 쓰이는 서로 다른 의미의 후보를 최대 5개 반환해.
- reading에는 히라가나 읽기를 넣어.
- meaning에는 짧은 한국어 뜻을 넣어.
- 관계없는 후보를 억지로 채우지 마.
- 해석할 수 없는 입력은 빈 후보 목록을 반환해.

입력: {text}
""",
    config={
        "response_mime_type": "application/json",
        "response_json_schema": candidate_schema,
    },
)

# JSON 문자열을 Python에서 사용할 데이터로 변환
data = json.loads(response.text)

for candidate in data["candidates"]:
    print(
        f"{candidate['word']} "
        f"({candidate['reading']}) — "
        f"{candidate['meaning']}"
    )