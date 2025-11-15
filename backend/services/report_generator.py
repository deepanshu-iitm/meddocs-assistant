"""
Medical report generation service with PDF export functionality
"""
import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from jinja2 import Template
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
import tempfile
from pathlib import Path
from config import settings

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Service for generating structured medical reports and exporting to PDF"""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
        
    def _setup_custom_styles(self):
        """Setup custom styles for medical reports"""
        # Title style
        self.styles.add(ParagraphStyle(
            name='ReportTitle',
            parent=self.styles['Title'],
            fontSize=18,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.darkblue
        ))
        
        # Section header style
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading1'],
            fontSize=14,
            spaceBefore=20,
            spaceAfter=12,
            textColor=colors.darkblue,
            borderWidth=1,
            borderColor=colors.darkblue,
            borderPadding=5
        ))
        
        # Subsection header style
        self.styles.add(ParagraphStyle(
            name='SubsectionHeader',
            parent=self.styles['Heading2'],
            fontSize=12,
            spaceBefore=15,
            spaceAfter=8,
            textColor=colors.darkgreen
        ))
        
        # Citation style
        self.styles.add(ParagraphStyle(
            name='Citation',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=colors.grey,
            leftIndent=20,
            spaceAfter=6
        ))
        
        # Medical data style
        self.styles.add(ParagraphStyle(
            name='MedicalData',
            parent=self.styles['Normal'],
            fontSize=10,
            fontName='Courier',
            leftIndent=10,
            backgroundColor=colors.lightgrey,
            borderWidth=1,
            borderColor=colors.grey,
            borderPadding=5
        ))
    
    def generate_report(
        self, 
        title: str, 
        sections: Dict[str, Dict[str, Any]], 
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate a complete medical report and export to PDF
        
        Args:
            title: Report title
            sections: Dictionary of section data
            metadata: Additional report metadata
            
        Returns:
            Path to generated PDF file
        """
        try:
            # Create unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"medical_report_{timestamp}.pdf"
            filepath = os.path.join(settings.reports_dir, filename)
            
            # Create PDF document
            doc = SimpleDocTemplate(
                filepath,
                pagesize=A4,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=18
            )
            
            # Build report content
            story = []
            
            # Add title
            story.append(Paragraph(title, self.styles['ReportTitle']))
            story.append(Spacer(1, 20))
            
            # Add metadata if available
            if metadata:
                story.extend(self._add_metadata_section(metadata))
            
            # Add sections
            for section_name, section_data in sections.items():
                story.extend(self._add_section(section_name, section_data))
            
            # Add citations section
            all_citations = []
            for section_data in sections.values():
                if 'citations' in section_data:
                    all_citations.extend(section_data['citations'])
            
            if all_citations:
                story.extend(self._add_citations_section(all_citations))
            
            # Build PDF
            doc.build(story)
            
            logger.info(f"Generated medical report: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            raise
    
    def _add_metadata_section(self, metadata: Dict[str, Any]) -> List:
        """Add metadata section to report"""
        elements = []
        
        elements.append(Paragraph("Report Information", self.styles['SectionHeader']))
        
        # Create metadata table
        data = []
        if 'generated_date' in metadata:
            data.append(['Generated Date:', metadata['generated_date']])
        if 'documents_used' in metadata:
            data.append(['Documents Used:', str(metadata['documents_used'])])
        if 'total_pages' in metadata:
            data.append(['Total Pages Analyzed:', str(metadata['total_pages'])])
        if 'report_type' in metadata:
            data.append(['Report Type:', metadata['report_type']])
        
        if data:
            table = Table(data, colWidths=[2*inch, 4*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.lightblue),
                ('TEXTCOLOR', (0, 0), (0, -1), colors.darkblue),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                ('BACKGROUND', (1, 0), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            elements.append(table)
            elements.append(Spacer(1, 20))
        
        return elements
    
    def _add_section(self, section_name: str, section_data: Dict[str, Any]) -> List:
        """Add a section to the report"""
        elements = []
        
        # Section header
        formatted_name = section_name.replace('_', ' ').title()
        elements.append(Paragraph(formatted_name, self.styles['SectionHeader']))
        
        # Section content
        content = section_data.get('content', '')
        if content:
            # Split content into paragraphs
            paragraphs = content.split('\n\n')
            for para in paragraphs:
                if para.strip():
                    # Check if it's a table or structured data
                    if '|' in para and para.count('|') > 2:
                        elements.extend(self._process_table_content(para))
                    else:
                        elements.append(Paragraph(para.strip(), self.styles['Normal']))
                        elements.append(Spacer(1, 6))
        
        # Add tables if present
        if 'tables' in section_data and section_data['tables']:
            elements.extend(self._add_tables(section_data['tables']))
        
        # Add images if present
        if 'images' in section_data and section_data['images']:
            elements.extend(self._add_images(section_data['images']))
        
        elements.append(Spacer(1, 15))
        return elements
    
    def _process_table_content(self, table_text: str) -> List:
        """Process table content from text"""
        elements = []
        
        try:
            # Split into rows
            rows = [row.strip() for row in table_text.split('\n') if row.strip()]
            
            # Parse table data
            table_data = []
            for row in rows:
                if '|' in row:
                    cells = [cell.strip() for cell in row.split('|') if cell.strip()]
                    if cells:
                        table_data.append(cells)
            
            if table_data:
                # Create table
                table = Table(table_data)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.darkblue),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                elements.append(table)
                elements.append(Spacer(1, 12))
        
        except Exception as e:
            logger.warning(f"Error processing table content: {e}")
            # Fallback to regular paragraph
            elements.append(Paragraph(table_text, self.styles['MedicalData']))
        
        return elements
    
    def _add_tables(self, tables: List[Dict[str, Any]]) -> List:
        """Add tables to the report"""
        elements = []
        
        for i, table_info in enumerate(tables):
            elements.append(Paragraph(f"Table {i+1}", self.styles['SubsectionHeader']))
            
            # Add table content
            content = table_info.get('content', '')
            if content:
                elements.extend(self._process_table_content(content))
            
            # Add source citation
            doc_id = table_info.get('document_id')
            page_num = table_info.get('page_number')
            if doc_id:
                citation_text = f"Source: Document {doc_id}"
                if page_num:
                    citation_text += f", Page {page_num}"
                elements.append(Paragraph(citation_text, self.styles['Citation']))
            
            elements.append(Spacer(1, 10))
        
        return elements
    
    def _add_images(self, images: List[Dict[str, Any]]) -> List:
        """Add images to the report"""
        elements = []
        
        for i, image_info in enumerate(images):
            elements.append(Paragraph(f"Figure {i+1}", self.styles['SubsectionHeader']))
            
            # Add image description/OCR content
            content = image_info.get('content', '')
            if content:
                elements.append(Paragraph(f"Content: {content}", self.styles['Normal']))
            
            # Add source citation
            doc_id = image_info.get('document_id')
            page_num = image_info.get('page_number')
            if doc_id:
                citation_text = f"Source: Document {doc_id}"
                if page_num:
                    citation_text += f", Page {page_num}"
                elements.append(Paragraph(citation_text, self.styles['Citation']))
            
            elements.append(Spacer(1, 10))
        
        return elements
    
    def _add_citations_section(self, citations: List[Dict[str, Any]]) -> List:
        """Add citations section to the report"""
        elements = []
        
        elements.append(Paragraph("References and Citations", self.styles['SectionHeader']))
        
        # Group citations by document
        doc_citations = {}
        for citation in citations:
            doc_id = citation.get('document_id')
            if doc_id not in doc_citations:
                doc_citations[doc_id] = citation
        
        # Add citation list
        for i, (doc_id, citation) in enumerate(doc_citations.items(), 1):
            citation_text = f"{i}. Document {doc_id}"
            
            pages = citation.get('pages', [])
            if pages:
                citation_text += f" (Pages: {', '.join(map(str, pages))})"
            
            sections = citation.get('sections', [])
            if sections:
                citation_text += f" - Sections: {', '.join(sections)}"
            
            # Add Google Drive link if available
            google_drive_url = citation.get('google_drive_url')
            if google_drive_url:
                citation_text += f" - Available at: {google_drive_url}"
            
            elements.append(Paragraph(citation_text, self.styles['Citation']))
        
        return elements
    
    def create_summary_report(
        self, 
        documents: List[Dict[str, Any]], 
        key_findings: List[str],
        recommendations: List[str] = None
    ) -> str:
        """
        Create a summary report of multiple documents
        
        Args:
            documents: List of document information
            key_findings: List of key findings from analysis
            recommendations: Optional list of recommendations
            
        Returns:
            Path to generated summary report PDF
        """
        try:
            # Prepare sections
            sections = {
                'executive_summary': {
                    'content': '\n\n'.join(key_findings),
                    'citations': []
                },
                'document_overview': {
                    'content': self._create_document_overview(documents),
                    'citations': []
                }
            }
            
            if recommendations:
                sections['recommendations'] = {
                    'content': '\n\n'.join(recommendations),
                    'citations': []
                }
            
            # Generate report
            title = f"Medical Document Analysis Summary - {datetime.now().strftime('%Y-%m-%d')}"
            metadata = {
                'generated_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'documents_used': len(documents),
                'report_type': 'Summary Analysis'
            }
            
            return self.generate_report(title, sections, metadata)
            
        except Exception as e:
            logger.error(f"Error creating summary report: {e}")
            raise
    
    def _create_document_overview(self, documents: List[Dict[str, Any]]) -> str:
        """Create an overview of analyzed documents"""
        overview_parts = []
        
        for i, doc in enumerate(documents, 1):
            doc_info = f"{i}. {doc.get('filename', 'Unknown Document')}"
            
            if doc.get('file_type'):
                doc_info += f" ({doc['file_type'].upper()})"
            
            if doc.get('upload_date'):
                doc_info += f" - Uploaded: {doc['upload_date']}"
            
            if doc.get('file_size'):
                size_mb = doc['file_size'] / (1024 * 1024)
                doc_info += f" - Size: {size_mb:.1f} MB"
            
            overview_parts.append(doc_info)
        
        return '\n\n'.join(overview_parts)
