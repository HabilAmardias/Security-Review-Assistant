"""Unit tests for hierarchical chunking."""

from __future__ import annotations

from ase_security_review.usecase.chunking import chunk_text, recursive_split, split_by_headings


def test_split_by_headings_english_and_indo():
    text = "Intro line.\nChapter 1: Auth\nFirst para.\nBAB 2: Payment\nSecond para.\n1.2.3 Testing\nThird para."
    sections = split_by_headings(text)
    headings = [h for h, _ in sections]
    assert "Chapter 1: Auth" in headings
    assert "BAB 2: Payment" in headings
    assert "1.2.3 Testing" in headings


def test_split_by_headings_no_match_returns_single_section():
    text = "just a paragraph with no headings here"
    sections = split_by_headings(text)
    assert len(sections) == 1
    assert sections[0][0] == ""
    assert "just a paragraph" in sections[0][1]


def test_recursive_split_respects_size():
    text = "word " * 2000
    chunks = recursive_split(text, chunk_size=500, overlap=50)
    assert len(chunks) > 1
    assert all(len(c) <= 600 for c in chunks)  # chunk_size + overlap tolerance


def test_chunk_text_keeps_heading_context():
    text = "BAB 2: Kriteria Penetration Test\n" + ("content paragraph " * 300)
    chunks = chunk_text(text, chunk_size=500, overlap=50)
    assert chunks
    assert "BAB 2: Kriteria Penetration Test" in chunks[0]


def test_chunk_text_empty():
    assert chunk_text("   \n\n  ") == []
