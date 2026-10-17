from app.sessions import Segment
from app.settings import Settings, load_settings, save_settings
from app.transcription import models
from app.transcription.postprocess import clean_segments
from app.transcription.transcriber import BASE_PROMPT, build_prompts


def test_parse_vocabulary_dedupes_and_splits():
    text = "Hugo Guedes\nIOB, Kubernetes; okr\n\n iob \nOKR"
    assert Settings.parse_vocabulary(text) == ["Hugo Guedes", "IOB", "Kubernetes", "okr"]


def test_settings_roundtrip(tmp_path):
    path = tmp_path / "settings.json"
    assert load_settings(path) == Settings()
    save_settings(Settings(model="large-v3-turbo", vocabulary=["Ação"]), path)
    assert load_settings(path) == Settings(model="large-v3-turbo", vocabulary=["Ação"])
    path.write_text("{lixo", encoding="utf-8")
    assert load_settings(path) == Settings()


def test_build_prompts():
    assert build_prompts([]) == (BASE_PROMPT, None)
    prompt, hotwords = build_prompts(["IOB", "Joana"])
    assert hotwords == "IOB, Joana"
    assert prompt.startswith(BASE_PROMPT) and "IOB, Joana" in prompt


def test_clean_segments_drops_hallucinations_and_repeats():
    segs = [
        Segment(0, 2, "Vamos começar."),
        Segment(2, 4, "Legendas pela comunidade Amara.org"),
        Segment(4, 6, "O orçamento foi aprovado."),
        Segment(6, 8, "O orçamento foi aprovado"),
        Segment(8, 9, "Obrigado por assistir!"),
        Segment(9, 10, "Tchau, tchau."),
    ]
    assert clean_segments(segs) == [
        Segment(0, 2, "Vamos começar."),
        Segment(4, 8, "O orçamento foi aprovado."),
        Segment(9, 10, "Tchau, tchau."),
    ]


def test_is_downloaded_requires_all_files(tmp_path):
    path = models.model_dir(tmp_path, "medium")
    path.mkdir(parents=True)
    (path / "model.bin").write_bytes(b"x")
    assert not models.is_downloaded(tmp_path, "medium")
    for name in models.REQUIRED_FILES:
        (path / name).write_bytes(b"x")
    assert models.is_downloaded(tmp_path, "medium")
    models.delete_model(tmp_path, "medium")
    assert not path.exists()


def test_catalog_is_multilingual_only():
    assert all(not m.id.endswith(".en") and not m.id.startswith("distil") for m in models.CATALOG)
