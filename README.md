# MedDocs Assistant - AI-Powered Medical Document Analysis

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.121.1-009688.svg)](https://fastapi.tiangolo.com)
[![Google Gemini](https://img.shields.io/badge/Google-Gemini-4285F4.svg)](https://ai.google.dev/)

## Overview

MedDocs Assistant is a comprehensive AI-powered platform designed to help healthcare organizations manage, analyze, and extract insights from large collections of medical documents. The system supports multiple document formats (PDF, Word, Excel, Images) and provides intelligent Q&A capabilities with proper citations and structured report generation.

### Key Features

- **Multi-Format Document Processing**: Supports PDF, Word (.docx), Excel (.xlsx), and image files (PNG, JPG, TIFF, BMP)
- **AI-Powered Q&A**: Natural language queries with document-grounded responses using Google Gemini
- **Intelligent Report Generation**: Structured medical reports with customizable sections
- **Google Drive Integration**: Seamless import and access to Google Drive documents
- **Citation & References**: Automatic citation generation with clickable Google Drive links
- **Conversational Memory**: Multi-turn conversations with context retention
- **Vector Search**: Advanced semantic search using ChromaDB and sentence transformers
- **Modern Web Interface**: Responsive frontend with drag-and-drop file uploads
- **Docker Ready**: Containerized deployment with Docker Compose
- **Secure & Scalable**: Production-ready with authentication and rate limiting

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Frontend      │    │    Backend       │    │   External      │
│   (HTML/JS)     │◄──►│   (FastAPI)      │◄──►│   Services      │
│                 │    │                  │    │                 │
│ • File Upload   │    │ • Document Proc. │    │ • Google Gemini │
│ • Chat Interface│    │ • Vector Store   │    │ • Google Drive  │
│ • Report Gen.   │    │ • AI Integration │    │ • ChromaDB      │
│ • Google Drive  │    │ • Report Export  │    │          │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │    Database      │
                    │   (SQLite)       │
                    │                  │
                    │ • Documents      │
                    │ • Conversations  │
                    │ • Reports        │
                    │ • Citations      │
                    └──────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- Google API Key (for Gemini AI)
- Google Drive API credentials

### 1. Clone the Repository

```bash
git clone https://github.com/deepanshu-iitm/meddocs-assistant.git
cd meddocs-assistant
```

### 2. Environment Setup

```bash
# Google AI Configuration
GOOGLE_API_KEY=google_api_key

# Google Drive API Configuration
GOOGLE_DRIVE_CREDENTIALS_FILE=credentials.json
GOOGLE_DRIVE_TOKEN_FILE=token.json

# Database Configuration
DATABASE_URL=sqlite:///./meddocs.db

# File Upload Configuration
MAX_FILE_SIZE=50000000  # 50MB
UPLOAD_DIR=./uploads

# Vector Database Configuration
CHROMA_PERSIST_DIRECTORY=./chroma_db

# Report Generation
REPORTS_DIR=./reports
TEMP_DIR=./temp

# Security
SECRET_KEY=your_secret_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30


# Edit the .env file with your configuration
# Required: GOOGLE_API_KEY
# Optional: Google Drive credentials
```

### 3. Manual Installation

```bash
# Install backend dependencies
cd backend
pip install -r requirements.txt

# Start the backend server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Serve frontend (in another terminal)
cd ../frontend
python -m http.server 3000
```

### 4. Access the Application

- **Frontend**: http://localhost:3000 
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## Usage Guide

### Document Upload

1. Navigate to the **Documents** tab
2. Drag and drop files or click "Choose Files"
3. Supported formats: PDF, DOCX, XLSX, PNG, JPG, TIFF, BMP
4. Wait for processing to complete

### Google Drive Integration

1. Configure Google Drive API credentials
2. Go to **Google Drive** tab
3. Click "Load Google Drive Files"
4. Import desired documents

### AI Chat Interface

1. Navigate to the **Chat** tab
2. Ask questions about your uploaded documents
3. Receive AI-powered responses with citations
4. Continue multi-turn conversations

### Report Generation

1. Go to the **Reports** tab
2. Enter report title and select sections
3. Optionally filter specific documents
4. Generate and download PDF reports

## Configuration

### Google Drive Setup

1. Create a Google Cloud Project
2. Enable Google Drive API
3. Create service account credentials
4. Download `credentials.json`
5. Place in project root directory

## Tech Stack

### Backend
- **Framework**: FastAPI 0.121.1
- **AI/LLM**: Google Gemini 1.5 flash
- **Vector Database**: ChromaDB
- **Embeddings**: Sentence Transformers
- **Document Processing**: PyPDF2, python-docx, openpyxl, pytesseract
- **Database**: SQLite (SQLAlchemy ORM)
- **Report Generation**: ReportLab, WeasyPrint

### Frontend
- **Framework**: Vanilla JavaScript + Bootstrap 5
- **Styling**: Custom CSS with modern design
- **Icons**: Font Awesome 6
- **Features**: Responsive design, drag-and-drop, real-time chat


## API Endpoints

### Documents
- `POST /documents/upload` - Upload document
- `GET /documents` - List all documents
- `GET /documents/{id}` - Get document details
- `DELETE /documents/{id}` - Delete document

### Chat
- `POST /chat` - Send message to AI assistant
- `GET /chat/history/{session_id}` - Get conversation history

### Reports
- `POST /reports/generate` - Generate medical report
- `GET /reports` - List all reports
- `GET /reports/{id}/download` - Download report PDF

### Google Drive
- `GET /google-drive/files` - List Drive files
- `POST /google-drive/import/{file_id}` - Import Drive file

### System
- `GET /health` - Health check
- `GET /stats` - System statistics


**Built with ❤️ by Deepanshu Pathak**