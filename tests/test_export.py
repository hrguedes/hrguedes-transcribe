from app.export import export_session, to_md, to_txt
from app.sessions import Segment

SEGMENTS = [
    Segment(0.0, 2.0, "Bom dia, começamos a reunião."),
    Segment(2.2, 4.0, "A pauta é o orçamento."),
    Segment(8.0, 9.5, "Próximo item: ações."),
]


def _session(store):
    s = store.create("Reunião de Planejamento")
    s.duration = 605
    s.save_transcript(SEGMENTS, "pt", "test")
    return s


def test_txt_paragraphs_and_timestamps(store):
    s = _session(store)
    assert to_txt(s, SEGMENTS) == (
        "Bom dia, começamos a reunião. A pauta é o orçamento.\n\nPróximo item: ações.\n"
    )
    assert "[00:00:08] Próximo item: ações." in to_txt(s, SEGMENTS, timestamps=True)


def test_md_header(store):
    md = to_md(_session(store), SEGMENTS)
    assert md.startswith("# Reunião de Planejamento\n")
    assert "**Duração:** 10min 05s" in md


def test_export_all_formats(qapp, store, tmp_path):
    s = _session(store)
    for fmt in ("txt", "md", "pdf"):
        out = tmp_path / f"out.{fmt}"
        export_session(s, out, fmt)
        assert out.stat().st_size > 0
    assert (tmp_path / "out.pdf").read_bytes().startswith(b"%PDF")
    assert "orçamento" in (tmp_path / "out.md").read_text(encoding="utf-8")
