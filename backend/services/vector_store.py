"""
Vector store service for document embeddings and similarity search
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import numpy as np
from config import settings

logger = logging.getLogger(__name__)


class VectorStore:
    """Service for managing document embeddings and similarity search"""
    
    def __init__(self):
        self.client = chromadb.PersistentClient(
            path=settings.chroma_persist_directory,
            settings=Settings(anonymized_telemetry=False)
        )
        self.collection_name = "medical_documents"
        self.embedding_model = SentenceTransformer(settings.embedding_model)
        self.collection = self._get_or_create_collection()
    
    def _get_or_create_collection(self):
        """Get or create the ChromaDB collection"""
        try:
            collection = self.client.get_collection(name=self.collection_name)
            logger.info(f"Retrieved existing collection: {self.collection_name}")
        except Exception:
            collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"description": "Medical document embeddings"}
            )
            logger.info(f"Created new collection: {self.collection_name}")
        
        return collection
    
    def add_document_chunks(self, document_id: int, chunks: List[Dict[str, Any]]) -> bool:
        """
        Add document chunks to the vector store
        
        Args:
            document_id: Database ID of the document
            chunks: List of chunk dictionaries with content and metadata
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not chunks:
                logger.warning(f"No chunks provided for document {document_id}")
                return False
            
            # Prepare data for ChromaDB
            documents = []
            metadatas = []
            ids = []
            
            for chunk in chunks:
                chunk_id = f"doc_{document_id}_chunk_{chunk['chunk_index']}"
                
                # Prepare metadata
                metadata = {
                    'document_id': str(document_id),
                    'chunk_index': int(chunk['chunk_index']),
                    'chunk_type': str(chunk.get('chunk_type', 'text')),
                    'page_number': str(chunk.get('page_number', '')),
                    'section_title': str(chunk.get('section_title', '')),
                }
                
                # Add any additional metadata from chunk_metadata, converting to simple types
                if 'chunk_metadata' in chunk and chunk['chunk_metadata']:
                    for key, value in chunk['chunk_metadata'].items():
                        if isinstance(value, (str, int, float, bool)):
                            metadata[f"meta_{key}"] = value
                        elif value is not None:
                            metadata[f"meta_{key}"] = str(value)
                
                documents.append(chunk['content'])
                metadatas.append(metadata)
                ids.append(chunk_id)
            
            # Generate embeddings
            embeddings = self.embedding_model.encode(documents).tolist()
            
            # Add to ChromaDB
            self.collection.add(
                documents=documents,
                metadatas=metadatas,
                embeddings=embeddings,
                ids=ids
            )
            
            logger.info(f"Added {len(chunks)} chunks for document {document_id} to vector store")
            return True
            
        except Exception as e:
            logger.error(f"Error adding document chunks to vector store: {e}")
            return False
    
    def search_similar_chunks(
        self, 
        query: str, 
        n_results: int = 5,
        document_ids: Optional[List[int]] = None,
        min_similarity: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        Search for similar document chunks
        
        Args:
            query: Search query
            n_results: Number of results to return
            document_ids: Optional list of document IDs to filter by
            min_similarity: Minimum similarity threshold
            
        Returns:
            List of similar chunks with metadata and scores
        """
        try:
            # Generate query embedding
            query_embedding = self.embedding_model.encode([query]).tolist()[0]
            
            # Prepare where clause for filtering
            where_clause = None
            if document_ids:
                where_clause = {"document_id": {"$in": document_ids}}
            
            # Search in ChromaDB
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where_clause,
                include=['documents', 'metadatas', 'distances']
            )
            
            # Process results
            similar_chunks = []
            if results['documents'] and results['documents'][0]:
                for i, (doc, metadata, distance) in enumerate(zip(
                    results['documents'][0],
                    results['metadatas'][0],
                    results['distances'][0]
                )):
                    # Convert distance to similarity score (ChromaDB uses cosine distance)
                    similarity = 1 - distance
                    
                    if similarity >= min_similarity:
                        chunk_info = {
                            'content': doc,
                            'metadata': metadata,
                            'similarity_score': similarity,
                            'document_id': metadata.get('document_id'),
                            'chunk_index': metadata.get('chunk_index'),
                            'page_number': metadata.get('page_number'),
                            'section_title': metadata.get('section_title', ''),
                            'chunk_type': metadata.get('chunk_type', 'text')
                        }
                        similar_chunks.append(chunk_info)
            
            logger.info(f"Found {len(similar_chunks)} similar chunks for query: {query[:50]}...")
            return similar_chunks
            
        except Exception as e:
            logger.error(f"Error searching similar chunks: {e}")
            return []
    
    def delete_document_chunks(self, document_id: int) -> bool:
        """
        Delete all chunks for a specific document
        
        Args:
            document_id: Database ID of the document
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get all chunk IDs for the document
            results = self.collection.get(
                where={"document_id": document_id},
                include=['metadatas']
            )
            
            if results['ids']:
                self.collection.delete(ids=results['ids'])
                logger.info(f"Deleted {len(results['ids'])} chunks for document {document_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting document chunks: {e}")
            return False
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the vector store collection"""
        try:
            count = self.collection.count()
            return {
                'total_chunks': count,
                'collection_name': self.collection_name,
                'embedding_model': settings.embedding_model
            }
        except Exception as e:
            logger.error(f"Error getting collection stats: {e}")
            return {}
    
    def search_by_document_section(
        self, 
        document_id: int, 
        section_types: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Search for chunks by document ID and section types
        
        Args:
            document_id: Database ID of the document
            section_types: List of section types to search for
            
        Returns:
            List of matching chunks
        """
        try:
            where_clause = {
                "document_id": document_id,
                "chunk_type": {"$in": section_types}
            }
            
            results = self.collection.get(
                where=where_clause,
                include=['documents', 'metadatas']
            )
            
            chunks = []
            if results['documents']:
                for doc, metadata in zip(results['documents'], results['metadatas']):
                    chunk_info = {
                        'content': doc,
                        'metadata': metadata,
                        'document_id': metadata.get('document_id'),
                        'chunk_index': metadata.get('chunk_index'),
                        'page_number': metadata.get('page_number'),
                        'section_title': metadata.get('section_title', ''),
                        'chunk_type': metadata.get('chunk_type', 'text')
                    }
                    chunks.append(chunk_info)
            
            return chunks
            
        except Exception as e:
            logger.error(f"Error searching by document section: {e}")
            return []
