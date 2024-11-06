from typing import Dict, List, Optional, Union
from enum import Enum
from pydantic import BaseModel, Field

class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class TokenMetrics(BaseModel):
    embedding_tokens: int = Field(0, description="Number of tokens used for embedding generation")
    extraction_tokens: int = Field(0, description="Number of tokens used for information extraction")

class ModelsUsed(BaseModel):
    embedding: Optional[str] = Field(None, description="Model used for embedding generation")
    extraction: Optional[str] = Field(None, description="Model used for information extraction")

class ResumeResponse(BaseModel):
    process_id: str = Field(..., description="Unique identifier for this processing request")
    status: ProcessingStatus = Field(..., description="Current status of the processing")
    processing_time: float = Field(..., description="Time taken to process the resume in seconds")
    raw_text: str = Field(..., description="Cleaned text extracted from the PDF")
    extracted_info: Dict = Field(..., description="Structured information extracted from the resume")
    vector_embedding: Optional[List[float]] = Field(None, description="Vector embedding of the resume text")
    links: List[str] = Field(default_factory=list, description="URLs extracted from the resume")
    token_metrics: TokenMetrics = Field(..., description="Token usage metrics")
    models_used: ModelsUsed = Field(..., description="Models used in processing")

class ResumeProcessingError(BaseModel):
    detail: str = Field(..., description="Error description")