from pathlib import Path
import tempfile
from typing import Dict, List, Optional, Union
import uuid

from fastapi import UploadFile
from loguru import logger
from pdfminer.high_level import extract_pages
from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfpage import PDFPage
from pdfminer.pdftypes import resolve1, PDFObjRef
from pdf2image import convert_from_path
import PyPDF2
import pytesseract
import pdfplumber
from concurrent.futures import ThreadPoolExecutor
import requests
import re

class PDFService:
    """Service for processing PDF documents with comprehensive logging and error handling."""
    
    def __init__(self):
        logger.info("Initializing PDF Service")
        
    @staticmethod
    def _get_valid_url(uri_str: str) -> str:
        """Validate and clean URLs from PDF."""
        logger.debug(f"Validating URL: {uri_str}")
        
        # Filter out unwanted URLs
        if any(x in uri_str.lower() for x in ["mailto:", "tel:", "wikipedia.org", "gmail.com"]):
            return ''
            
        url_pattern = r'(?:https?://)?(?:www\.)?[a-zA-Z0-9.-]+\.(?:com|ai|org|net|edu|gov|mil|in|info|co\.uk)(?:/[a-zA-Z0-9./-]*)?'
        try:
            matches = re.findall(url_pattern, uri_str)
            if not matches:
                return ''
            
            url = matches[0]
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
                
            logger.debug(f"Validated URL: {url}")
            return url
        except Exception as e:
            logger.error(f"Error validating URL {uri_str}: {str(e)}")
            return ''

    async def extract_hyperlinks(self, pdf_path: Path) -> List[str]:
        """Extract hyperlinks from PDF document."""
        logger.info(f"Extracting hyperlinks from {pdf_path}")
        links_list = []
        
        try:
            with open(pdf_path, 'rb') as file:
                parser = PDFParser(file)
                document = PDFDocument(parser)
                
                for page_num, page in enumerate(PDFPage.create_pages(document)):
                    logger.debug(f"Processing page {page_num + 1} for hyperlinks")
                    
                    if 'Annots' not in page.attrs:
                        continue
                        
                    annotations = resolve1(page.attrs['Annots'])
                    if not annotations:
                        continue
                        
                    for annot in annotations:
                        try:
                            annot = resolve1(annot)
                            if annot.get('Subtype').name != 'Link' or 'A' not in annot:
                                continue
                                
                            uri = resolve1(annot['A'])
                            if 'URI' not in uri:
                                continue
                                
                            uri_obj = uri['URI']
                            if isinstance(uri_obj, PDFObjRef):
                                uri_obj = resolve1(uri_obj)
                                
                            uri_str = uri_obj.decode('utf-8') if isinstance(uri_obj, bytes) else str(uri_obj)
                            uri_str = uri_str.rstrip('/')
                            
                            valid_url = self._get_valid_url(uri_str)
                            if valid_url:
                                links_list.append(valid_url)
                                
                        except Exception as e:
                            logger.warning(f"Error processing annotation: {str(e)}")
                            continue
                            
            unique_links = list(set(links_list))
            logger.info(f"Extracted {len(unique_links)} unique hyperlinks")
            return unique_links
            
        except Exception as e:
            logger.error(f"Error extracting hyperlinks: {str(e)}")
            raise

    async def extract_text_from_pdf(self, pdf_path: Path) -> Dict[str, Union[str, List[str]]]:
        """Extract text content from PDF with OCR support for images."""
        logger.info(f"Beginning text extraction from {pdf_path}")
        
        try:
            extracted_text = ""
            has_tables = False
            pages_with_images = []
            
            # Check for tables and images
            logger.debug("Scanning for tables and images")
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    if page.extract_tables():
                        has_tables = True
                        logger.debug(f"Found tables on page {page_num + 1}")
                    if page.images:
                        pages_with_images.append(page_num)
                        logger.debug(f"Found images on page {page_num + 1}")
            
            # Extract basic text
            logger.debug("Extracting basic text content")
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                for page_num, page in enumerate(reader.pages):
                    logger.debug(f"Extracting text from page {page_num + 1}")
                    extracted_text += page.extract_text() + "\n"
            
            # Handle tables if present
            if has_tables:
                logger.info("Processing tables")
                with pdfplumber.open(pdf_path) as pdf:
                    for page_num, page in enumerate(pdf.pages):
                        for table in page.extract_tables():
                            logger.debug(f"Processing table on page {page_num + 1}")
                            for row in table:
                                formatted_row = "|".join([str(cell) if cell is not None else "" for cell in row])
                                extracted_text += formatted_row + "\n"
                            extracted_text += "\n"
            
            # Handle images with OCR if present
            if pages_with_images:
                logger.info(f"Processing {len(pages_with_images)} pages with images using OCR")
                pages = convert_from_path(
                    pdf_path,
                    first_page=min(pages_with_images) + 1,
                    last_page=max(pages_with_images) + 1
                )
                
                def ocr_page(page):
                    return pytesseract.image_to_string(page)
                
                with ThreadPoolExecutor() as executor:
                    ocr_results = list(executor.map(ocr_page, pages))
                    
                for page_num, ocr_result in enumerate(ocr_results):
                    logger.debug(f"Added OCR text from page {pages_with_images[page_num] + 1}")
                    extracted_text += ocr_result + "\n"
            
            # Clean extracted text
            logger.debug("Cleaning extracted text")
            cleaned_text = re.sub(r"[^a-zA-Z0-9\s@+./:,-_|]", " ", extracted_text)
            cleaned_text = cleaned_text.replace("\n", " ").replace("  ", " ")

            # Validate if it's a resume
            is_resume = self._validate_resume_content(cleaned_text)

            # Extract plain text links
            logger.debug("Extracting plain text links")
            plain_links = self._extract_plain_text_links(cleaned_text)
            
            logger.info("Text extraction completed successfully")
            return {
                "status": True,
                "cleaned_text": cleaned_text,
                "links": plain_links,
                "is_resume": is_resume
            }
            
        except Exception as e:
            logger.error(f"Error in text extraction: {str(e)}")
            return {
                "status": False,
                "error": str(e)
            }

    def _validate_resume_content(self, text: str) -> bool:
        """Validate if the text content appears to be a resume."""
        resume_keywords = [
            "experience", "education", "skills", "qualification",
            "projects", "certification", "work", "employment",
            "job", "profile", "accomplishment", "achievement",
            "responsibility", "university", "college", "degree"
        ]
        
        text_lower = text.lower()
        matches = sum(1 for keyword in resume_keywords if keyword in text_lower)
        
        # Require at least 3 resume keywords to consider it a valid resume
        return matches >= 4

    def _extract_plain_text_links(self, text: str) -> List[str]:
        """Extract valid URLs from plain text."""
        logger.debug("Extracting plain text links")
        links = []
        url_pattern = r'(?:https?://)?(?:www\.)?[a-zA-Z0-9.-]+\.(?:com|org|net|edu|gov|mil|in|info|co\.uk)(?:/[a-zA-Z0-9./-]*)?'
        
        matches = re.findall(url_pattern, text)
        for match in matches:
            valid_url = self._get_valid_url(match.rstrip('/'))
            if valid_url:
                links.append(valid_url)
                
        logger.debug(f"Found {len(links)} plain text links")
        return list(set(links))

    async def process_pdf(self, source: Union[str, UploadFile]) -> Dict:
        """Process PDF from either URL or uploaded file."""
        logger.info("Starting PDF processing")
        
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                if isinstance(source, str) and (source.startswith('http://') or source.startswith('https://')):
                    logger.info(f"Downloading PDF from URL: {source}")
                    response = requests.get(source)
                    response.raise_for_status()
                    tmp_file.write(response.content)
                else:
                    logger.info("Processing uploaded PDF file")
                    content = await source.read()
                    tmp_file.write(content)
                
                tmp_path = Path(tmp_file.name)
                
            # Extract text and links
            text_result = await self.extract_text_from_pdf(tmp_path)
            if not text_result["status"]:
                raise Exception(text_result["error"])
                
            # Extract hyperlinks
            hyperlinks = await self.extract_hyperlinks(tmp_path)
            
            # Combine all links
            all_links = list(set(hyperlinks + text_result["links"]))
            
            # Clean up temporary file
            tmp_path.unlink()
            
            logger.info("PDF processing completed successfully")
            return {
                "status": True,
                "cleaned_text": text_result["cleaned_text"],
                "links": all_links
            }
            
        except Exception as e:
            logger.error(f"Error in PDF processing: {str(e)}")
            if 'tmp_path' in locals():
                tmp_path.unlink()
            return {
                "status": False,
                "error": str(e)
            }