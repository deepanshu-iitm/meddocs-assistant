from fastapi import FastAPI, File, UploadFile, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import uuid
import logging
from datetime import datetime
import asyncio

# Import local modules
from config import settings
from database import get_db, init_db
from models import (
    Document, DocumentChunk, Conversation, Message, Citation, Report,
    DocumentResponse, MessageRequest, MessageResponse, ReportRequest, ReportResponse
)
from services.document_processor import DocumentProcessor
from services.vector_store import VectorStore
from services.google_drive import GoogleDriveService
from services.gemini_ai import GeminiAIService
from services.report_generator import ReportGenerator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="MedDocs Assistant Backend",
    description="AI-powered medical document assistant with Q&A and report generation",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
document_processor = DocumentProcessor()
vector_store = VectorStore()
google_drive_service = GoogleDriveService()
gemini_ai = GeminiAIService()
report_generator = ReportGenerator()

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    """Initialize database and services on startup"""
    try:
        init_db()
        logger.info("Database initialized successfully")
        
        # Test Google Drive connection
        if google_drive_service.is_authenticated():
            logger.info("Google Drive service authenticated")
        else:
            logger.warning("Google Drive service not authenticated")
            
    except Exception as e:
        logger.error(f"Error during startup: {e}")

@app.get("/")
def read_root():
    """Root endpoint with API information"""
    return {
        "message": "MedDocs Assistant Backend is running successfully!",
        "version": "1.0.0",
        "endpoints": {
            "documents": "/documents",
            "chat": "/chat",
            "reports": "/reports",
            "google_drive": "/google-drive"
        }
    }

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "database": "connected",
            "vector_store": "connected",
            "google_drive": "connected" if google_drive_service.is_authenticated() else "disconnected",
            "gemini_ai": "connected"
        }
    }

# Document Management Endpoints
@app.post("/documents/upload", response_model=DocumentResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload and process a medical document"""
    try:
        # Validate file type
        allowed_types = ['pdf', 'docx', 'doc', 'xlsx', 'xls', 'png', 'jpg', 'jpeg', 'tiff', 'bmp']
        file_extension = file.filename.split('.')[-1].lower()
        
        if file_extension not in allowed_types:
            raise HTTPException(status_code=400, detail=f"File type {file_extension} not supported")
        
        # Check file size
        content = await file.read()
        if len(content) > settings.max_file_size:
            raise HTTPException(status_code=400, detail="File size exceeds maximum limit")
        
        # Generate unique filename
        unique_filename = f"{uuid.uuid4()}_{file.filename}"
        file_path = os.path.join(settings.upload_dir, unique_filename)
        
        # Save file
        with open(file_path, 'wb') as f:
            f.write(content)
        
        # Create database record
        db_document = Document(
            filename=unique_filename,
            original_filename=file.filename,
            file_path=file_path,
            file_type=file_extension,
            file_size=len(content),
            processing_status="pending"
        )
        db.add(db_document)
        db.commit()
        db.refresh(db_document)
        
        # Process document in background
        background_tasks.add_task(process_document_background, db_document.id, file_path, file_extension)
        
        return DocumentResponse.from_orm(db_document)
        
    except Exception as e:
        logger.error(f"Error uploading document: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/documents", response_model=List[DocumentResponse])
def get_documents(db: Session = Depends(get_db)):
    """Get list of all uploaded documents"""
    try:
        documents = db.query(Document).all()
        return [DocumentResponse.from_orm(doc) for doc in documents]
    except Exception as e:
        logger.error(f"Error getting documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/documents/{document_id}", response_model=DocumentResponse)
def get_document(document_id: int, db: Session = Depends(get_db)):
    """Get specific document by ID"""
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        return DocumentResponse.from_orm(document)
    except Exception as e:
        logger.error(f"Error getting document {document_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/documents/{document_id}")
def delete_document(document_id: int, db: Session = Depends(get_db)):
    """Delete a document and its chunks"""
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Delete from vector store
        vector_store.delete_document_chunks(document_id)
        
        # Delete file
        if os.path.exists(document.file_path):
            os.remove(document.file_path)
        
        # Delete from database
        db.delete(document)
        db.commit()
        
        return {"message": "Document deleted successfully"}
        
    except Exception as e:
        logger.error(f"Error deleting document {document_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Chat and Q&A Endpoints
@app.post("/chat", response_model=MessageResponse)
async def chat_with_assistant(
    request: MessageRequest,
    db: Session = Depends(get_db)
):
    """Chat with the medical document assistant"""
    try:
        # Get or create conversation
        session_id = request.session_id or str(uuid.uuid4())
        conversation = db.query(Conversation).filter(Conversation.session_id == session_id).first()
        
        if not conversation:
            conversation = Conversation(session_id=session_id)
            db.add(conversation)
            db.commit()
            db.refresh(conversation)
        
        # Save user message
        user_message = Message(
            conversation_id=conversation.id,
            role="user",
            content=request.message
        )
        db.add(user_message)
        db.commit()
        
        # Search for relevant document chunks
        relevant_chunks = vector_store.search_similar_chunks(
            query=request.message,
            n_results=10,
            min_similarity=0.3
        )
        
        # Get conversation history
        recent_messages = db.query(Message).filter(
            Message.conversation_id == conversation.id
        ).order_by(Message.timestamp.desc()).limit(10).all()
        
        conversation_history = []
        for msg in reversed(recent_messages[:-1]):  # Exclude current user message
            conversation_history.append({
                'role': msg.role,
                'content': msg.content
            })
        
        # Generate response using Gemini AI
        ai_response = gemini_ai.answer_question(
            question=request.message,
            document_chunks=relevant_chunks,
            conversation_history=conversation_history
        )
        
        # Save assistant message
        assistant_message = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=ai_response['answer'],
            msg_metadata={
                'confidence': ai_response['confidence'],
                'sources_used': ai_response['sources_used']
            }
        )
        db.add(assistant_message)
        db.commit()
        db.refresh(assistant_message)
        
        # Save citations
        citations_data = []
        for citation in ai_response['citations']:
            # Get document info
            document = db.query(Document).filter(Document.id == citation['document_id']).first()
            if document:
                db_citation = Citation(
                    message_id=assistant_message.id,
                    document_id=citation['document_id'],
                    citation_text=f"Document: {document.original_filename}",
                    relevance_score=str(citation.get('relevance_score', 0))
                )
                db.add(db_citation)
                
                citation_info = {
                    'document_name': document.original_filename,
                    'document_id': document.id,
                    'pages': citation.get('pages', []),
                    'sections': citation.get('sections', []),
                    'google_drive_url': document.google_drive_url,
                    'relevance_score': citation.get('relevance_score', 0)
                }
                citations_data.append(citation_info)
        
        db.commit()
        
        # Prepare response
        response = MessageResponse(
            id=assistant_message.id,
            role=assistant_message.role,
            content=assistant_message.content,
            timestamp=assistant_message.timestamp,
            citations=citations_data,
            session_id=session_id
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error in chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Report Generation Endpoints
@app.post("/reports/generate", response_model=ReportResponse)
async def generate_report(
    request: ReportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Generate a structured medical report"""
    try:
        # Create report record
        db_report = Report(
            title=request.title,
            sections=request.sections,
            content={},
            status="pending"
        )
        db.add(db_report)
        db.commit()
        db.refresh(db_report)
        
        # Generate report in background
        background_tasks.add_task(
            generate_report_background,
            db_report.id,
            request.title,
            request.sections,
            request.document_ids
        )
        
        return ReportResponse.from_orm(db_report)
        
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/reports", response_model=List[ReportResponse])
def get_reports(db: Session = Depends(get_db)):
    """Get list of all generated reports"""
    try:
        reports = db.query(Report).order_by(Report.created_at.desc()).all()
        return [ReportResponse.from_orm(report) for report in reports]
    except Exception as e:
        logger.error(f"Error getting reports: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/reports/{report_id}/download")
def download_report(report_id: int, db: Session = Depends(get_db)):
    """Download report as PDF"""
    try:
        report = db.query(Report).filter(Report.id == report_id).first()
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
        
        if not report.file_path or not os.path.exists(report.file_path):
            raise HTTPException(status_code=404, detail="Report file not found")
        
        return FileResponse(
            path=report.file_path,
            filename=f"{report.title.replace(' ', '_')}.pdf",
            media_type="application/pdf"
        )
        
    except Exception as e:
        logger.error(f"Error downloading report {report_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Background Tasks
async def process_document_background(document_id: int, file_path: str, file_type: str):
    """Background task to process uploaded documents"""
    try:
        # Get database session
        from database import SessionLocal
        db = SessionLocal()
        
        try:
            # Update status to processing
            document = db.query(Document).filter(Document.id == document_id).first()
            if document:
                document.processing_status = "processing"
                db.commit()
            
            # Process document
            processed_content = document_processor.process_document(file_path, file_type)
            
            # Extract and chunk content
            full_text = processed_content.get('text', '')
            chunks = document_processor.chunk_content(full_text, {
                'document_id': document_id,
                'file_type': file_type,
                'doc_metadata': processed_content.get('doc_metadata', {})
            })
            
            # Add chunks to database
            for chunk_data in chunks:
                db_chunk = DocumentChunk(
                    document_id=document_id,
                    chunk_index=chunk_data['chunk_index'],
                    content=chunk_data['content'],
                    chunk_type=chunk_data.get('chunk_type', 'text'),
                    chunk_metadata=chunk_data.get('chunk_metadata', {})
                )
                db.add(db_chunk)
            
            # Add to vector store
            vector_store.add_document_chunks(document_id, chunks)
            
            # Update document status and doc_metadata
            if document:
                document.processing_status = "completed"
                document.doc_metadata = processed_content.get('doc_metadata', {})
                db.commit()
            
            logger.info(f"Successfully processed document {document_id}")
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error processing document {document_id}: {e}")
        
        # Update status to failed
        from database import SessionLocal
        db = SessionLocal()
        try:
            document = db.query(Document).filter(Document.id == document_id).first()
            if document:
                document.processing_status = "failed"
                db.commit()
        finally:
            db.close()

async def generate_report_background(
    report_id: int,
    title: str,
    sections: List[str],
    document_ids: Optional[List[int]] = None
):
    """Background task to generate medical reports"""
    try:
        from database import SessionLocal
        db = SessionLocal()
        
        try:
            # Update status to generating
            report = db.query(Report).filter(Report.id == report_id).first()
            if report:
                report.status = "generating"
                db.commit()
            
            # Generate each section
            section_content = {}
            
            for section_name in sections:
                # Search for relevant content for this section
                search_query = f"{section_name} medical findings data"
                relevant_chunks = vector_store.search_similar_chunks(
                    query=search_query,
                    n_results=15,
                    document_ids=document_ids,
                    min_similarity=0.2
                )
                
                # Generate section content
                section_data = gemini_ai.generate_report_section(
                    section_name=section_name,
                    document_chunks=relevant_chunks
                )
                
                section_content[section_name] = section_data
            
            # Generate PDF report
            pdf_path = report_generator.generate_report(
                title=title,
                sections=section_content,
                metadata={
                    'generated_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'documents_used': len(document_ids) if document_ids else 'All available',
                    'report_type': 'Medical Analysis Report'
                }
            )
            
            # Update report with results
            if report:
                report.content = section_content
                report.file_path = pdf_path
                report.status = "completed"
                db.commit()
            
            logger.info(f"Successfully generated report {report_id}")
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error generating report {report_id}: {e}")
        
        # Update status to failed
        from database import SessionLocal
        db = SessionLocal()
        try:
            report = db.query(Report).filter(Report.id == report_id).first()
            if report:
                report.status = "failed"
                db.commit()
        finally:
            db.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)