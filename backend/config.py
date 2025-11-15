"""
Configuration settings for MedDocs Assistant
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""
    
    # Google AI Configuration
    google_api_key: str
    
    # Google Drive API Configuration
    google_drive_credentials_file: str = "credentials.json"
    google_drive_token_file: str = "token.json"
    
    # Database Configuration
    database_url: str = "sqlite:///./meddocs.db"
    
    # File Upload Configuration
    max_file_size: int = 50000000  # 50MB
    upload_dir: str = "./uploads"
    
    # Vector Database Configuration
    chroma_persist_directory: str = "./chroma_db"
    
    # Report Generation
    reports_dir: str = "./reports"
    temp_dir: str = "./temp"
    
    # Security
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Gemini Model Configuration
    gemini_model: str = "gemini-1.5-flash"
    gemini_temperature: float = 0.1
    gemini_max_tokens: int = 8192
    
    # Embedding Configuration
    embedding_model: str = "all-MiniLM-L6-v2"
    chunk_size: int = 1000
    chunk_overlap: int = 200
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Create settings instance
settings = Settings()

# Ensure directories exist
os.makedirs(settings.upload_dir, exist_ok=True)
os.makedirs(settings.reports_dir, exist_ok=True)
os.makedirs(settings.temp_dir, exist_ok=True)
os.makedirs(settings.chroma_persist_directory, exist_ok=True)
