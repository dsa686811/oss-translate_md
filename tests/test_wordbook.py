import asyncio
import json
from html import unescape
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
from concurrent.futures import ThreadPoolExecutor
import unittest
from unittest.mock import patch

import wordbook


def sample_study(word="学校", meaning="학교"):
    return {
        "word": word,
        "reading": "がっこう",
        "meaning": meaning,
        "kanji": [{
            "character": "学",
            "korean_label": "배울 학",
            "onyomi": ["がく"],
            "kunyomi": ["まなぶ"],
            "on_examples": [{
                "reading": "がく",
                "word": "学生",
                "word_reading": "がくせい",
                "word_meaning": "학생",
                "sentence": "私は学生です。",
                "sentence_reading": "わたしはがくせいです。",
                "translation": "저는 학생입니다.",
            }],
            "kun_examples": [],
        }],
        "word_examples": [],
    }


class StorageTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "data" / "wordbook.json"
        path_patch = patch.object(wordbook, "WORDBOOK_PATH", self.path)
        path_patch.start()
        self.addCleanup(path_patch.stop)

    def test_missing_file_is_an_empty_wordbook(self):
        self.assertEqual(wordbook.load_entries(), [])
        self.assertFalse(self.path.exists())

    def test_saved_details_survive_a_new_python_process(self):
        study = sample_study()
        wordbook.save_word(study)
        script = (
            "import json, sys; from pathlib import Path; import wordbook; "
            "wordbook.WORDBOOK_PATH = Path(sys.argv[1]); "
            "print(json.dumps(wordbook.load_entries(), ensure_ascii=True))"
        )
        result = subprocess.run(
            [sys.executable, "-c", script, str(self.path)],
            cwd=Path(wordbook.__file__).parent,
            capture_output=True, text=True, check=True,
        )
        entries = json.loads(result.stdout)
        self.assertEqual(entries[0]["study"], study)

    def test_duplicate_is_not_added_but_another_meaning_is(self):
        _, first_id, added = wordbook.save_word(sample_study())
        self.assertTrue(added)
        entries, duplicate_id, added = wordbook.save_word(sample_study())
        self.assertFalse(added)
        self.assertEqual(first_id, duplicate_id)
        self.assertEqual(len(entries), 1)
        entries, _, added = wordbook.save_word(sample_study(meaning="다른 뜻"))
        self.assertTrue(added)
        self.assertEqual(len(entries), 2)

    def test_delete_keeps_the_other_entry_and_ignores_stale_ids(self):
        _, first_id, _ = wordbook.save_word(sample_study())
        _, second_id, _ = wordbook.save_word(sample_study("公園", "공원"))
        entries, removed = wordbook.delete_word(first_id)
        self.assertTrue(removed)
        self.assertEqual([entry["id"] for entry in entries], [second_id])
        entries, removed = wordbook.delete_word(first_id)
        self.assertFalse(removed)
        self.assertEqual([entry["id"] for entry in entries], [second_id])
        wordbook.delete_word(second_id)
        self.assertEqual(wordbook.load_entries(), [])

    def test_invalid_results_are_not_saved(self):
        for result in (None, "검색 안내", {}, {"word": "学校"}):
            with self.assertRaises(ValueError):
                wordbook.save_word(result)
        self.assertFalse(self.path.exists())

    def test_corrupt_file_is_not_overwritten(self):
        self.path.parent.mkdir()
        self.path.write_text("broken JSON", encoding="utf-8")
        with self.assertRaises(wordbook.WordbookError):
            wordbook.save_word(sample_study())
        self.assertEqual(self.path.read_text(encoding="utf-8"), "broken JSON")

    def test_parallel_saves_do_not_lose_entries(self):
        with ThreadPoolExecutor(max_workers=5) as pool:
            list(pool.map(
                lambda number: wordbook.save_word(sample_study(f"単語{number}")),
                range(20),
            ))
        self.assertEqual(len(wordbook.load_entries()), 20)


class AppWordbookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # API 키 파일을 읽거나 Gemini에 접속하지 않고 화면과 연결 함수를 검사한다.
        with patch("dotenv.load_dotenv"), patch("google.genai.Client") as client:
            import app
            cls.ui = app
            cls.client = client.return_value

    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path_patch = patch.object(
            wordbook, "WORDBOOK_PATH", Path(directory.name) / "wordbook.json"
        )
        path_patch.start()
        self.addCleanup(path_patch.stop)

    def test_save_reopen_delete_without_api_calls(self):
        study = sample_study()
        rows, _, message, preview = self.ui.save_current_word(study)
        self.assertEqual(rows, [["学校", "がっこう", "학교"]])
        self.assertIn("저장했어요", message)
        self.assertEqual(preview, study)
        entry_id = wordbook.load_entries()[0]["id"]
        reopened, _ = self.ui.open_saved_word(entry_id)
        self.assertEqual(reopened, study)
        rows, _, message, preview = self.ui.delete_saved_word(entry_id)
        self.assertEqual(rows, [])
        self.assertIn("삭제했어요", message)
        self.assertIsNone(preview)
        self.assertEqual(wordbook.load_entries(), [])
        self.client.models.generate_content.assert_not_called()

    def test_save_before_search_does_not_create_an_entry(self):
        _, _, message, _ = self.ui.save_current_word(None)
        self.assertIn("먼저 단어를 검색", message)
        self.assertEqual(wordbook.load_entries(), [])

    def test_saved_examples_are_rendered_in_the_review(self):
        study = sample_study()
        with self.ui.gr.Blocks() as preview:
            self.ui.show_study(study, title="저장한 단어 복습")
        markdown = "\n".join(
            block.value for block in preview.blocks.values()
            if isinstance(block, self.ui.gr.Markdown)
        )
        visible_text = unescape(re.sub(r"<[^>]+>", "", markdown))
        self.assertIn("私は学生です。", visible_text)
        self.assertIn("저는 학생입니다.", visible_text)
        accordions = [
            block for block in preview.blocks.values()
            if isinstance(block, self.ui.gr.Accordion)
        ]
        self.assertTrue(any(block.label == "음독 대표 예문 보기" for block in accordions))

    def test_view_button_opens_its_word_without_api_calls(self):
        wordbook.save_word(sample_study("公園", "공원"))
        study = sample_study()
        _, entry_id, _ = wordbook.save_word(study)
        selected_id, preview, message = self.ui.open_saved_row(("学校", "がっこう", "학교"))
        self.assertEqual(selected_id, entry_id)
        self.assertEqual(preview, study)
        self.assertEqual(message, "")
        # 드롭다운 없이도 보기 버튼이 선택한 ID로 정확히 삭제할 수 있어야 한다.
        self.ui.delete_saved_word(selected_id)
        remaining = wordbook.load_entries()
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0]["study"]["word"], "公園")
        self.client.models.generate_content.assert_not_called()

    def test_navigation_refreshes_wordbook_and_preserves_search_results(self):
        from gradio.state_holder import SessionState

        study = sample_study()
        wordbook.save_word(study)
        session = SessionState(self.ui.app)
        session[self.ui.result_output._id] = study
        candidates = [{"word": "学校", "reading": "がっこう", "meaning": "학교"}]
        session[self.ui.candidates_state._id] = candidates
        open_function = next(
            fn for fn in self.ui.app.fns.values()
            if fn.fn is self.ui.show_wordbook_page
        )
        back_function = next(
            fn for fn in self.ui.app.fns.values()
            if fn.fn is self.ui.show_search_page
        )

        async def navigate():
            opened = await self.ui.app.process_api(open_function, inputs=[], state=session)
            self.assertFalse(opened["data"][0]["visible"])
            self.assertTrue(opened["data"][1]["visible"])
            self.assertEqual(session[self.ui.wordbook_rows._id], [["学校", "がっこう", "학교"]])
            returned = await self.ui.app.process_api(back_function, inputs=[], state=session)
            self.assertTrue(returned["data"][0]["visible"])
            self.assertFalse(returned["data"][1]["visible"])

        asyncio.run(navigate())
        self.assertEqual(session[self.ui.result_output._id], study)
        self.assertEqual(session[self.ui.candidates_state._id], candidates)
        self.client.models.generate_content.assert_not_called()

    def test_saving_also_returns_feedback_for_the_search_screen(self):
        result = self.ui.save_from_search(sample_study())
        self.assertEqual(len(result), 5)
        self.assertEqual(result[-1], result[2])
        self.assertIn("저장했어요", result[-1])

    def test_custom_font_theme_can_be_compared_during_launch(self):
        from gradio import utils

        theme = self.ui.create_theme()
        # launch()가 서버 시작 후 실행하는 비교를 그대로 확인한다.
        is_built_in = any(
            theme.to_dict() == built_in.to_dict()
            for built_in in utils.BUILT_IN_THEMES.values()
        )
        self.assertFalse(is_built_in)


if __name__ == "__main__":
    unittest.main()
