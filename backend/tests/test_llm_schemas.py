"""Unit tests for tolerant LLM JSON parsing and test-level backward compatibility."""

from __future__ import annotations

import pytest

from ase_security_review.domain.enums import TestLevel, parse_test_level
from ase_security_review.usecase.llm_schemas import parse_json_object


def test_parse_test_level_maps_legacy_both_to_pentest():
    assert parse_test_level("both") == TestLevel.PENTEST
    assert parse_test_level("pentest") == TestLevel.PENTEST
    assert parse_test_level("dast") == TestLevel.DAST
    assert parse_test_level("none") == TestLevel.NONE
    assert parse_test_level("garbage") == TestLevel.DAST
    assert parse_test_level(None) == TestLevel.DAST


def test_plain_json():
    assert parse_json_object('{"a": 1}') == {"a": 1}


def test_json_with_prose_around():
    text = 'Here is the result:\n{"test_level": "both"} \nThat is all.'
    assert parse_json_object(text) == {"test_level": "both"}


def test_json_in_code_fence():
    text = '```json\n{"requires_pentest": true}\n```'
    assert parse_json_object(text) == {"requires_pentest": True}


def test_empty_raises_descriptive_error():
    with pytest.raises(ValueError, match="empty"):
        parse_json_object("")
    with pytest.raises(ValueError, match="empty"):
        parse_json_object("   \n  ")


def test_garbage_raises_with_snippet():
    with pytest.raises(ValueError, match="not valid JSON"):
        parse_json_object("no json here at all")
