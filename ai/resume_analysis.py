"""
Resume analysis pre-processing and validation module.
Guarantees clean, non-empty text input before submitting to the LLM API.
"""

import re


class EmptyResumeTextError(ValueError):
    """Raised when resume text is missing, blank, or contains no readable tokens."""
    pass


def validate_resume_text(text):
    """
    Validates that the resume contains sufficient readable text for analysis.
    Raises EmptyResumeTextError if empty or too brief.
    """
    if not text or not isinstance(text, str):
        raise EmptyResumeTextError("Resume text is empty. Cannot perform analysis.")

    cleaned = clean_resume_text(text)
    if not cleaned or len(cleaned) < 20:
        raise EmptyResumeTextError(
            "Resume contains insufficient readable text (fewer than 20 characters). "
            "Please ensure the PDF contains extractable digital text."
        )

    return cleaned


def clean_resume_text(text):
    """
    Cleans raw text extracted from PDF:
    - Removes null characters
    - Normalizes irregular whitespace and line breaks
    - Limits excessive repeated characters
    """
    if not text:
        return ""

    # Strip null bytes
    text = text.replace('\x00', ' ')

    # Normalize carriage returns
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # Collapse excessive blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Collapse excessive spaces/tabs
    text = re.sub(r'[ \t]{2,}', ' ', text)

    return text.strip()
