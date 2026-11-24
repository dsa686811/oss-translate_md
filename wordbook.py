"""학습 결과를 JSON 파일에 저장하고 다시 읽는 함수들."""

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from threading import RLock
from uuid import uuid4


# 실행한 터미널의 위치와 관계없이 프로젝트의 data 폴더에 저장한다.
WORDBOOK_PATH = Path(__file__).resolve().parent / "data" / "wordbook.json"
_file_lock = RLock()


class WordbookError(Exception):
    """기존 단어장 파일을 안전하게 읽을 수 없을 때 발생하는 오류."""


def _validate_study(study):
    if not isinstance(study, dict):
        raise ValueError("저장할 학습 결과가 없어요.")
    for field in ("word", "reading", "meaning"):
        if not isinstance(study.get(field), str) or not study[field].strip():
            raise ValueError("단어, 읽기, 뜻이 있는 학습 결과만 저장할 수 있어요.")
    for field in ("kanji", "word_examples"):
        if not isinstance(study.get(field), list):
            raise ValueError("학습 결과의 형식을 확인해 주세요.")


def load_entries():
    """파일이 아직 없으면 빈 목록, 있으면 저장한 항목들을 돌려준다."""
    with _file_lock:
        if not WORDBOOK_PATH.exists():
            return []

        try:
            entries = json.loads(WORDBOOK_PATH.read_text(encoding="utf-8"))
            if not isinstance(entries, list):
                raise ValueError("단어장은 목록이어야 합니다.")
            entry_ids = set()
            for entry in entries:
                if not isinstance(entry, dict):
                    raise ValueError("항목의 형식이 올바르지 않습니다.")
                entry_id = entry.get("id")
                if not isinstance(entry_id, str) or not entry_id or entry_id in entry_ids:
                    raise ValueError("항목의 식별 번호를 확인해 주세요.")
                entry_ids.add(entry_id)
                _validate_study(entry.get("study"))
        except (ValueError, TypeError) as error:
            # 손상된 파일을 빈 단어장으로 취급하면 다음 저장에서 자료가 사라질 수 있다.
            raise WordbookError("단어장 파일을 읽을 수 없어요. 기존 파일은 유지했어요.") from error

        return entries


def _write_entries(entries):
    WORDBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = WORDBOOK_PATH.with_suffix(".json.tmp")
    temporary_path.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    # 새 내용을 모두 쓴 뒤 교체하여 저장 도중 기존 파일이 비는 일을 줄인다.
    temporary_path.replace(WORDBOOK_PATH)


def save_word(study):
    """학습 결과를 저장하고 (전체 목록, 항목 ID, 새로 저장했는지)를 반환한다."""
    _validate_study(study)
    snapshot = deepcopy(study)
    for field in ("word", "reading", "meaning"):
        snapshot[field] = snapshot[field].strip()

    with _file_lock:
        entries = load_entries()
        identity = tuple(snapshot[field] for field in ("word", "reading", "meaning"))
        for entry in entries:
            saved_identity = tuple(
                entry["study"][field].strip() for field in ("word", "reading", "meaning")
            )
            if identity == saved_identity:
                return entries, entry["id"], False

        entry_id = uuid4().hex
        entries.append({
            "id": entry_id,
            "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "study": snapshot,
        })
        _write_entries(entries)
        return entries, entry_id, True


def delete_word(entry_id):
    """선택한 ID의 항목만 삭제하고 (남은 목록, 삭제했는지)를 반환한다."""
    with _file_lock:
        entries = load_entries()
        remaining = [entry for entry in entries if entry["id"] != entry_id]
        removed = len(remaining) != len(entries)
        if removed:
            _write_entries(remaining)
        return remaining, removed
