import traceback
from html import escape
from pathlib import Path
from urllib.parse import quote
from study_schema import study_schema
import json
import re
import gradio as gr
from dotenv import load_dotenv
from google import genai
from wordbook import delete_word, load_entries, save_word


FONT_DIRECTORY = Path(__file__).resolve().parent / "assets" / "fonts"
gr.set_static_paths(paths=[FONT_DIRECTORY])


def font_url(filename):
    return "/gradio_api/file=" + quote((FONT_DIRECTORY / filename).as_posix(), safe="/:")


# 한글 범위에만 적용하므로 일본어·한자는 기존 글꼴을 사용한다.
FONT_STYLES = f"""
@font-face {{
    font-family: "NanumSquareRoundKorean";
    src: url("{font_url('NanumSquareRoundOTFR.otf')}") format("opentype");
    font-style: normal;
    font-weight: 400;
    font-display: swap;
    unicode-range: U+1100-11FF, U+3130-318F, U+A960-A97F, U+AC00-D7AF, U+D7B0-D7FF;
}}

@font-face {{
    font-family: "NanumSquareRoundKorean";
    src: url("{font_url('NanumSquareRoundOTFB.otf')}") format("opentype");
    font-style: normal;
    font-weight: 700;
    font-display: swap;
    unicode-range: U+1100-11FF, U+3130-318F, U+A960-A97F, U+AC00-D7AF, U+D7B0-D7FF;
}}
"""


def create_theme():
    # 글꼴 객체로 지정하여 Gradio의 기본 테마 비교에서도 오류가 나지 않게 한다.
    return gr.themes.Soft(
        primary_hue="green",
        neutral_hue="slate",
        spacing_size="sm",
        radius_size="lg",
        font=[
            gr.themes.Font("NanumSquareRoundKorean"),
            gr.themes.Font("Malgun Gothic"),
            gr.themes.Font("Meiryo"),
            gr.themes.Font("sans-serif"),
        ],
    ).set(
        body_background_fill="#ffffff",
        body_background_fill_dark="#ffffff",
        block_background_fill="#ffffff",
        block_background_fill_dark="#1a261e",
    )


load_dotenv()
client = genai.Client()

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

def study_word(text):
    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=f"""
너는 한국인을 위한 일본어 학습 도우미야.
선택한 단어와 의미에 맞는 학습 정보를 제공해.

작성 규칙:
- word에는 일본어 단어, reading에는 히라가나 읽기,
  meaning에는 한국어 뜻을 작성해.
- kanji에는 단어에 포함된 서로 다른 한자를 각각 한 번씩 넣어.
- character에는 한자 한 글자를 넣어.
- korean_label에는 '바를 정', '배울 학' 같은 한국식 훈음을 넣어.
- 한국식 훈음을 확실히 알 수 없으면 '확인 필요'라고 작성해.
- onyomi와 kunyomi에는 대표적인 음독과 훈독을 모두 히라가나로 넣어.
- 일반적으로 쓰이는 읽기가 없으면 해당 목록을 비워 둬.
- on_examples에는 대표 음독 하나를 사용하는 예문 1개를 넣어.
- kun_examples에는 대표 훈독 하나를 사용하는 예문 1개를 넣어.
- 일반적인 용례가 없으면 해당 예문 목록을 비워 둬.

예문 작성 규칙:
- reading에는 예시에서 사용하는 해당 한자의 읽기를 넣어.
- word에는 해당 한자와 읽기가 실제로 사용되는 예시 단어를 넣어.
- word_reading에는 예시 단어 전체의 히라가나 읽기를 넣어.
- word_meaning에는 예시 단어의 한국어 뜻을 넣어.
- sentence에는 짧고 자연스러운 일본어 예문을 넣어.
- sentence_reading에는 예문 전체의 히라가나 읽기를 넣어.
- translation에는 예문의 한국어 뜻을 넣어.
- 한글 발음 표기와 불필요한 설명은 넣지 마.

한자가 없는 단어:
- kanji 목록은 비워 둬.
- word_examples에 입력 단어의 대표 예문 2개를 넣어.
- 이 경우 각 예문의 reading에는 입력 단어의 읽기를 넣어.
- 한자가 있는 단어는 word_examples 목록을 비워 둬.

선택한 학습 대상:
{text}
""",
        config={
            "response_mime_type": "application/json",
            "response_json_schema": study_schema,
        },
    )

    # JSON 글자를 Python 데이터로 변환
    data = json.loads(response.text)

    # 구조화된 데이터를 화면 구성 코드에 전달
    return data

def explain_candidate(candidate):
    # 단어뿐 아니라 선택한 뜻도 함께 전달
    return study_word(
        f"일본어 단어: {candidate['word']}\n"
        f"읽기: {candidate['reading']}\n"
        f"선택한 한국어 뜻: {candidate['meaning']}\n"
        "이 단어와 뜻으로 학습 정보를 설명해. 후보를 다시 묻지 마."
    )


def search_candidates(text):
    # 새 검색을 할 때 이전 후보 선택을 초기화
    empty_dropdown = gr.Dropdown(
        choices=[], value=None, visible=False
    )

    if not text.strip():
        return [], empty_dropdown, "단어를 입력해 주세요."

    try:
        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=f"""
한국인을 위한 일본어 단어 검색이야.
입력에 해당하는 일본어 단어 후보를 찾아줘.

규칙:
- 일본어, 한국어 뜻, 한국어로 적은 일본어 발음을 처리해.
- 명확한 단어는 후보 1개만 반환해.
- 모호한 입력은 흔히 쓰이는 서로 다른 의미의 후보를 최대 5개 반환해.
- reading은 히라가나, meaning은 짧은 한국어 뜻으로 작성해.
- 관계없는 후보를 억지로 채우지 마.
- 해석할 수 없는 입력은 빈 후보 목록을 반환해.

입력: {text}
""",
            config={
                "response_mime_type": "application/json",
                "response_json_schema": candidate_schema,
            },
        )

        candidates = json.loads(response.text)["candidates"]

        if not candidates:
            return [], empty_dropdown, "단어를 찾지 못했어요. 다시 입력해 주세요."

        if len(candidates) == 1:
            result = explain_candidate(candidates[0])
            return [], empty_dropdown, result

        choices = []
        for index, candidate in enumerate(candidates):
            label = (
                f"{candidate['word']} "
                f"({candidate['reading']}) — {candidate['meaning']}"
            )
            choices.append((label, str(index)))

        dropdown = gr.Dropdown(
            choices=choices,
            value=None,
            visible=True,
        )
        return candidates, dropdown, "아래 후보에서 원하는 뜻을 선택해 주세요."

    except Exception:
        traceback.print_exc()
        return [], empty_dropdown, "일본어가 아닌 것 같아요 다시한번 입력부탁드려요!."


def select_candidate(selected, candidates):
    if selected is None:
        return "후보를 먼저 선택해 주세요."

    index = int(selected)
    if index < 0 or index >= len(candidates):
        return "후보를 다시 검색해 주세요."

    try:
        return explain_candidate(candidates[index])
    except Exception:
        traceback.print_exc()
        return "상세 정보를 가져오지 못했어요. 터미널을 확인해 주세요."


def wordbook_view(entries, selected_id=None):
    """목록에 표시할 단어들과 선택한 항목 ID를 반환한다."""
    rows = [
        [entry["study"]["word"], entry["study"]["reading"], entry["study"]["meaning"]]
        for entry in entries
    ]
    return rows, selected_id


def refresh_wordbook():
    try:
        entries = load_entries()
        return *wordbook_view(entries), f"저장한 단어 {len(entries)}개", None
    except Exception:
        traceback.print_exc()
        return [], None, "단어장을 불러오지 못했어요. 터미널을 확인해 주세요.", None


def show_wordbook_page():
    """검색 화면을 숨기고 최신 단어장 목록을 보여준다."""
    return gr.update(visible=False), gr.update(visible=True), *refresh_wordbook()


def show_search_page():
    """검색 데이터는 바꾸지 않고 검색 화면으로 돌아간다."""
    return gr.update(visible=True), gr.update(visible=False)


def save_current_word(data):
    # 검색 안내나 오류 메시지는 학습 결과가 아니므로 저장하지 않는다.
    if not isinstance(data, dict):
        return gr.skip(), gr.skip(), "먼저 단어를 검색하고 학습 결과를 확인해 주세요.", gr.skip()
    try:
        entries, entry_id, added = save_word(data)
        message = "단어장에 저장했어요." if added else "이미 같은 단어·읽기·뜻이 저장되어 있어요."
        return *wordbook_view(entries, entry_id), message, data
    except Exception:
        traceback.print_exc()
        return gr.skip(), gr.skip(), "저장하지 못했어요. 터미널을 확인해 주세요.", gr.skip()


def save_from_search(data):
    """단어장을 갱신하고 검색 화면에도 저장 결과를 알려준다."""
    result = save_current_word(data)
    return *result, result[2]


def open_saved_word(entry_id):
    try:
        entry = next((item for item in load_entries() if item["id"] == entry_id), None)
        if entry is None:
            return None, "저장한 단어를 선택해 주세요. 목록에 없다면 새로고침해 주세요."
        # 저장한 결과를 재사용하므로 Gemini를 다시 호출하지 않는다.
        return entry["study"], ""
    except Exception:
        traceback.print_exc()
        return None, "단어를 불러오지 못했어요. 터미널을 확인해 주세요."


def open_saved_row(identity):
    """각 단어 오른쪽의 보기 버튼으로 해당 항목을 연다."""
    try:
        entries = load_entries()
        for entry in entries:
            study = entry["study"]
            if identity == (study["word"], study["reading"], study["meaning"]):
                return (
                    entry["id"],
                    study,
                    "",
                )
        return None, None, "목록이 변경됐어요. 단어장 목록을 새로고침해 주세요."
    except Exception:
        traceback.print_exc()
        return None, None, "단어를 불러오지 못했어요. 터미널을 확인해 주세요."


def delete_saved_word(entry_id):
    if entry_id is None:
        return gr.skip(), gr.skip(), "삭제할 단어를 먼저 선택해 주세요.", gr.skip()
    try:
        entries, removed = delete_word(entry_id)
        message = "선택한 단어를 삭제했어요." if removed else "이미 삭제된 항목이에요. 목록을 갱신했어요."
        return *wordbook_view(entries), message, None
    except Exception:
        traceback.print_exc()
        return gr.skip(), gr.skip(), "삭제하지 못했어요. 터미널을 확인해 주세요.", gr.skip()


KANJI_PATTERN = re.compile(
    r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0002fa1f々〇]+"
)


def format_japanese(text):
    """日本語 중 한자 부분에만 크기 조절용 표시를 붙인다. 원본 데이터는 유지한다."""
    return KANJI_PATTERN.sub(
        r'<span class="kanji-text">\g<0></span>',
        escape(text),
    )


def format_reading(text):
    """음독·훈독의 일본어 읽기만 조금 크게 표시한다."""
    return f'<span class="reading-text">{escape(text)}</span>'


def show_examples(examples):
    if not examples:
        gr.Markdown("일반적으로 쓰이는 대표 용례가 없어요.")
        return

    for example in examples:
        gr.Markdown(
            f"**사용한 읽기:** {format_reading(example['reading'])}\n\n"
            f"**예시 단어:** {format_japanese(example['word'])} "
            f"（{example['word_reading']}）"
            f" — {example['word_meaning']}\n\n"
            f"**예문:** {format_japanese(example['sentence'])}\n\n"
            f"**읽기:** {example['sentence_reading']}\n\n"
            f"**뜻:** {example['translation']}"
        )


def show_study(data, title="학습 결과"):
    """검색 결과와 저장한 결과를 같은 형식으로 화면에 표시한다."""
    if data is None:
        gr.Markdown(
            "단어를 검색하면 학습 정보가 여기에 표시돼요.",
            elem_classes="page-text",
        )
        return
    if isinstance(data, str):
        gr.Markdown(data, elem_classes="page-text")
        return

    gr.Markdown(f"## {title}", elem_classes="page-text")
    gr.Markdown(
        f"### {format_japanese(data['word'])}（{data['reading']}）\n\n"
        f"**한국어 뜻:** {data['meaning']}",
        elem_classes="page-text",
    )

    for kanji in data["kanji"]:
        with gr.Group():
            gr.Markdown(f"### {format_japanese(kanji['character'])} — {kanji['korean_label']}")
            on_readings = "、".join(kanji["onyomi"])
            kun_readings = "、".join(kanji["kunyomi"])
            gr.Markdown(
                f"**음독:** {format_reading(on_readings) if on_readings else '일반적인 읽기 없음'}\n\n"
                f"**훈독:** {format_reading(kun_readings) if kun_readings else '일반적인 읽기 없음'}"
            )
            with gr.Accordion("음독 대표 예문 보기", open=False):
                show_examples(kanji["on_examples"])
            with gr.Accordion("훈독 대표 예문 보기", open=False):
                show_examples(kanji["kun_examples"])

    if data["word_examples"]:
        with gr.Accordion("단어 대표 예문 보기", open=False):
            show_examples(data["word_examples"])


with gr.Blocks(fill_width=True) as app:
    gr.Markdown("# 마나비칸지", elem_id="app-title")

    candidates_state = gr.State([])
    result_output = gr.State(None)
    saved_result = gr.State(None)
    wordbook_rows = gr.State([])
    selected_word_id = gr.State(None)

    # 화면 전환은 부모 영역만 숨기거나 표시하므로 검색 결과가 유지된다.
    with gr.Column(elem_id="search-page") as search_page:
        open_wordbook_button = gr.Button(
            "내 단어장 보기", size="sm", elem_classes="page-nav-button",
        )
        gr.Markdown(
            "일본어·한국어 단어 또는 일본어 발음을 입력해 보세요.",
            elem_classes="page-text",
        )
        word_input = gr.Textbox(
            label="단어 입력",
            placeholder="예: 学校, 학교, 코우엔",
            elem_id="word-input",
        )
        search_button = gr.Button(
            "검색", variant="primary", elem_id="search-button",
        )
        candidate_dropdown = gr.Dropdown(
            label="원하는 뜻 선택",
            choices=[], value=None, visible=False, interactive=True,
        )

        @gr.render(inputs=[result_output])
        def render_result(data):
            show_study(data)

        save_button = gr.Button("단어장에 저장하기", variant="primary")
        search_save_status = gr.Markdown("", elem_classes="page-text")

    with gr.Column(visible=False, elem_id="wordbook-page") as wordbook_page:
        back_to_search_button = gr.Button(
            "검색으로 돌아가기", size="sm", elem_classes="page-nav-button",
        )
        gr.Markdown("## 내 단어장", elem_classes="page-text")
        wordbook_status = gr.Markdown("", elem_classes="page-text")

        with gr.Row(elem_id="wordbook-layout"):
            with gr.Column(
                scale=2, min_width=0, elem_id="wordbook-list-panel",
                elem_classes="wordbook-panel",
            ):
                gr.Markdown("### 저장한 단어")
                with gr.Column(elem_id="wordbook-list-scroll", min_width=0):
                    @gr.render(inputs=[wordbook_rows])
                    def render_saved_words(rows):
                        if not rows:
                            gr.Markdown("아직 저장한 단어가 없어요.")
                            return

                        for word, reading, meaning in rows:
                            with gr.Row(elem_classes="saved-word-row"):
                                with gr.Column(scale=1, min_width=0):
                                    gr.Markdown(f"**{word}**（{reading}）\n\n{meaning}")
                                view_button = gr.Button(
                                    "보기", scale=0, min_width=70,
                                    elem_classes="saved-word-view",
                                )

                            def view_word(identity=(word, reading, meaning)):
                                return open_saved_row(identity)

                            view_button.click(
                                fn=view_word, inputs=[],
                                outputs=[selected_word_id, saved_result, wordbook_status],
                                js="""() => {
                                    const root = document.querySelector('gradio-app')?.shadowRoot || document;
                                    root.querySelector('#wordbook-detail-scroll')?.scrollTo(0, 0);
                                    return [];
                                }""",
                            )

                refresh_button = gr.Button("새로고침")

            with gr.Column(
                scale=3, min_width=0, elem_id="wordbook-detail-panel",
                elem_classes="wordbook-panel",
            ):
                with gr.Column(elem_id="wordbook-detail-scroll", min_width=0):
                    @gr.render(inputs=[saved_result])
                    def render_saved_result(data):
                        if data is None:
                            gr.Markdown("### 단어 복습하기")
                            gr.Markdown("복습할 단어의 ‘보기’를 눌러 주세요.")
                            return
                        show_study(data, title="단어 복습하기")

                delete_button = gr.Button("삭제하기", variant="stop")

    wordbook_outputs = [wordbook_rows, selected_word_id, wordbook_status, saved_result]
    app.load(fn=refresh_wordbook, inputs=[], outputs=wordbook_outputs)

    open_wordbook_button.click(
        fn=show_wordbook_page, inputs=[],
        outputs=[search_page, wordbook_page, *wordbook_outputs],
    )
    back_to_search_button.click(
        fn=show_search_page, inputs=[], outputs=[search_page, wordbook_page],
    )
    search_button.click(
        fn=search_candidates, inputs=[word_input],
        outputs=[candidates_state, candidate_dropdown, result_output],
    ).then(fn=lambda: "", inputs=[], outputs=[search_save_status])
    candidate_dropdown.input(
        fn=select_candidate, inputs=[candidate_dropdown, candidates_state],
        outputs=[result_output],
    ).then(fn=lambda: "", inputs=[], outputs=[search_save_status])
    save_button.click(
        fn=save_from_search, inputs=[result_output],
        outputs=[*wordbook_outputs, search_save_status],
    )
    refresh_button.click(fn=refresh_wordbook, inputs=[], outputs=wordbook_outputs)
    delete_button.click(
        fn=delete_saved_word, inputs=[selected_word_id], outputs=wordbook_outputs,
    )


if __name__ == "__main__":
    app.launch(
        share=True,
        theme=create_theme(),
        css=FONT_STYLES + """
        .gradio-container {
            --study-font-increase: 2pt;
            --manabi-green: #63CC63;
            background-color: var(--body-background-fill);
            max-width: 1200px !important;
            margin: 0 auto !important;
            padding: 32px 20px 48px !important;
        }

        #app-title,
        .page-text {
            --body-text-color: #000000;
        }

        #app-title,
        #search-page {
            width: 100% !important;
            max-width: 820px !important;
            margin-left: auto !important;
            margin-right: auto !important;
        }

.gradio-container {
    width: 100% !important;
    box-sizing: border-box;
}

.gradio-container .main.app {
    padding-inline: 0 !important;
}

#wordbook-page {
    width: 100% !important;
}

        #wordbook-layout {
            flex-wrap: nowrap !important;
            align-items: stretch !important;
            gap: 20px !important;
        }

        .wordbook-panel {
            --body-text-color: #000800;
            --body-text-color-subdued: var(--body-text-color);
            --accordion-text-color: var(--body-text-color);
            --block-background-fill: #d9f3d9;
            --border-color-primary: #3b923b;
            min-width: 0 !important;
            height: calc(100dvh - 260px);
            min-height: 360px;
            overflow: hidden;
            padding: 16px !important;
            border: 1px solid var(--border-color-primary);
            border-radius: 16px;
            background: var(--manabi-green);
        }

        .wordbook-panel > * {
            flex-shrink: 0;
        }

        #wordbook-list-scroll,
        #wordbook-detail-scroll {
            flex: 1 1 0 !important;
            min-height: 0 !important;
            min-width: 0 !important;
            overflow-y: auto !important;
            overflow-x: hidden !important;
            overscroll-behavior: contain;
            scrollbar-gutter: stable;
            padding-right: 8px;
        }

        #wordbook-list-scroll > *,
        #wordbook-detail-scroll > * {
            flex-shrink: 0;
        }

        .gradio-container .prose h1 {
            font-size: 28px !important;
            letter-spacing: -0.04em;
        }

        .gradio-container .prose h2 {
            font-size: 21px !important;
        }

        .gradio-container .prose h3 {
            font-size: 19px !important;
        }

        .gradio-container .prose p {
            margin-top: 6px !important;
            margin-bottom: 6px !important;
            line-height: 1.7;
        }

        .gradio-container .prose h1,
        .gradio-container .prose h2,
        .gradio-container .prose h3,
        .gradio-container button {
            font-weight: 700;
        }

        .gradio-container .kanji-text,
        .gradio-container .reading-text {
            font-size: calc(1em + var(--study-font-increase));
        }

        #word-input {
            --block-background-fill: #288c28;
            --input-background-fill: var(--manabi-green);
            --input-background-fill-focus: var(--manabi-green);
            --input-placeholder-color: #214321;
        }

        #word-input :is(input, textarea) {
            --body-text-color: #142814;
        }

        #search-button {
            min-height: 44px;
            border-radius: 12px;
            font-weight: 700;
        }

        .page-nav-button {
            width: auto !important;
            min-width: 150px !important;
            max-width: 190px !important;
            margin-left: auto !important;
            align-self: flex-end;
        }

        .saved-word-row {
            flex-wrap: nowrap !important;
            align-items: center !important;
            gap: 12px !important;
            padding: 8px 0 !important;
            border-bottom: 1px solid var(--border-color-primary);
        }

        .saved-word-view {
            flex: 0 0 70px !important;
            max-width: 70px !important;
            min-height: 36px !important;
            align-self: center;
            border-radius: 10px;
        }

        @media (max-width: 800px) {
            #wordbook-layout {
                flex-direction: column !important;
            }

            .wordbook-panel {
                width: 100% !important;
                height: auto;
                min-height: 0;
            }

            #wordbook-list-scroll,
            #wordbook-detail-scroll {
                flex: none !important;
            }

            #wordbook-list-scroll {
                max-height: 240px;
            }

            #wordbook-detail-scroll {
                max-height: 65dvh;
            }
        }

        @media (max-width: 600px) {
            .gradio-container {
                padding: 20px 12px 32px !important;
            }
        }
        """,
    )
