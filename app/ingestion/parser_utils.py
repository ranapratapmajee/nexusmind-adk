# filepath: app/ingestion/parser_utils.py
import io
import logging
from pypdf import PdfReader

logger = logging.getLogger(__name__)

class PDFExtractor:
    """Extracts raw text strings from byte buffers."""
    
    @staticmethod
    def extract_clean_text(file_bytes: bytes) -> str:
        """Reads stream bytes using pypdf to consolidate page paragraphs."""
        try:
            # Wrap the raw memory buffer cleanly
            bytes_stream = io.BytesIO(file_bytes)
            pdf_reader = PdfReader(bytes_stream)
            
            extracted_pages = []
            for idx, page in enumerate(pdf_reader.pages):
                page_text = page.extract_text()
                if page_text:
                    extracted_pages.append(page_text)
                    
            consolidated_text = "\n\n".join(extracted_pages)
            logger.info(f"📄 Extracted {len(pdf_reader.pages)} pages from the uploaded stream.")
            return consolidated_text
            
        except Exception as e:
            logger.error(f"❌ Failed to extract text from PDF data stream: {str(e)}")
            raise RuntimeError(f"PDF extraction error: {str(e)}")

pdf_extractor = PDFExtractor()