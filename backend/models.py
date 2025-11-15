"""
Database models for MedDocs Assistant
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from pydantic import BaseModel, Field

Base = declarative_base()


class Document(Base):
    """Document model for storing uploaded documents"""
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_type = Column(String, nullable=False)  # pdf, docx, xlsx, image
    file_size = Column(Integer, nullable=False)
    upload_date = Column(DateTime, default=datetime.utcnow)
    is_google_drive = Column(Boolean, default=False)
    google_drive_id = Column(String, nullable=True)
    google_drive_url = Column(String, nullable=True)
    processing_status = Column(String, default="pending")  # pending, processing, completed, failed
    doc_metadata = Column(JSON, nullable=True)
    
    # Relationships
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")
    citations = relationship("Citation", back_populates="document")


class DocumentChunk(Base):
    """Document chunks for vector storage"""
    __tablename__ = "document_chunks"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    page_number = Column(Integer, nullable=True)
    section_title = Column(String, nullable=True)
    chunk_type = Column(String, default="text")  # text, table, image, chart
    chunk_metadata = Column(JSON, nullable=True)
    
    # Relationships
    document = relationship("Document", back_populates="chunks")


class Conversation(Base):
    """Conversation sessions for multi-turn chat"""
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    context = Column(JSON, nullable=True)  # Store conversation context
    
    # Relationships
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    """Individual messages in conversations"""
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    role = Column(String, nullable=False)  # user, assistant
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    msg_metadata = Column(JSON, nullable=True)
    
    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    citations = relationship("Citation", back_populates="message")


class Citation(Base):
    """Citations linking messages to document sources"""
    __tablename__ = "citations"
    
    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=False)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    chunk_id = Column(Integer, ForeignKey("document_chunks.id"), nullable=True)
    citation_text = Column(Text, nullable=False)
    relevance_score = Column(String, nullable=True)
    
    # Relationships
    message = relationship("Message", back_populates="citations")
    document = relationship("Document", back_populates="citations")


class Report(Base):
    """Generated medical reports"""
    __tablename__ = "reports"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    sections = Column(JSON, nullable=False)  # List of requested sections
    content = Column(JSON, nullable=False)  # Generated content by section
    file_path = Column(String, nullable=True)  # Path to generated PDF
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="pending")  # pending, generating, completed, failed
    report_metadata = Column(JSON, nullable=True)


# Pydantic models for API
class DocumentResponse(BaseModel):
    id: int
    filename: str
    original_filename: str
    file_type: str
    file_size: int
    upload_date: datetime
    is_google_drive: bool
    google_drive_url: Optional[str] = None
    processing_status: str
    doc_metadata: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class MessageRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class MessageResponse(BaseModel):
    id: int
    role: str
    content: str
    timestamp: datetime
    citations: List[Dict[str, Any]] = []
    session_id: str

    class Config:
        from_attributes = True


class ReportRequest(BaseModel):
    title: str
    sections: List[str] = Field(..., description="List of sections to include in report")
    document_ids: Optional[List[int]] = Field(None, description="Specific documents to use")


class ReportResponse(BaseModel):
    id: int
    title: str
    sections: List[str]
    status: str
    file_path: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class CitationResponse(BaseModel):
    document_name: str
    document_id: int
    chunk_content: str
    page_number: Optional[int] = None
    google_drive_url: Optional[str] = None
    relevance_score: Optional[float] = None
