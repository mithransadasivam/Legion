import pytest

from legion.documents import CHUNK_CHARS, OVERLAP_CHARS, chunk_file, chunk_text, find_files, read_pages


def make_pdf(pages: list[str]) -> bytes:
    """A real, minimal PDF with one line of text per page -- no PDF-writing library needed."""
    count = len(pages)
    font_id = 3 + 2 * count
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(count))
    objects = ["<< /Type /Catalog /Pages 2 0 R >>", f"<< /Type /Pages /Kids [{kids}] /Count {count} >>"]
    for i, text in enumerate(pages):
        stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET"
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {4 + 2 * i} 0 R "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> >>"
        )
        objects.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    out = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{body}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out


class TestChunkText:
    def test_short_text_is_one_chunk(self):
        assert chunk_text("A short note.") == ["A short note."]

    def test_blank_text_yields_nothing(self):
        assert chunk_text("") == []
        assert chunk_text("  \n\n   \n") == []

    def test_long_text_is_cut_into_bounded_chunks(self):
        text = " ".join(f"This is sentence number {i}." for i in range(200))

        chunks = chunk_text(text)

        assert len(chunks) > 3
        assert all(len(chunk) <= CHUNK_CHARS + OVERLAP_CHARS for chunk in chunks)

    def test_nothing_is_lost_between_chunks(self):
        sentences = [f"Fact {i} is documented here." for i in range(150)]

        joined = " ".join(chunk_text(" ".join(sentences)))

        assert all(sentence in joined for sentence in sentences)

    def test_each_chunk_repeats_the_end_of_the_previous_one(self):
        sentences = [f"Sentence {i} ends here." for i in range(100)]

        chunks = chunk_text(" ".join(sentences))

        for earlier, later in zip(chunks, chunks[1:]):
            last_sentence_before = earlier.split(". ")[-1].rstrip(".") + "."
            assert last_sentence_before in later, "an idea straddling a cut should appear whole in one chunk"

    def test_cuts_land_on_sentence_boundaries(self):
        chunks = chunk_text(" ".join(f"Sentence {i} ends here." for i in range(100)))

        assert all(chunk.endswith(".") for chunk in chunks)

    def test_paragraphs_are_kept_whole_when_they_fit(self):
        text = "First paragraph here.\n\nSecond paragraph here."

        assert chunk_text(text) == ["First paragraph here. Second paragraph here."]

    def test_a_wall_of_text_with_no_punctuation_is_still_cut(self):
        chunks = chunk_text("word " * 1000)

        assert len(chunks) > 1
        assert all(len(chunk) <= CHUNK_CHARS + OVERLAP_CHARS for chunk in chunks)

    def test_a_single_endless_token_is_hard_cut(self):
        chunks = chunk_text("x" * 5000)

        assert len(chunks) > 1
        assert "".join(chunks).count("x") >= 5000


class TestFindFiles:
    def test_finds_supported_files_recursively_in_a_stable_order(self, tmp_path):
        (tmp_path / "b.txt").write_text("b")
        (tmp_path / "a.md").write_text("a")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "c.PDF").write_bytes(make_pdf(["c"]))

        found = [path.relative_to(tmp_path).as_posix() for path in find_files(tmp_path)]

        assert found == ["a.md", "b.txt", "sub/c.PDF"]

    def test_ignores_unsupported_hidden_and_editor_temp_files(self, tmp_path):
        for name in ("photo.jpg", "data.csv", ".hidden.txt", "~$draft.md", "keep.txt"):
            (tmp_path / name).write_text("x")

        assert [path.name for path in find_files(tmp_path)] == ["keep.txt"]

    def test_a_missing_folder_is_just_empty(self, tmp_path):
        assert find_files(tmp_path / "nope") == []


class TestReading:
    def test_a_text_file_is_one_page_labelled_with_its_name(self, tmp_path):
        path = tmp_path / "notes.md"
        path.write_text("Some notes.", encoding="utf-8")

        assert read_pages(path) == [("notes.md", "Some notes.")]

    def test_bytes_that_are_not_valid_utf8_do_not_break_reading(self, tmp_path):
        path = tmp_path / "odd.txt"
        path.write_bytes(b"caf\xe9 notes")

        [(label, text)] = read_pages(path)

        assert "notes" in text

    def test_a_pdf_is_read_page_by_page_with_page_numbers(self, tmp_path):
        path = tmp_path / "paper.pdf"
        path.write_bytes(make_pdf(["Alpha findings.", "Beta findings."]))

        pages = read_pages(path)

        assert [label for label, _ in pages] == ["paper.pdf, p. 1", "paper.pdf, p. 2"]
        assert "Alpha findings." in pages[0][1]
        assert "Beta findings." in pages[1][1]

    def test_chunks_remember_which_page_they_came_from(self, tmp_path):
        path = tmp_path / "paper.pdf"
        path.write_bytes(make_pdf(["Alpha findings.", "Beta findings."]))

        chunks = chunk_file(path)

        assert [chunk.source for chunk in chunks] == ["paper.pdf, p. 1", "paper.pdf, p. 2"]

    def test_a_corrupt_pdf_yields_nothing_instead_of_an_error(self, tmp_path):
        path = tmp_path / "broken.pdf"
        path.write_bytes(b"this is not a pdf at all")

        assert chunk_file(path) == []

    def test_an_empty_file_yields_nothing(self, tmp_path):
        path = tmp_path / "empty.txt"
        path.write_text("")

        assert chunk_file(path) == []
