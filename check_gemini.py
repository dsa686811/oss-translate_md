from dotenv import load_dotenv
from google import genai

# .env의 API 키를 환경변수로 불러오기
load_dotenv()

# GEMINI_API_KEY 환경변수를 사용해 연결 준비
client = genai.Client()

# Gemini에 질문 보내기
response = client.models.generate_content(
    model="gemini-3.5-flash-lite",
    contents="일본어 단어 学校의 읽기와 한국어 뜻을 간단히 알려줘.",
)

# 받은 답변을 터미널에 표시
print(response.text)