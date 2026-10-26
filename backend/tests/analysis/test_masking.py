"""Tests for pattern-based masking (FR-29, NFR-06, US-32)."""

from app.analysis.masking import (
    MaskedItem,
    MaskedItemType,
    apply_masking,
    detect_masked_items,
    mask,
    mask_literal_occurrences,
)

SAMPLE_REPORT = (
    "login crashes when i use my email jane.doe@example.com, "
    "password: hunter2, and the request sent Bearer sk-abc123def456ghi789jkl"
)


class TestDetectMaskedItems:
    def test_email_is_detected(self):
        items = detect_masked_items("contact me at jane.doe@example.com please")
        assert len(items) == 1
        assert items[0].type == MaskedItemType.EMAIL
        assert items[0].original_text == "jane.doe@example.com"

    def test_password_key_value_is_detected(self):
        items = detect_masked_items("password: hunter2")
        assert len(items) == 1
        assert items[0].type == MaskedItemType.PASSWORD
        assert items[0].original_text == "hunter2"

    def test_password_is_detected_case_insensitively_and_with_equals(self):
        items = detect_masked_items("PWD=SuperSecret1")
        assert len(items) == 1
        assert items[0].type == MaskedItemType.PASSWORD

    def test_the_word_password_alone_in_prose_is_not_detected(self):
        """A false negative here is safer than flooding review with a hit
        on every sentence that merely mentions the word."""
        items = detect_masked_items("the password field on the login form is empty")
        assert items == []

    def test_api_key_with_known_prefix_is_detected(self):
        items = detect_masked_items("using key sk-abc123def456ghi789jkl in the request")
        assert len(items) == 1
        assert items[0].type == MaskedItemType.API_KEY

    def test_aws_style_key_is_detected(self):
        items = detect_masked_items("AKIAIOSFODNN7EXAMPLE was used")
        assert len(items) == 1
        assert items[0].type == MaskedItemType.API_KEY

    def test_bearer_token_is_detected(self):
        items = detect_masked_items("Authorization: Bearer abc123def456ghi789")
        assert len(items) == 1
        assert items[0].type == MaskedItemType.TOKEN
        assert items[0].original_text == "abc123def456ghi789"

    def test_jwt_shape_is_detected(self):
        jwt = (
            "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0."
            "dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        )
        items = detect_masked_items(f"token was {jwt} in the logs")
        assert len(items) == 1
        assert items[0].type == MaskedItemType.TOKEN

    def test_ordinary_text_with_no_secret_detects_nothing(self):
        assert detect_masked_items("login crashes when i click submit") == []

    def test_overlapping_matches_keep_only_the_first(self):
        """A Bearer token also matches the email-free surrounding text; the
        more specific token pattern must win, not be duplicated."""
        items = detect_masked_items("Authorization: Bearer abc123def456ghi789")
        assert len(items) == 1

    def test_multiple_distinct_secrets_are_all_detected(self):
        items = detect_masked_items(SAMPLE_REPORT)
        types = {item.type for item in items}
        assert MaskedItemType.EMAIL in types
        assert MaskedItemType.PASSWORD in types
        assert MaskedItemType.TOKEN in types or MaskedItemType.API_KEY in types


class TestApplyMasking:
    def test_detected_items_are_replaced_with_the_placeholder(self):
        items = detect_masked_items("email me at jane.doe@example.com")
        masked = apply_masking("email me at jane.doe@example.com", items)
        assert "jane.doe@example.com" not in masked
        assert "[masked]" in masked

    def test_text_outside_items_is_unchanged(self):
        items = detect_masked_items("email me at jane.doe@example.com now")
        masked = apply_masking("email me at jane.doe@example.com now", items)
        assert masked == "email me at [masked] now"

    def test_no_items_leaves_text_unchanged(self):
        assert apply_masking("nothing to mask here", []) == "nothing to mask here"


class TestMaskLiteralOccurrences:
    def test_every_occurrence_of_a_manually_masked_value_is_masked(self):
        """US-32 criterion 3: any selected text can be masked manually, and
        every occurrence of it is masked."""
        text = "internal-id-42 appeared twice: internal-id-42 and internal-id-42 again"
        items = mask_literal_occurrences(text, [], "internal-id-42")
        assert len(items) == 3
        assert all(item.type == MaskedItemType.MANUAL for item in items)

    def test_manual_masking_does_not_duplicate_an_already_detected_span(self):
        text = "jane.doe@example.com appears once"
        detected = detect_masked_items(text)
        combined = mask_literal_occurrences(text, detected, "jane.doe@example.com")
        assert len(combined) == 1

    def test_empty_value_masks_nothing(self):
        items = mask_literal_occurrences("some text", [], "")
        assert items == []

    def test_restoring_a_false_positive_means_dropping_it_from_the_list(self):
        """US-32 criterion 2: restoring a false positive. Since items are a
        plain list, restoring one is the caller filtering it out before
        calling apply_masking; proven here by checking the masked text
        reverts to the original once the item is dropped."""
        text = "call me at jane.doe@example.com"
        items = detect_masked_items(text)
        restored = [item for item in items if item.original_text != "jane.doe@example.com"]
        assert apply_masking(text, restored) == text


class TestMask:
    def test_mask_returns_masked_text_and_items_together(self):
        result = mask("email jane.doe@example.com and password: hunter2")
        assert "jane.doe@example.com" not in result.masked_text
        assert "hunter2" not in result.masked_text
        assert len(result.items) == 2

    def test_nothing_detected_still_returns_a_result(self):
        """US-32 criterion 4: when nothing is detected, review is still
        available, not skipped. Proven at this layer by confirming a clean
        report returns an empty item list rather than an error or None."""
        result = mask("login crashes when i click submit")
        assert result.masked_text == "login crashes when i click submit"
        assert result.items == []

    def test_only_the_masked_copy_differs_from_the_original(self):
        """US-32 criterion 5: the original is untouched; masking produces a
        separate copy."""
        original = "email jane.doe@example.com"
        result = mask(original)
        assert result.masked_text != original


def test_masked_item_records_the_original_span_for_restoration():
    item = MaskedItem(type=MaskedItemType.EMAIL, original_text="a@b.com", start=5, end=12)
    assert item.original_text == "a@b.com"
    assert item.start == 5
    assert item.end == 12
