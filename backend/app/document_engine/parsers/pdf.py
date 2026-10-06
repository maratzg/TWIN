from io import BytesIO

from pypdf import PdfReader, mult
from pypdf.errors import FileNotDecryptedError, PdfReadError

from app.document_engine.types import ExtractedPage


class PDFDocumentError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class PDFParser:
    max_page_content_bytes = 25 * 1024 * 1024

    def parse(self, content: bytes) -> list[ExtractedPage]:
        try:
            reader = PdfReader(BytesIO(content), strict=True)
        except (PdfReadError, ValueError, OSError) as exc:
            raise PDFDocumentError("CORRUPT_PDF", "The PDF is corrupt or unsupported.") from exc
        if reader.is_encrypted:
            try:
                result = reader.decrypt("")
            except Exception as exc:
                raise PDFDocumentError("ENCRYPTED_PDF", "Encrypted PDFs are not supported.") from exc
            if not result:
                raise PDFDocumentError("ENCRYPTED_PDF", "Encrypted PDFs are not supported.")
        if not reader.pages:
            raise PDFDocumentError("EMPTY_PDF", "The PDF does not contain any pages.")

        pages: list[ExtractedPage] = []
        try:
            for page_number, page in enumerate(reader.pages, start=1):
                contents = page.get_contents()
                if contents is not None and len(contents.get_data()) > self.max_page_content_bytes:
                    raise PDFDocumentError(
                        "PDF_PAGE_TOO_COMPLEX",
                        f"Page {page_number} exceeds the safe content-stream limit.",
                    )
                blocks: list[dict] = []

                def visitor(text, user_matrix, text_matrix, _font, font_size):
                    clean = " ".join(text.split())
                    if not clean:
                        return
                    matrix = mult(text_matrix, user_matrix)
                    blocks.append(
                        {
                            "text": clean[:1000],
                            "x": round(float(matrix[4]), 2),
                            "y": round(float(matrix[5]), 2),
                            "font_size": round(float(font_size or 0), 2),
                        }
                    )

                text = page.extract_text(visitor_text=visitor) or ""
                pages.append(
                    ExtractedPage(
                        page_number=page_number,
                        text=text.strip(),
                        blocks=blocks,
                    )
                )
        except FileNotDecryptedError as exc:
            raise PDFDocumentError("ENCRYPTED_PDF", "Encrypted PDFs are not supported.") from exc
        except PDFDocumentError:
            raise
        except Exception as exc:
            raise PDFDocumentError("PDF_EXTRACTION_FAILED", "PDF text extraction failed.") from exc
        return pages
