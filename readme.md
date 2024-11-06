# Resume Parser API

A robust FastAPI-based service that processes resumes in PDF format, extracting structured information and generating text embeddings. This API combines PDF processing capabilities with AI-powered information extraction to convert unstructured resume data into structured, analyzable formats.

## Features

- PDF text extraction with OCR support
- Resume validation and verification
- Structured information extraction using OpenAI
- Optional text embedding generation
- Hyperlink extraction
- Table and image processing
- Experience calculation and fresher detection
- Comprehensive logging and error handling
- Configurable through environment variables

## Flow of the code:
```
|----------------|     |----------------|     |----------------|
|   PDF Upload   | --> |  PDF Service   | --> |   Validation   |
|----------------|     |----------------|     |----------------|
                           |      ^
                           v      |
                      |----------------|
                      |  OCR Service   |
                      |----------------|
                           |      ^
                           v      |
|----------------|     |----------------|     |----------------|
|   AI Service   | <-- | Text Process   | --> |   Embedding    |
|----------------|     |----------------|     |   Generation   |
       |                                      |----------------|
       v
|----------------|     |----------------|
|  Structure     | --> |    Final       |
|  Generation    |     |   Response     |
|----------------|     |----------------|
```

## Project Structure

```
resume_parser_api/
├── app/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py        # Configuration management
│   │   ├── dependencies.py  # Service dependencies
│   │   └── logging.py       # Logging setup
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes/
│   │       ├── __init__.py
│   │       └── resume.py    # API endpoints
│   ├── services/
│   │   ├── __init__.py
│   │   ├── pdf.py          # PDF processing service
│   │   └── ai.py           # AI service for OpenAI interactions
│   └── models/
│       ├── __init__.py
│       └── schemas.py       # Data models and schemas
├── Tesseract-OCR/          # Tesseract binaries
├── poppler-23.11.0/        # Poppler binaries
├── logs/                   # Application logs
├── main.py                 # Application entry point
├── .env                    # Environment configuration
└── requirements.txt        # Project dependencies
```

## Core Components

### 1. PDF Service (`app/services/pdf.py`)
- Handles PDF file processing
- Extracts text, tables, and images
- Performs OCR on image-based content
- Validates if the document is a resume
- Extracts hyperlinks from the document

### 2. AI Service (`app/services/ai.py`)
- Manages OpenAI API interactions
- Generates text embeddings
- Extracts structured information from resume text
- Calculates total experience
- Determines fresher/experienced status
- Handles token counting and rate limiting

### 3. Configuration (`app/core/config.py`)
- Manages environment variables
- Configures application settings
- Sets up logging and paths
- Handles external tool configurations

### 4. API Routes (`app/api/routes/resume.py`)
- Defines API endpoints
- Handles file uploads
- Orchestrates services
- Manages response formatting
- Implements error handling

## Development Setup

### Prerequisites
- Python 3.8 or higher
- Tesseract OCR
- Poppler
- OpenAI API key

### Environment Setup

1. Create and activate virtual environment:

For Windows:
```powershell
# Create virtual environment
python -m venv resume_api_env

# Activate virtual environment
.\resume_api_env\Scripts\activate
```

For Linux/Mac:
```bash
# Create virtual environment
python -m venv resume_api_env

# Activate virtual environment
source resume_api_env/bin/activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up external tools:

- Download [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki)
- Download [Poppler](https://github.com/oschwartz10612/poppler-windows/releases/)
- Place them in the project root directory under `Tesseract-OCR` and `poppler-23.11.0` respectively

4. Create `.env` file:
```env
# OpenAI Configuration
OPENAI_API_KEY=your_api_key_here

# Application Configuration
DEBUG=True
LOG_LEVEL=INFO

# API Settings
MAX_RETRIES=3
REQUEST_TIMEOUT=30.0
MAX_FILE_SIZE=10485760

# Feature Flags
ENABLE_OCR=True
ENABLE_TABLE_EXTRACTION=True
ENABLE_LINK_EXTRACTION=True
GENERATE_EMBEDDINGS=False
ENABLE_BACKGROUND_TASKS=True
```

5. Start the application:
```bash
python main.py
```

The API will be available at `http://localhost:8000`

## API Documentation

Once running, access the interactive API documentation at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Main Endpoint

`POST /api/v1/resume/parse`
- Accepts PDF file uploads
- Returns structured resume information
- Validates resume content
- Optional embedding generation

Example response structure:
```json
{
    "status": true,
    "process_id": "unique-id",
    "structured_data": {
        "name": "John Doe",
        "email": ["john@example.com"],
        "skills": ["Python", "FastAPI", "AI"],
        "is_fresher": false,
        "total_experience_in_months": 36
        // ... other extracted information
    },
    "embeddings": [...],  // If enabled
    "token_metrics": {
        "extraction": 1000,
        "embedding": 500
    }
}
```

## Error Handling

The API implements comprehensive error handling:
- Invalid file types (400)
- Non-resume documents (422)
- Processing errors (500)
- Rate limiting
- Token usage tracking

## Logging

Detailed logging is implemented throughout the application:
- Request tracking with process IDs
- Error logging with stack traces
- Performance metrics
- Token usage tracking
- Service status logging

Logs are stored in the `logs/` directory and rotated automatically.

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

Make sure to:
- Follow the existing code style
- Add tests if applicable
- Update documentation as needed
- Run tests before submitting

