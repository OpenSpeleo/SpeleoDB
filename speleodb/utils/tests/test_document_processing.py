# -*- coding: utf-8 -*-

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pymupdf
import pytest
from django.core.files.base import ContentFile
from PIL import Image

from speleodb.utils.document_processing import DocumentProcessor


class TestDocumentProcessor:
    def test_is_document_file(self) -> None:
        """Test document file detection."""
        # Valid document files
        assert DocumentProcessor.is_document_file("document.pdf")
        assert DocumentProcessor.is_document_file("report.doc")
        assert DocumentProcessor.is_document_file("thesis.docx")
        assert DocumentProcessor.is_document_file("readme.txt")
        assert DocumentProcessor.is_document_file("document.rtf")

        # Invalid files
        assert not DocumentProcessor.is_document_file("image.jpg")
        assert not DocumentProcessor.is_document_file("video.mp4")
        assert not DocumentProcessor.is_document_file("")

    def test_create_placeholder(self) -> None:
        """Test generic placeholder creation."""
        placeholder = DocumentProcessor.create_placeholder()

        assert isinstance(placeholder, ContentFile)
        assert placeholder.size > 0

        # Verify it's a valid image
        img = Image.open(placeholder)
        assert img.format == "JPEG"
        assert img.size == (300, 200)

    def test_generate_preview_pdf_with_real_file(self) -> None:
        """Test preview generation for real PDF files."""
        artifacts_dir = Path(__file__).parent.parent.parent / "api/v1/tests/artifacts"

        with (artifacts_dir / "document.pdf").open(mode="rb") as f:
            preview = DocumentProcessor.generate_preview(f, filename="test.pdf")

        assert isinstance(preview, ContentFile)
        assert preview.size > 0

        # Verify it's a valid JPEG image
        img = Image.open(preview)
        # PyMuPDF might generate either placeholder or actual preview
        # depending on whether it's installed
        assert img.format == "JPEG"
        assert img.width <= 302  # 300 + 2 border  # noqa: PLR2004
        assert img.height <= 202  # 200 + 2 border  # noqa: PLR2004

    def test_generate_preview_different_types(self) -> None:
        """Test preview generation for different document types."""
        # Non-PDF documents should get placeholders
        test_content = b"Test document content"

        for ext, _ in [(".doc", "DOC"), (".docx", "DOCX"), (".txt", "TXT")]:
            mock_file = BytesIO(test_content)
            preview = DocumentProcessor.generate_preview(
                mock_file, filename=f"test{ext}"
            )

            assert isinstance(preview, ContentFile)
            assert preview.size > 0

            # Verify it's a placeholder
            img = Image.open(preview)
            assert img.format == "JPEG"
            assert img.size == (300, 200)

    def test_generate_preview_pdf_error_handling(self) -> None:
        """Test error handling when PDF extraction fails."""
        # Invalid PDF data
        invalid_pdf = BytesIO(b"Not a valid PDF")

        with pytest.raises(pymupdf.FileDataError, match="Failed to open stream"):
            _ = DocumentProcessor.generate_preview(invalid_pdf, filename="corrupt.pdf")

    def test_generate_preview_empty_filename(self) -> None:
        """Test preview generation with empty filename."""
        mock_file = BytesIO(b"content")
        preview = DocumentProcessor.generate_preview(mock_file, filename="")

        assert isinstance(preview, ContentFile)
        assert preview.size > 0
