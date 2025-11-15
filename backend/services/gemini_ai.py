"""
Google Gemini AI service for Q&A and report generation
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
import google.generativeai as genai
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import HumanMessage, SystemMessage, AIMessage
from config import settings
import json
import re

logger = logging.getLogger(__name__)


class GeminiAIService:
    """Service for interacting with Google Gemini AI for medical document Q&A"""
    
    def __init__(self):
        # Configure Gemini
        genai.configure(api_key=settings.google_api_key)
        
        # Initialize LangChain Gemini model
        self.llm = ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            temperature=settings.gemini_temperature,
            max_tokens=settings.gemini_max_tokens,
            google_api_key=settings.google_api_key
        )
        
        # System prompts for different tasks
        self.qa_system_prompt = """You are a medical document assistant. Your role is to answer questions based ONLY on the provided medical documents. 

CRITICAL RULES:
1. ONLY use information that is explicitly stated in the provided document chunks
2. If the answer cannot be found in the documents, clearly state "I cannot find this information in the provided documents"
3. NEVER make up or infer medical information not explicitly stated
4. Always cite which document and section your answer comes from
5. Be precise and factual in your responses
6. For medical data, preserve exact numbers, dates, and measurements as they appear

When answering:
- Start with a direct answer if found in documents
- Cite the source document(s) and relevant sections
- If partial information is available, clearly state what is and isn't available
- Use professional medical language when appropriate"""

        self.report_system_prompt = """You are a medical report generator. Your task is to create structured medical reports using ONLY the information from provided documents.

CRITICAL RULES:
1. Extract content EXACTLY as it appears in source documents
2. Do NOT paraphrase or rewrite unless explicitly asked for a summary
3. Preserve all medical data, numbers, dates, and measurements exactly
4. Organize content into the requested sections
5. Clearly indicate which document each piece of information comes from
6. If a requested section has no available data, state this clearly

For each section:
- Extract relevant content verbatim from source documents
- Maintain original formatting for tables and structured data
- Include document citations for all content
- Only summarize when explicitly requested"""

    def answer_question(
        self, 
        question: str, 
        document_chunks: List[Dict[str, Any]], 
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Answer a question based on document chunks
        
        Args:
            question: User's question
            document_chunks: Relevant document chunks from vector search
            conversation_history: Previous conversation messages
            
        Returns:
            Dictionary with answer, citations, and metadata
        """
        try:
            if not document_chunks:
                return {
                    'answer': "I cannot find any relevant information in the provided documents to answer your question.",
                    'citations': [],
                    'confidence': 0.0,
                    'sources_used': 0
                }
            
            # Prepare context from document chunks
            context = self._prepare_context(document_chunks)
            
            # Build conversation messages
            messages = [SystemMessage(content=self.qa_system_prompt)]
            
            # Add conversation history if available
            if conversation_history:
                for msg in conversation_history[-6:]:  # Last 6 messages for context
                    if msg['role'] == 'user':
                        messages.append(HumanMessage(content=msg['content']))
                    elif msg['role'] == 'assistant':
                        messages.append(AIMessage(content=msg['content']))
            
            # Add current question with context
            user_message = f"""Context from medical documents:
{context}

Question: {question}

Please answer based only on the information provided in the context above. Include specific citations."""
            
            messages.append(HumanMessage(content=user_message))
            
            # Get response from Gemini
            response = self.llm.invoke(messages)
            answer = response.content
            
            # Extract citations and analyze response
            citations = self._extract_citations(answer, document_chunks)
            confidence = self._calculate_confidence(answer, document_chunks)
            
            return {
                'answer': answer,
                'citations': citations,
                'confidence': confidence,
                'sources_used': len(set(chunk['document_id'] for chunk in document_chunks))
            }
            
        except Exception as e:
            logger.error(f"Error generating answer: {e}")
            return {
                'answer': "I encountered an error while processing your question. Please try again.",
                'citations': [],
                'confidence': 0.0,
                'sources_used': 0
            }
    
    def generate_report_section(
        self, 
        section_name: str, 
        document_chunks: List[Dict[str, Any]], 
        section_requirements: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a specific section of a medical report
        
        Args:
            section_name: Name of the section to generate
            document_chunks: Relevant document chunks
            section_requirements: Specific requirements for this section
            
        Returns:
            Dictionary with section content and metadata
        """
        try:
            if not document_chunks:
                return {
                    'content': f"No relevant information found for {section_name} section.",
                    'citations': [],
                    'tables': [],
                    'images': []
                }
            
            # Prepare context
            context = self._prepare_context(document_chunks)
            
            # Build prompt for section generation
            prompt = f"""Generate the "{section_name}" section for a medical report using the provided context.

{self.report_system_prompt}

Context from medical documents:
{context}

Section Requirements: {section_requirements or f'Extract all relevant information for {section_name}'}

Instructions:
1. Extract content exactly as it appears in the source documents
2. Organize information clearly under the "{section_name}" heading
3. Include all relevant tables, data, and measurements
4. Cite source documents for each piece of information
5. Maintain professional medical report formatting

Generate the section content now:"""

            response = self.llm.invoke([HumanMessage(content=prompt)])
            content = response.content
            
            # Extract structured elements
            citations = self._extract_citations(content, document_chunks)
            tables = self._extract_tables_from_chunks(document_chunks)
            images = self._extract_images_from_chunks(document_chunks)
            
            return {
                'content': content,
                'citations': citations,
                'tables': tables,
                'images': images
            }
            
        except Exception as e:
            logger.error(f"Error generating report section {section_name}: {e}")
            return {
                'content': f"Error generating {section_name} section.",
                'citations': [],
                'tables': [],
                'images': []
            }
    
    def summarize_content(self, content: str, summary_type: str = "concise") -> str:
        """
        Generate a summary of medical content
        
        Args:
            content: Content to summarize
            summary_type: Type of summary (concise, detailed, executive)
            
        Returns:
            Summary text
        """
        try:
            prompt = f"""Summarize the following medical content. Create a {summary_type} summary that:
1. Captures key medical findings and information
2. Maintains accuracy of all medical data
3. Uses professional medical language
4. Highlights important clinical information

Content to summarize:
{content}

Generate a {summary_type} summary:"""

            response = self.llm.invoke([HumanMessage(content=prompt)])
            return response.content
            
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return "Error generating summary."
    
    def _prepare_context(self, document_chunks: List[Dict[str, Any]]) -> str:
        """Prepare context string from document chunks"""
        context_parts = []
        
        for i, chunk in enumerate(document_chunks):
            doc_id = chunk.get('document_id', 'Unknown')
            page_num = chunk.get('page_number', 'Unknown')
            section = chunk.get('section_title', '')
            content = chunk.get('content', '')
            
            context_part = f"""[Document {doc_id}, Page {page_num}"""
            if section:
                context_part += f", Section: {section}"
            context_part += f"]\n{content}\n"
            
            context_parts.append(context_part)
        
        return "\n---\n".join(context_parts)
    
    def _extract_citations(self, answer: str, document_chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract citation information from answer and chunks"""
        citations = []
        
        # Create a mapping of document IDs to chunk info
        doc_info = {}
        for chunk in document_chunks:
            doc_id = chunk.get('document_id')
            if doc_id not in doc_info:
                doc_info[doc_id] = {
                    'document_id': doc_id,
                    'chunks': [],
                    'pages': set(),
                    'sections': set()
                }
            
            doc_info[doc_id]['chunks'].append(chunk)
            if chunk.get('page_number'):
                doc_info[doc_id]['pages'].add(chunk['page_number'])
            if chunk.get('section_title'):
                doc_info[doc_id]['sections'].add(chunk['section_title'])
        
        # Create citations for each document used
        for doc_id, info in doc_info.items():
            citation = {
                'document_id': doc_id,
                'pages': sorted(list(info['pages'])) if info['pages'] else [],
                'sections': list(info['sections']) if info['sections'] else [],
                'chunk_count': len(info['chunks']),
                'relevance_score': sum(chunk.get('similarity_score', 0) for chunk in info['chunks']) / len(info['chunks'])
            }
            citations.append(citation)
        
        return citations
    
    def _calculate_confidence(self, answer: str, document_chunks: List[Dict[str, Any]]) -> float:
        """Calculate confidence score for the answer"""
        if "cannot find" in answer.lower() or "not available" in answer.lower():
            return 0.0
        
        # Base confidence on similarity scores and number of sources
        if document_chunks:
            avg_similarity = sum(chunk.get('similarity_score', 0) for chunk in document_chunks) / len(document_chunks)
            source_factor = min(len(set(chunk['document_id'] for chunk in document_chunks)) / 3, 1.0)
            return min(avg_similarity * source_factor, 1.0)
        
        return 0.5
    
    def _extract_tables_from_chunks(self, document_chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract table information from document chunks"""
        tables = []
        
        for chunk in document_chunks:
            if chunk.get('chunk_type') == 'table' or 'table' in chunk.get('metadata', {}):
                table_info = {
                    'document_id': chunk.get('document_id'),
                    'page_number': chunk.get('page_number'),
                    'content': chunk.get('content', ''),
                    'metadata': chunk.get('metadata', {})
                }
                tables.append(table_info)
        
        return tables
    
    def _extract_images_from_chunks(self, document_chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract image information from document chunks"""
        images = []
        
        for chunk in document_chunks:
            if chunk.get('chunk_type') == 'image' or 'image' in chunk.get('metadata', {}):
                image_info = {
                    'document_id': chunk.get('document_id'),
                    'page_number': chunk.get('page_number'),
                    'content': chunk.get('content', ''),
                    'metadata': chunk.get('metadata', {})
                }
                images.append(image_info)
        
        return images
    
    def validate_medical_content(self, content: str) -> Dict[str, Any]:
        """
        Validate medical content for accuracy and completeness
        
        Args:
            content: Medical content to validate
            
        Returns:
            Validation results
        """
        try:
            prompt = f"""Review the following medical content for accuracy and completeness. Check for:
1. Consistency in medical terminology
2. Proper citation of sources
3. Accuracy of medical data and measurements
4. Completeness of information
5. Professional medical language usage

Content to review:
{content}

Provide a brief validation report with any issues found:"""

            response = self.llm.invoke([HumanMessage(content=prompt)])
            
            return {
                'validation_report': response.content,
                'is_valid': 'no issues found' in response.content.lower(),
                'recommendations': []
            }
            
        except Exception as e:
            logger.error(f"Error validating medical content: {e}")
            return {
                'validation_report': "Error during validation",
                'is_valid': False,
                'recommendations': []
            }
