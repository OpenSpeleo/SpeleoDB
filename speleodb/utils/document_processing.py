# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

import fitz  # PyMuPDF
from django.core.files.base import ContentFile
from PIL import Image
from PIL import ImageDraw

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Utility class for processing documents, including preview generation."""

    # Supported document extensions
    DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt", ".rtf"}

    @staticmethod
    def is_document_file(filename: str) -> bool:
        """Check if file is a document based on extension."""
        if not filename:
            return False
        return Path(filename).suffix.lower() in DocumentProcessor.DOCUMENT_EXTENSIONS

    @staticmethod
    def generate_preview(
        document_file: BinaryIO, filename: str = ""
    ) -> ContentFile[bytes]:
        """
        Generate a preview thumbnail for document.

        For PDFs, extracts the first page using PyMuPDF (no external dependencies).
        For other document types, generates a document icon placeholder.

        Args:
            document_file: File-like object containing the document
            filename: Original filename to determine document type

        Returns:
            ContentFile containing the preview image in JPEG format
        """
        # Determine document type from filename
        ext = Path(filename).suffix.lower() if filename else ""

        # Extract first page for PDFs
        if ext == ".pdf":
            # Reset file pointer
            document_file.seek(0)
            pdf_data = document_file.read()

            # Open PDF with PyMuPDF
            with fitz.open(stream=pdf_data, filetype="pdf") as pdf_reader:  # type: ignore[type-arg,no-untyped-call]
                # PDF with no content or invalid
                if not pdf_reader:
                    return DocumentProcessor._create_placeholder_with_icon(ext)

                # Get first page
                page = pdf_reader[0]

                # Render page to image at lower resolution for thumbnail
                # zoom = 0.5 means 72 DPI (half of default 144 DPI)
                mat = fitz.Matrix(0.5, 0.5)  # type: ignore[type-arg,no-untyped-call]
                pix = page.get_pixmap(matrix=mat)  # pyright: ignore[reportAttributeAccessIssue]

                # Convert to PIL Image
                img_data = pix.pil_tobytes(format="PNG")
                img = Image.open(BytesIO(img_data))

                # Convert to RGB if necessary
                if img.mode != "RGB":
                    img = img.convert("RGB")  # type: ignore[assignment]

                # Resize to max 300x200 maintaining aspect ratio
                img.thumbnail((300, 200), Image.Resampling.LANCZOS)

                # Add a subtle border
                bordered_img = Image.new(
                    "RGB", (img.width + 2, img.height + 2), (200, 200, 200)
                )
                bordered_img.paste(img, (1, 1))

                # Save to buffer
                buffer = BytesIO()
                bordered_img.save(buffer, format="JPEG", quality=85)
                buffer.seek(0)

                return ContentFile(buffer.read())

        # For non-PDF documents or if PDF extraction fails, create a placeholder with
        # icon
        return DocumentProcessor._create_placeholder_with_icon(ext)

    @staticmethod
    def _create_placeholder_with_icon(ext: str) -> ContentFile[bytes]:
        """Create a placeholder image with document icon."""
        # Create a light gray placeholder
        img = Image.new("RGB", (300, 200), color=(240, 240, 240))
        draw = ImageDraw.Draw(img)

        # Draw document icon
        # Page outline
        page_x1, page_y1 = 100, 40
        page_x2, page_y2 = 200, 160
        corner_size = 20

        # Draw main rectangle
        draw.rectangle(
            [(page_x1, page_y1), (page_x2, page_y2)],
            outline=(100, 100, 100),
            width=2,
        )

        # Draw folded corner
        points = [
            (page_x2 - corner_size, page_y1),
            (page_x2 - corner_size, page_y1 + corner_size),
            (page_x2, page_y1 + corner_size),
        ]
        draw.polygon(points, fill=(200, 200, 200), outline=(100, 100, 100))

        # Draw some lines to represent text
        line_y = page_y1 + 40
        line_spacing = 15
        for i in range(4):
            y = line_y + (i * line_spacing)
            if y < page_y2 - 20:
                draw.line(
                    [(page_x1 + 20, y), (page_x2 - 20, y)],
                    fill=(180, 180, 180),
                    width=2,
                )

        # Add document type text
        doc_type = {
            ".pdf": "PDF",
            ".doc": "DOC",
            ".docx": "DOCX",
            ".txt": "TXT",
            ".rtf": "RTF",
        }.get(ext, "DOC")

        # Draw text
        text = doc_type
        text_width = len(text) * 8  # Approximate
        text_x = (300 - text_width) // 2
        text_y = 170
        draw.text((text_x, text_y), text, fill=(100, 100, 100))

        # Save to buffer
        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        buffer.seek(0)

        return ContentFile(buffer.read())

    @staticmethod
    def create_placeholder() -> ContentFile[bytes]:
        """Create a generic document placeholder image."""
        return DocumentProcessor._create_placeholder_with_icon("")
