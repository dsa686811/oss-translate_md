# 예문 한 개의 양식
example_schema = {
    "type": "object",
    "properties": {
        "reading": {"type": "string"},
        "word": {"type": "string"},
        "word_reading": {"type": "string"},
        "word_meaning": {"type": "string"},
        "sentence": {"type": "string"},
        "sentence_reading": {"type": "string"},
        "translation": {"type": "string"},
    },
    "required": [
        "reading",
        "word",
        "word_reading",
        "word_meaning",
        "sentence",
        "sentence_reading",
        "translation",
    ],
}

# 한자 한 개의 양식
kanji_schema = {
    "type": "object",
    "properties": {
        "character": {"type": "string"},
        "korean_label": {"type": "string"},
        "onyomi": {
            "type": "array",
            "items": {"type": "string"},
        },
        "kunyomi": {
            "type": "array",
            "items": {"type": "string"},
        },
        "on_examples": {
            "type": "array",
            "items": example_schema,
        },
        "kun_examples": {
            "type": "array",
            "items": example_schema,
        },
    },
    "required": [
        "character",
        "korean_label",
        "onyomi",
        "kunyomi",
        "on_examples",
        "kun_examples",
    ],
}

# 상세 학습 결과 전체의 양식
study_schema = {
    "type": "object",
    "properties": {
        "word": {"type": "string"},
        "reading": {"type": "string"},
        "meaning": {"type": "string"},
        "kanji": {
            "type": "array",
            "items": kanji_schema,
        },
        "word_examples": {
            "type": "array",
            "items": example_schema,
        },
    },
    "required": [
        "word",
        "reading",
        "meaning",
        "kanji",
        "word_examples",
    ],
}