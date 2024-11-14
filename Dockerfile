FROM ubuntu:22.04

# Install system dependencies and cleanup
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    libtesseract-dev \
    libleptonica-dev \
    python3 \
    python3-pip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies including propeller
RUN pip3 install -r requirements.txt

# Copy application files
COPY . .

# Environment variables for Tesseract
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/4.00/tessdata

# Expose port 8080
EXPOSE 8080

# Default command
CMD ["python3", "-m", "http.server", "8080"]
