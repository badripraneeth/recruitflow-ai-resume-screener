import os
from pypdf import PdfReader
from pypdf.errors import PdfReadError, PdfStreamError


# Maximum allowed PDF file size: 10 MB
MAX_PDF_SIZE_BYTES = 10 * 1024 * 1024


class PDFValidationError(ValueError):
    """Raised when an uploaded file fails validation (extension, MIME, size, or signature)."""
    pass


class PDFParsingError(RuntimeError):
    """Raised when a PDF file is corrupted, encrypted, or cannot be read."""
    pass


def validate_pdf_file(file):
    """
    Validates the uploaded file to ensure it is a genuine, safe PDF under the size limit.
    Checks:
      1. File extension is .pdf
      2. File size does not exceed MAX_PDF_SIZE_BYTES (10MB)
      3. MIME content-type (if available) is application/pdf
      4. File signature (magic bytes) starts with %PDF-
    """
    if isinstance(file, (str, os.PathLike)):
        filename = os.path.basename(str(file))
        file_size = os.path.getsize(file) if os.path.exists(file) else None
    else:
        filename = getattr(file, 'name', '')
        file_size = getattr(file, 'size', None)

    if not filename.lower().endswith('.pdf'):
        raise PDFValidationError(f"Invalid file extension for '{filename}'. Only PDF files are supported.")

    if file_size is not None and file_size > MAX_PDF_SIZE_BYTES:
        max_mb = MAX_PDF_SIZE_BYTES / (1024 * 1024)
        raise PDFValidationError(f"File '{filename}' exceeds the maximum allowed size of {max_mb:.0f}MB.")

    # Validate MIME type from upload header if present
    content_type = getattr(file, 'content_type', None)
    if content_type and content_type.lower() not in ('application/pdf', 'application/x-pdf', 'binary/octet-stream'):
        raise PDFValidationError(f"File '{filename}' has invalid MIME type '{content_type}'. Must be application/pdf.")

    # Validate magic bytes / PDF header signature
    try:
        if isinstance(file, (str, os.PathLike)):
            with open(file, 'rb') as fp:
                header = fp.read(5)
                if not header.startswith(b'%PDF-'):
                    raise PDFValidationError(f"File '{filename}' does not have a valid PDF header signature.")
        elif hasattr(file, 'seek') and hasattr(file, 'read'):
            file.seek(0)
            header = file.read(5)
            file.seek(0)
            if not header.startswith(b'%PDF-'):
                raise PDFValidationError(f"File '{filename}' does not have a valid PDF header signature.")
    except PDFValidationError:
        raise
    except Exception as e:
        raise PDFValidationError(f"Unable to read file signature for '{filename}': {str(e)}")


def extract_text_from_pdf(file):
    """
    Safely extracts raw text from a PDF file using pypdf.

    Parameters:
      file: A file-like object, Django UploadedFile, or file path (str/PathLike).

    Returns:
      str: The extracted text from all readable pages (may be empty string if PDF contains no text).

    Raises:
      PDFValidationError: If file fails validation (non-PDF, oversized, invalid header).
      PDFParsingError: If PDF is corrupted, encrypted, or unreadable.
    """
    # If a path string is provided, open and delegate
    if isinstance(file, (str, os.PathLike)):
        validate_pdf_file(file)
        with open(file, 'rb') as f:
            return extract_text_from_pdf(f)

    # 1. Validate file extension, size, and header signature
    validate_pdf_file(file)

    # 2. Reset stream pointer to beginning
    if hasattr(file, 'seek'):
        file.seek(0)

    # 3. Read PDF with pypdf
    try:
        reader = PdfReader(file)
    except (PdfReadError, PdfStreamError, Exception) as err:
        raise PDFParsingError(f"Corrupted or unreadable PDF: {str(err)}")

    # 4. Check encryption
    if reader.is_encrypted:
        try:
            decrypted = reader.decrypt("")
            if not decrypted:
                raise PDFParsingError("PDF is password protected and cannot be processed.")
        except Exception:
            raise PDFParsingError("PDF is password protected and cannot be processed.")

    # 5. Handle empty PDF (0 pages)
    if not reader.pages:
        return ""

    # 6. Extract text page by page
    text_fragments = []
    for idx, page in enumerate(reader.pages):
        try:
            page_text = page.extract_text()
            if page_text:
                text_fragments.append(page_text.strip())
        except Exception:
            # Continue extracting remaining pages if a single page stream fails
            continue

    # Reset pointer again for any downstream storage
    if hasattr(file, 'seek'):
        file.seek(0)

    extracted_text = "\n\n".join(text_fragments).strip()
    return extracted_text
