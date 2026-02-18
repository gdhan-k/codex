from pathlib import Path

import webpage_to_korean_pdf as app


def test_chunk_text_splits_long_text():
    text = "\n".join(["a" * 20 for _ in range(4)])
    chunks = app.chunk_text(text, max_chars=30)

    assert len(chunks) >= 2
    assert all(len(chunk) <= 30 for chunk in chunks)


def test_translate_text_uses_translate_chunk(monkeypatch):
    def stub_translate(chunk, source, target, timeout):
        return f"KO:{chunk[:5]}"

    monkeypatch.setattr(app, "_translate_chunk", stub_translate)

    cfg = app.TranslationConfig(source_lang="en", target_lang="ko", chunk_size=10)
    result = app.translate_text("hello\nworld", cfg)

    assert "KO:" in result


def test_write_pdf_creates_file(tmp_path: Path):
    output = tmp_path / "out.pdf"
    app.write_pdf("테스트 문장입니다.", output, title="demo")

    assert output.exists()
    assert output.stat().st_size > 0
    assert output.read_bytes().startswith(b"%PDF")


def test_text_extractor_does_not_drop_body_after_meta_or_link():
    parser = app.TextExtractor()
    parser.feed(
        "<html><head><meta charset='utf-8'><link rel='stylesheet' href='a.css'></head>"
        "<body><h1>Hello</h1><p>World</p></body></html>"
    )

    assert "Hello" in parser.parts
    assert "World" in parser.parts
