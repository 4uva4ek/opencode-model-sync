from opencode_model_sync import i18n


def test_detect_picks_first_supported_language():
    assert i18n.detect(["de-DE", "ru-RU", "en-US"]) == "ru"
    assert i18n.detect(["en_GB"]) == "en"
    assert i18n.detect(["fr-FR"]) == "en"


def test_both_languages_define_the_same_keys():
    assert set(i18n._TEXT["en"]) == set(i18n._TEXT["ru"])


def test_tr_formats_and_switches_language():
    i18n.set_language("ru")
    assert i18n.tr("banner.noNew", provider="Ollama") == "Ollama: нет новых моделей или возможностей для синхронизации."
    i18n.set_language("en")
    assert i18n.tr("banner.noNew", provider="Ollama") == "Ollama: no new models or missing capabilities to sync."
