import gradio as gr


def show_input(text):
    return f"입력한 내용: {text}"


app = gr.Interface(
    fn=show_input,
    inputs=gr.Textbox(label="일본어 단어", placeholder="예: 学校"),
    outputs=gr.Textbox(label="결과"),
    title="마나비칸지",
    description="일본어 단어를 입력해 보세요.",
    submit_btn="확인", 
    clear_btn="지우기",
)

app.launch()