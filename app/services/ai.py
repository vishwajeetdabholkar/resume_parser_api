from typing import Dict, Any, Optional
import json
from datetime import datetime
import time

from openai import OpenAI
import tiktoken
from loguru import logger
from pydantic import BaseModel, Field

class AIServiceConfig(BaseModel):
    """Configuration settings for AI Service."""
    api_key: str
    default_model: str = "gpt-3.5-turbo-0125"
    embedding_model: str = "text-embedding-ada-002"
    max_retries: int = 3
    timeout: float = 30.0
    max_tokens: int = 2000
    temperature: float = 0.1
    generate_embeddings: bool = False
    debug_mode: bool = False

class AIService:
    """Service for AI-powered resume processing and analysis."""
    
    def __init__(self, config: AIServiceConfig):
        """Initialize AI service with OpenAI client and configuration."""
        self.config = config
        self.client = OpenAI(api_key=config.api_key)
        self.session_id = f"ai_service_{int(time.time())}"
        
        self.metrics = {
            "total_tokens": 0,
            "api_calls": 0,
            "errors": 0
        }
        
        logger.info(f"Initialized AI Service with session ID: {self.session_id}")

    def _is_fresher(self, extracted_info: Dict) -> bool:
        """Determine if candidate is a fresher based on experience."""
        total_months = extracted_info.get("total_experience_in_months", 0)
        return total_months < 12  # Less than 1 year = fresher

    def _count_tokens(self, text: str, model: str) -> int:
        try:
            encoding = tiktoken.encoding_for_model(model)
            token_count = len(encoding.encode(text))
            self.metrics["total_tokens"] += token_count
            return token_count
        except Exception as e:
            logger.error(f"Token counting failed: {e}")
            return 0

    def _validate_json_structure(self, json_str: str) -> Dict:
        """Validate and clean JSON response."""
        try:
            # First try direct parsing
            return json.loads(json_str)
        except json.JSONDecodeError:
            logger.debug("Initial JSON parsing failed, attempting cleanup")
            try:
                # Try to extract JSON from the response if it's wrapped in other text
                json_start = json_str.find('{')
                json_end = json_str.rfind('}') + 1
                if json_start >= 0 and json_end > 0:
                    clean_json = json_str[json_start:json_end]
                    return json.loads(clean_json)
                raise ValueError("No valid JSON structure found")
            except Exception as e:
                logger.error(f"JSON cleanup failed: {e}")
                raise

    async def get_embedding(self, text: str) -> Dict[str, Any]:
        """Generate embeddings for text if enabled in config."""
        if not self.config.generate_embeddings:
            logger.debug("Embedding generation is disabled")
            return {
                "status": False,
                "error": "Embedding generation is disabled",
                "token_count": 0,
                "embedding_model": self.config.embedding_model
            }

        try:
            text = text.replace("\n", " ")
            token_count = self._count_tokens(text, self.config.embedding_model)
            logger.info(f"Generating embeddings for {token_count} tokens")

            response = self.client.embeddings.create(
                input=[text],
                model=self.config.embedding_model
            )
            embedding = response.data[0].embedding

            return {
                "status": True,
                "data": {
                    "embedding": embedding,
                    "embedding_model": self.config.embedding_model,
                    "token_count": token_count
                }
            }
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            return {
                "status": False,
                "error": str(e),
                "token_count": token_count if 'token_count' in locals() else 0,
                "embedding_model": self.config.embedding_model
            }

    async def extract_resume_info(self, resume_text: str) -> Dict[str, Any]:
        """Extract structured information from resume text."""
        try:
            token_count = self._count_tokens(resume_text, self.config.default_model)
            logger.info(f"Extracting resume info, tokens: {token_count}")
            
            system_prompt = """You are an expert resume parser. Your task is to extract information from resumes and return it in a specific JSON format.
            - ONLY return the JSON object, no other text.
            - All dates must be in YYYY-MM format.
            - If a value is not found, use appropriate default values ('Not Available' for strings, [] for arrays).
            - Ensure all JSON keys and values are properly quoted.
            - Boolean values must be true or false (lowercase).
            - Numbers must not be in quotes."""

            prompt = """Parse the following resume and return a JSON object with this exact structure:
            {
                "name": "string",
                "email": ["string"],
                "mobile": ["string"],
                "address": {
                    "city": "string",
                    "state": "string",
                    "country": "string"
                },
                "skills": ["string"],
                "companies": [{
                    "company_name": "string",
                    "start_date": {
                        "year": "YYYY",
                        "month": "MM"
                    },
                    "end_date": {
                        "year": "YYYY",
                        "month": "MM"
                    },
                    "designation": "string",
                    "is_current": boolean
                }],
                "linkedin_url": "string",
                "github_url": "string",
                "education": [{
                    "college_name": "string",
                    "start_year": "YYYY",
                    "end_year": "YYYY",
                    "description": "string"
                }],
                "certifications": ["string"],
                "profile_name": "string",
                "achievements": [{
                    "year": "YYYY",
                    "title": "string",
                    "description": "string"
                }]
            }"""

            self.metrics["api_calls"] += 1
            completion = self.client.chat.completions.create(
                model=self.config.default_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                    {"role": "user", "content": f"Resume text to parse:\n{resume_text}"}
                ],
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                response_format={ "type": "json_object" }  # Force JSON response
            )

            response_text = completion.choices[0].message.content
            logger.debug(f"Raw API response: {response_text[:200]}...")  # Log first 200 chars
            
            extracted_info = self._validate_json_structure(response_text)

            # Process experience dates
            if "companies" in extracted_info:
                total_experience = 0
                current_date = datetime.now()
                
                for company in extracted_info["companies"]:
                    try:
                        start_date = company.get("start_date", {})
                        end_date = company.get("end_date", {})
                        is_current = company.get("is_current", False)

                        if is_current:
                            end_year = current_date.year
                            end_month = current_date.month
                        else:
                            end_year = int(end_date.get("year", 0))
                            end_month = int(end_date.get("month", 0))

                        start_year = int(start_date.get("year", 0))
                        start_month = int(start_date.get("month", 0))

                        if all([start_year, start_month, end_year, end_month]):
                            months = (end_year - start_year) * 12 + (end_month - start_month)
                            total_experience += max(0, months)
                            company["total_experience_in_months"] = max(0, months)

                    except Exception as e:
                        logger.warning(f"Failed to process company dates: {e}")
                        company["total_experience_in_months"] = 0

                extracted_info["total_experience_in_months"] = total_experience

            is_fresher = self._is_fresher(extracted_info)
            extracted_info["is_fresher"] = is_fresher
            
            return {
                "status": True,
                "data": extracted_info,
                "token_count": token_count,
                "model": self.config.default_model
            }

        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {e}")
            self.metrics["errors"] += 1
            return {
                "status": False,
                "error": "Failed to parse extracted information",
                "token_count": token_count,
                "model": self.config.default_model
            }
        except Exception as e:
            logger.error(f"Resume info extraction failed: {e}")
            self.metrics["errors"] += 1
            return {
                "status": False,
                "error": str(e),
                "token_count": token_count if 'token_count' in locals() else 0,
                "model": self.config.default_model
            }

    def get_metrics(self) -> Dict[str, Any]:
        """Return service metrics."""
        return {
            **self.metrics,
            "session_id": self.session_id,
            "success_rate": (
                (self.metrics["api_calls"] - self.metrics["errors"]) 
                / self.metrics["api_calls"] if self.metrics["api_calls"] > 0 else 0
            )
        }