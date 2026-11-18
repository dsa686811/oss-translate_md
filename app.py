import gradio as gr
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client()


def study_word(text):
    if not text.strip():
        return "단어를 입력해 주세요."

    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=(
            "너는 한국인을 위한 일본어 학습 도우미야. "
            "다음 입력에 해당하는 일본어 단어, 히라가나 읽기, "
            "한국어 뜻을 간단히 알려줘.\n"
            f"입력: {text}"
        ),
    )
    return response.text


app = gr.Interface(
    fn=study_word,
    inputs=gr.Textbox(label="단어 입력", placeholder="예: 学校 또는 학교"),
    outputs=gr.Textbox(label="학습 결과"),
    title="마나비칸지",
    description="일본어 또는 한국어 단어를 입력해 보세요.",
    submit_btn="확인",
    clear_btn="지우기",
)

app.launch()