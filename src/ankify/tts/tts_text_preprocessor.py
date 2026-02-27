import re
import unicodedata
from xml.sax.saxutils import escape as xml_escape


def has_vocabulary_separators(text: str) -> bool:
    return "/" in text or ";" in text


def has_cjk(text: str) -> bool:
    cjk_name_markers = (
        "HIRAGANA",
        "KATAKANA",
        "CJK UNIFIED IDEOGRAPH",
        "HANGUL SYLLABLE",
        "HANGUL JAMO",
    )
    for char in text:
        name = unicodedata.name(char, "")
        if any(marker in name for marker in cjk_name_markers):
            return True
    return False


def replace_separators_with_ssml_breaks(
    text: str, mapping: list[tuple[str, str]]
) -> str:
    sentinels: list[tuple[str, str]] = []
    preprocessed = text
    for index, (separator, replacement) in enumerate(mapping):
        sentinel = f"__ankify_sep_{index}__"
        preprocessed = preprocessed.replace(separator, sentinel)
        sentinels.append((sentinel, replacement))

    escaped = xml_escape(preprocessed)
    for sentinel, replacement in sentinels:
        escaped = escaped.replace(sentinel, replacement)

    return escaped


def replace_separators_with_plain_text(text: str) -> str:
    if has_cjk(text):
        return text.replace("/", "、")
    return re.sub(r"\s*/\s*", ", ", text)


def lang_code_from_voice_id(voice_id: str) -> str:
    # Standard: lang-REGION (e.g. "ja-JP-KeitaNeural")
    match = re.match(r"^([a-z]{2,3}-[A-Z]{2})(?:-|$)", voice_id)
    if match:
        return match.group(1)

    # Script subtag: lang-Script-REGION (e.g. "iu-Latn-CA-TaqqiqNeural")
    match = re.match(r"^([a-z]{2,3}-[A-Z][a-z]{3}-[A-Z]{2})(?:-|$)", voice_id)
    if match:
        return match.group(1)

    parts = voice_id.split("-")
    if len(parts) >= 2 and parts[0].isalpha() and parts[1].isalpha():
        return f"{parts[0]}-{parts[1]}"

    return "en-US"
