from app.i18n import normalize_language, parse_accept_language, translate


def test_normalize_language_defaults_to_en():
    assert normalize_language(None) == "en"
    assert normalize_language("fr-FR") == "en"


def test_normalize_language_supports_chinese_aliases():
    assert normalize_language("zh") == "zh-CN"
    assert normalize_language("zh-CN") == "zh-CN"


def test_parse_accept_language_prefers_first_supported():
    assert parse_accept_language("de-DE,en;q=0.8") == "de"
    assert parse_accept_language("zh-CN,en;q=0.9") == "zh-CN"


def test_translate_returns_localized_message():
    assert "Bitte" in translate("errors.unauthorized", "de")
    assert "Please" in translate("errors.unauthorized", "en")
    assert "登录" in translate("errors.unauthorized", "zh-CN")
