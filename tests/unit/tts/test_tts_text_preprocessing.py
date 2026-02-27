from ankify.tts.aws_tts import AWSPollySingleLanguageClient
from ankify.tts.edge_tts import EdgeTTSSingleLanguageClient
from ankify.tts.tts_text_preprocessor import (
    has_cjk,
    has_vocabulary_separators,
    lang_code_from_voice_id,
    replace_separators_with_plain_text,
    replace_separators_with_ssml_breaks,
)


def test_has_vocabulary_separators():
    assert has_vocabulary_separators("because/due to")
    assert has_vocabulary_separators("because; due to")
    assert not has_vocabulary_separators("because due to")


def test_has_cjk_detects_scripts():
    assert has_cjk("から")
    assert has_cjk("因为")
    assert has_cjk("안녕하세요")
    assert not has_cjk("because")
    assert not has_cjk("потом что")


def test_replace_separators_with_ssml_breaks_escapes_xml_and_inserts_breaks():
    text = "5 < 10; a/b & c > d"
    mapping = [
        ("/", "<break time='100ms'/>"),
        (";", "<break time='200ms'/>"),
    ]

    result = replace_separators_with_ssml_breaks(text, mapping)

    assert "&lt;" in result
    assert "&gt;" in result
    assert "&amp;" in result
    assert "<break time='100ms'/>" in result
    assert "<break time='200ms'/>" in result
    assert "a/b" not in result
    assert "10;" not in result


def test_replace_separators_with_plain_text_uses_latin_comma():
    assert replace_separators_with_plain_text("because/due to") == "because, due to"
    assert replace_separators_with_plain_text("because / due to") == "because, due to"
    assert replace_separators_with_plain_text("because /due to") == "because, due to"
    assert replace_separators_with_plain_text("because/ due to") == "because, due to"


def test_replace_separators_with_plain_text_uses_cjk_comma():
    assert replace_separators_with_plain_text("から/ので") == "から、ので"
    assert replace_separators_with_plain_text("から / ので") == "から 、 ので"


def test_replace_separators_with_plain_text_keeps_semicolon():
    assert replace_separators_with_plain_text("から/ので; のために") == "から、ので; のために"


def test_lang_code_from_voice_id():
    assert lang_code_from_voice_id("ja-JP-KeitaNeural") == "ja-JP"
    assert lang_code_from_voice_id("zh-CN-XiaoxiaoNeural") == "zh-CN"
    assert lang_code_from_voice_id("en-US") == "en-US"
    assert lang_code_from_voice_id("invalidvoiceid") == "en-US"
    assert lang_code_from_voice_id("en-US-AndrewNeural") == "en-US"
    assert lang_code_from_voice_id("de-DE-ConradNeural") == "de-DE"
    assert lang_code_from_voice_id("ru-RU-DmitryNeural") == "ru-RU"
    # Script subtag: lang-Script-REGION
    assert lang_code_from_voice_id("iu-Latn-CA-TaqqiqNeural") == "iu-Latn-CA"
    # 3-letter language code
    assert lang_code_from_voice_id("fil-PH-AngeloNeural") == "fil-PH"

def test_aws_uses_shared_ssml_preprocessing():
    result = AWSPollySingleLanguageClient.possibly_preprocess_text_into_ssml("and/or; also")

    assert result["TextType"] == "ssml"
    assert "<speak>" in result["Text"]
    assert "<break time='100ms'/>" in result["Text"]
    assert "<break time='200ms'/>" in result["Text"]


def test_edge_uses_shared_plain_text_preprocessing_for_cjk():
    result = EdgeTTSSingleLanguageClient.possibly_preprocess_text("から/ので; のために")
    assert result == "から、ので; のために"
