from typing import Optional
from datetime import datetime
import uuid

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from loguru import logger

from app.services.pdf import PDFService
from app.services.ai import AIService, AIServiceConfig
from app.core.config import get_settings
from app.core.dependencies import get_ai_service, get_pdf_service
from app.models.schemas import (
    ResumeResponse, 
    ResumeProcessingError,
    ProcessingStatus
)

router = APIRouter(prefix="/resume", tags=["Resume Processing"])

@router.post(
    "/parse",
    response_model=ResumeResponse,
    responses={
        400: {"model": ResumeProcessingError},
        500: {"model": ResumeProcessingError}
    }
)
async def parse_resume(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    pdf_service: PDFService = Depends(get_pdf_service),
    ai_service: AIService = Depends(get_ai_service),
) -> ResumeResponse:
    """
    Process and parse resume file to extract structured information.
    
    Args:
        file: Uploaded PDF resume file
        background_tasks: FastAPI background tasks handler
        pdf_service: Injected PDF processing service
        ai_service: Injected AI service
    
    Returns:
        ResumeResponse containing structured resume information
    """
    process_id = str(uuid.uuid4())
    start_time = datetime.utcnow()
    
    logger.info(f"[{process_id}] Starting resume parsing process")
    
    try:
        # Validate file type
        if not file.filename.endswith('.pdf'):
            logger.error(f"[{process_id}] Invalid file type: {file.filename}")
            raise HTTPException(
                status_code=400,
                detail="Only PDF files are supported"
            )

        # Step 1: Process PDF
        logger.info(f"[{process_id}] Starting PDF text extraction")
        pdf_result = await pdf_service.process_pdf(file)
        
        if not pdf_result["status"]:
            logger.error(f"[{process_id}] PDF processing failed: {pdf_result.get('error')}")
            raise HTTPException(
                status_code=500,
                detail=f"PDF processing failed: {pdf_result.get('error')}"
            )
        
        if not pdf_result.get("is_resume", False):
            logger.warning(f"[{process_id}] Document is not a resume")
            return JSONResponse(
                status_code=422,
                content={
                    "status": False,
                    "code": "NOT_RESUME",
                    "message": "The provided document does not appear to be a resume. Please ensure you're uploading a valid resume.",
                    "process_id": process_id
                }
            )

        # Step 2: Extract text and generate embedding
        logger.info(f"[{process_id}] Generating text embedding")
        embedding_result = await ai_service.get_embedding(pdf_result["cleaned_text"])
        
        if not embedding_result["status"]:
            logger.warning(f"[{process_id}] Embedding generation failed: {embedding_result.get('error')}")
            # Continue processing as this is not critical

        # Step 3: Extract structured information
        logger.info(f"[{process_id}] Extracting structured information")
        extraction_result = await ai_service.extract_resume_info(pdf_result["cleaned_text"])
        
        if not extraction_result["status"]:
            logger.error(f"[{process_id}] Information extraction failed: {extraction_result.get('error')}")
            raise HTTPException(
                status_code=500,
                detail=f"Information extraction failed: {extraction_result.get('error')}"
            )

        # Calculate processing time
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        logger.info(f"[{process_id}] Processing completed in {processing_time:.2f} seconds")

        # Construct response
        response_data = {
            "process_id": process_id,
            "status": ProcessingStatus.COMPLETED,
            "processing_time": processing_time,
            "raw_text": pdf_result["cleaned_text"],
            "extracted_info": extraction_result["data"],
            "vector_embedding": embedding_result.get("data", {}).get("embedding") if embedding_result["status"] else None,
            "links": pdf_result.get("links", []),
            "token_metrics": {
                "embedding_tokens": embedding_result.get("data", {}).get("token_count", 0) if embedding_result["status"] else 0,
                "extraction_tokens": extraction_result.get("token_count", 0)
            },
            "models_used": {
                "embedding": embedding_result.get("data", {}).get("embedding_model") if embedding_result["status"] else None,
                "extraction": extraction_result.get("model")
            }
        }

        # Schedule cleanup in background if needed
        if background_tasks:
            background_tasks.add_task(cleanup_temporary_files, process_id)

        logger.info(f"[{process_id}] Successfully completed resume parsing")
        return JSONResponse(content=response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[{process_id}] Unexpected error during resume parsing: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )

@router.get(
    "/status/{process_id}",
    response_model=ProcessingStatus
)
async def get_process_status(process_id: str):
    """
    Get the status of a resume processing request.
    
    Args:
        process_id: Unique identifier for the processing request
    
    Returns:
        Current status of the processing request
    """
    # Implementation for status checking
    # This could be expanded to check status from a cache or database
    pass

async def cleanup_temporary_files(process_id: str):
    """
    Cleanup temporary files created during processing.
    
    Args:
        process_id: Unique identifier for the processing request
    """
    logger.info(f"[{process_id}] Cleaning up temporary files")
    # Implementation for cleanup
    pass