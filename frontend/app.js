/**
 * MedDocs Assistant - Frontend JavaScript
 * Handles all frontend interactions with the backend API
 */

class MedDocsApp {
    constructor() {
        this.apiBaseUrl = 'http://localhost:8000';
        this.currentSessionId = null;
        this.documents = [];
        this.reports = [];
        this.googleDriveFiles = [];
        
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.setupTabNavigation();
        this.loadDocuments();
        this.loadReports();
        this.showStatus('Application loaded successfully', 'success');
    }

    setupEventListeners() {
        // File upload
        const fileInput = document.getElementById('file-input');
        const uploadArea = document.getElementById('upload-area');

        fileInput.addEventListener('change', (e) => this.handleFileUpload(e.target.files));
        
        // Drag and drop
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });
        
        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('dragover');
        });
        
        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            this.handleFileUpload(e.dataTransfer.files);
        });

        // Chat
        const chatInput = document.getElementById('chat-input');
        const sendButton = document.getElementById('send-button');
        
        sendButton.addEventListener('click', () => this.sendMessage());
        chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Report generation
        const reportForm = document.getElementById('report-form');
        reportForm.addEventListener('submit', (e) => {
            e.preventDefault();
            this.generateReport();
        });

        // Google Drive
        const loadDriveButton = document.getElementById('load-drive-files');
        const refreshDriveButton = document.getElementById('refresh-drive-files');
        const driveSearch = document.getElementById('drive-search');
        
        loadDriveButton.addEventListener('click', () => this.loadGoogleDriveFiles());
        refreshDriveButton.addEventListener('click', () => this.loadGoogleDriveFiles());
        driveSearch.addEventListener('input', (e) => this.filterGoogleDriveFiles(e.target.value));
    }

    setupTabNavigation() {
        const navLinks = document.querySelectorAll('[data-tab]');
        const tabContents = document.querySelectorAll('.tab-content');

        navLinks.forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                
                // Remove active classes
                navLinks.forEach(l => l.classList.remove('active'));
                tabContents.forEach(t => t.classList.remove('active'));
                
                // Add active class to clicked link
                link.classList.add('active');
                
                // Show corresponding tab content
                const tabId = link.getAttribute('data-tab') + '-tab';
                const tabContent = document.getElementById(tabId);
                if (tabContent) {
                    tabContent.classList.add('active');
                }
            });
        });
    }

    async handleFileUpload(files) {
        if (!files || files.length === 0) return;

        const progressContainer = document.getElementById('upload-progress');
        const progressBar = progressContainer.querySelector('.progress-bar');
        
        progressContainer.classList.remove('d-none');
        
        for (let i = 0; i < files.length; i++) {
            const file = files[i];
            
            try {
                // Update progress
                const progress = ((i + 1) / files.length) * 100;
                progressBar.style.width = `${progress}%`;
                progressBar.textContent = `${Math.round(progress)}%`;
                
                await this.uploadFile(file);
                
            } catch (error) {
                console.error('Upload error:', error);
                this.showStatus(`Failed to upload ${file.name}: ${error.message}`, 'error');
            }
        }
        
        progressContainer.classList.add('d-none');
        progressBar.style.width = '0%';
        
        // Refresh documents list
        await this.loadDocuments();
        this.showStatus(`Successfully uploaded ${files.length} file(s)`, 'success');
    }

    async uploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch(`${this.apiBaseUrl}/documents/upload`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Upload failed');
        }

        return await response.json();
    }

    async loadDocuments() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/documents`);
            if (!response.ok) throw new Error('Failed to load documents');
            
            this.documents = await response.json();
            this.renderDocuments();
            this.updateDocumentFilter();
            
        } catch (error) {
            console.error('Error loading documents:', error);
            this.showStatus('Failed to load documents', 'error');
        }
    }

    renderDocuments() {
        const container = document.getElementById('documents-list');
        
        if (this.documents.length === 0) {
            container.innerHTML = `
                <div class="text-center text-muted">
                    <i class="fas fa-folder-open fa-2x mb-2"></i>
                    <p>No documents uploaded yet</p>
                </div>
            `;
            return;
        }

        container.innerHTML = this.documents.map(doc => `
            <div class="document-item ${doc.processing_status}" data-id="${doc.id}">
                <div class="document-info">
                    <div>
                        <div class="document-name">
                            <i class="fas fa-file-${this.getFileIcon(doc.file_type)} me-2"></i>
                            ${doc.original_filename}
                        </div>
                        <div class="document-meta">
                            ${this.formatFileSize(doc.file_size)} • 
                            ${new Date(doc.upload_date).toLocaleDateString()} •
                            <span class="status-badge status-${doc.processing_status}">${doc.processing_status}</span>
                            ${doc.is_google_drive ? '<i class="fab fa-google-drive ms-1"></i>' : ''}
                        </div>
                    </div>
                    <div class="document-actions">
                        ${doc.google_drive_url ? `<a href="${doc.google_drive_url}" target="_blank" class="btn btn-sm btn-outline-primary" title="View in Google Drive"><i class="fab fa-google-drive"></i></a>` : ''}
                        <button class="btn btn-sm btn-outline-danger" onclick="app.deleteDocument(${doc.id})" title="Delete">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
            </div>
        `).join('');
    }

    async deleteDocument(documentId) {
        if (!confirm('Are you sure you want to delete this document?')) return;

        try {
            const response = await fetch(`${this.apiBaseUrl}/documents/${documentId}`, {
                method: 'DELETE'
            });

            if (!response.ok) throw new Error('Failed to delete document');

            await this.loadDocuments();
            this.showStatus('Document deleted successfully', 'success');

        } catch (error) {
            console.error('Error deleting document:', error);
            this.showStatus('Failed to delete document', 'error');
        }
    }

    async sendMessage() {
        const input = document.getElementById('chat-input');
        const message = input.value.trim();
        
        if (!message) return;

        // Clear input
        input.value = '';

        // Add user message to chat
        this.addMessageToChat('user', message);

        // Show typing indicator
        this.showTypingIndicator();

        try {
            const response = await fetch(`${this.apiBaseUrl}/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    message: message,
                    session_id: this.currentSessionId
                })
            });

            if (!response.ok) throw new Error('Failed to send message');

            const result = await response.json();
            this.currentSessionId = result.session_id;

            // Remove typing indicator
            this.hideTypingIndicator();

            // Add assistant response
            this.addMessageToChat('assistant', result.content, result.citations);

        } catch (error) {
            console.error('Error sending message:', error);
            this.hideTypingIndicator();
            this.addMessageToChat('assistant', 'Sorry, I encountered an error while processing your message. Please try again.');
            this.showStatus('Failed to send message', 'error');
        }
    }

    addMessageToChat(role, content, citations = []) {
        const messagesContainer = document.getElementById('chat-messages');
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}-message`;
        
        let citationsHtml = '';
        if (citations && citations.length > 0) {
            citationsHtml = `
                <div class="message-citations">
                    <strong>Sources:</strong>
                    ${citations.map(citation => `
                        <div class="citation-item">
                            <i class="fas fa-file-medical me-1"></i>
                            ${citation.document_name}
                            ${citation.pages && citation.pages.length > 0 ? ` (Pages: ${citation.pages.join(', ')})` : ''}
                            ${citation.google_drive_url ? `<a href="${citation.google_drive_url}" target="_blank" class="citation-link ms-2"><i class="fab fa-google-drive"></i> View</a>` : ''}
                        </div>
                    `).join('')}
                </div>
            `;
        }

        messageDiv.innerHTML = `
            <div class="message-content">
                ${role === 'assistant' ? '<i class="fas fa-robot me-2"></i>' : ''}
                ${content}
            </div>
            ${citationsHtml}
        `;

        messagesContainer.appendChild(messageDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    showTypingIndicator() {
        const messagesContainer = document.getElementById('chat-messages');
        
        const typingDiv = document.createElement('div');
        typingDiv.className = 'message assistant-message typing-indicator';
        typingDiv.id = 'typing-indicator';
        typingDiv.innerHTML = `
            <div class="message-content">
                <i class="fas fa-robot me-2"></i>
                Analyzing documents...
                <div class="typing-dots ms-2">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            </div>
        `;

        messagesContainer.appendChild(typingDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    hideTypingIndicator() {
        const typingIndicator = document.getElementById('typing-indicator');
        if (typingIndicator) {
            typingIndicator.remove();
        }
    }

    async generateReport() {
        const title = document.getElementById('report-title').value.trim();
        const selectedSections = Array.from(document.querySelectorAll('.section-checkboxes input:checked'))
            .map(input => input.value);
        const selectedDocuments = Array.from(document.getElementById('document-filter').selectedOptions)
            .map(option => parseInt(option.value))
            .filter(id => !isNaN(id));

        if (!title) {
            this.showStatus('Please enter a report title', 'error');
            return;
        }

        if (selectedSections.length === 0) {
            this.showStatus('Please select at least one section', 'error');
            return;
        }

        this.showLoading('Generating Report', 'This may take a few minutes...');

        try {
            const response = await fetch(`${this.apiBaseUrl}/reports/generate`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    title: title,
                    sections: selectedSections,
                    document_ids: selectedDocuments.length > 0 ? selectedDocuments : null
                })
            });

            if (!response.ok) throw new Error('Failed to generate report');

            const result = await response.json();
            this.hideLoading();
            
            await this.loadReports();
            this.showStatus('Report generation started successfully', 'success');

            // Reset form
            document.getElementById('report-form').reset();
            document.querySelectorAll('.section-checkboxes input[checked]').forEach(input => input.checked = true);

        } catch (error) {
            console.error('Error generating report:', error);
            this.hideLoading();
            this.showStatus('Failed to generate report', 'error');
        }
    }

    async loadReports() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/reports`);
            if (!response.ok) throw new Error('Failed to load reports');
            
            this.reports = await response.json();
            this.renderReports();
            
        } catch (error) {
            console.error('Error loading reports:', error);
            this.showStatus('Failed to load reports', 'error');
        }
    }

    renderReports() {
        const container = document.getElementById('reports-list');
        
        if (this.reports.length === 0) {
            container.innerHTML = `
                <div class="text-center text-muted">
                    <i class="fas fa-file-alt fa-2x mb-2"></i>
                    <p>No reports generated yet</p>
                </div>
            `;
            return;
        }

        container.innerHTML = this.reports.map(report => `
            <div class="report-item" data-id="${report.id}">
                <div class="d-flex justify-content-between align-items-start">
                    <div class="flex-grow-1">
                        <h6 class="mb-1">${report.title}</h6>
                        <div class="text-muted small">
                            <i class="fas fa-calendar me-1"></i>
                            ${new Date(report.created_at).toLocaleString()}
                        </div>
                        <div class="mt-1">
                            <span class="report-status status-${report.status}">${report.status}</span>
                        </div>
                        <div class="mt-1 text-muted small">
                            Sections: ${report.sections.join(', ')}
                        </div>
                    </div>
                    <div class="ms-2">
                        ${report.status === 'completed' && report.file_path ? 
                            `<a href="${this.apiBaseUrl}/reports/${report.id}/download" class="btn btn-sm btn-primary" title="Download PDF">
                                <i class="fas fa-download"></i>
                            </a>` : 
                            `<button class="btn btn-sm btn-secondary" disabled>
                                <i class="fas fa-clock"></i>
                            </button>`
                        }
                    </div>
                </div>
            </div>
        `).join('');
    }

    async loadGoogleDriveFiles() {
        this.showLoading('Loading Google Drive Files', 'Connecting to Google Drive...');

        try {
            const response = await fetch(`${this.apiBaseUrl}/google-drive/files?file_types=pdf,docx,xlsx,png,jpg`);
            
            if (!response.ok) {
                if (response.status === 401) {
                    throw new Error('Google Drive not authenticated. Please configure credentials.');
                }
                throw new Error('Failed to load Google Drive files');
            }

            const result = await response.json();
            this.googleDriveFiles = result.files || [];
            this.renderGoogleDriveFiles();
            this.hideLoading();
            
            this.showStatus(`Loaded ${this.googleDriveFiles.length} files from Google Drive`, 'success');

        } catch (error) {
            console.error('Error loading Google Drive files:', error);
            this.hideLoading();
            this.showStatus(error.message, 'error');
        }
    }

    renderGoogleDriveFiles() {
        const container = document.getElementById('google-drive-files');
        
        if (this.googleDriveFiles.length === 0) {
            container.innerHTML = `
                <div class="text-center text-muted">
                    <i class="fab fa-google-drive fa-2x mb-2"></i>
                    <p>No supported files found in Google Drive</p>
                </div>
            `;
            return;
        }

        container.innerHTML = this.googleDriveFiles.map(file => `
            <div class="drive-file-item" data-id="${file.id}">
                <div class="drive-file-info">
                    <div class="drive-file-name">
                        <i class="fas fa-file-${this.getFileIcon(this.getFileExtension(file.name))} me-2"></i>
                        ${file.name}
                    </div>
                    <div class="drive-file-meta">
                        ${this.formatFileSize(file.size)} • 
                        Modified: ${new Date(file.modified_time).toLocaleDateString()}
                    </div>
                </div>
                <div class="drive-file-actions">
                    <a href="${file.web_view_link}" target="_blank" class="btn btn-sm btn-outline-danger" title="View in Google Drive">
                        <i class="fab fa-google-drive"></i>
                    </a>
                    <button class="btn btn-sm btn-danger" onclick="app.importGoogleDriveFile('${file.id}')" title="Import to MedDocs">
                        <i class="fas fa-download"></i>
                    </button>
                </div>
            </div>
        `).join('');
    }

    async importGoogleDriveFile(fileId) {
        this.showLoading('Importing File', 'Downloading from Google Drive...');

        try {
            const response = await fetch(`${this.apiBaseUrl}/google-drive/import/${fileId}`, {
                method: 'POST'
            });

            if (!response.ok) throw new Error('Failed to import file from Google Drive');

            const result = await response.json();
            this.hideLoading();
            
            await this.loadDocuments();
            this.showStatus('File imported successfully from Google Drive', 'success');

        } catch (error) {
            console.error('Error importing Google Drive file:', error);
            this.hideLoading();
            this.showStatus('Failed to import file from Google Drive', 'error');
        }
    }

    filterGoogleDriveFiles(searchTerm) {
        const items = document.querySelectorAll('.drive-file-item');
        const term = searchTerm.toLowerCase();

        items.forEach(item => {
            const fileName = item.querySelector('.drive-file-name').textContent.toLowerCase();
            if (fileName.includes(term)) {
                item.style.display = 'flex';
            } else {
                item.style.display = 'none';
            }
        });
    }

    updateDocumentFilter() {
        const select = document.getElementById('document-filter');
        
        // Clear existing options except "All Documents"
        select.innerHTML = '<option value="">All Documents</option>';
        
        // Add document options
        this.documents.forEach(doc => {
            if (doc.processing_status === 'completed') {
                const option = document.createElement('option');
                option.value = doc.id;
                option.textContent = doc.original_filename;
                select.appendChild(option);
            }
        });
    }

    showLoading(title, detail) {
        const modal = document.getElementById('loadingModal');
        document.getElementById('loading-text').textContent = title;
        document.getElementById('loading-detail').textContent = detail;
        
        const bootstrapModal = new bootstrap.Modal(modal);
        bootstrapModal.show();
    }

    hideLoading() {
        const modal = document.getElementById('loadingModal');
        const bootstrapModal = bootstrap.Modal.getInstance(modal);
        if (bootstrapModal) {
            bootstrapModal.hide();
        }
    }

    showStatus(message, type = 'info') {
        const statusBar = document.getElementById('status-bar');
        const statusMessage = document.getElementById('status-message');
        
        statusMessage.textContent = message;
        
        // Remove existing alert classes
        statusBar.className = 'alert d-block';
        
        // Add appropriate alert class
        switch (type) {
            case 'success':
                statusBar.classList.add('alert-success');
                break;
            case 'error':
                statusBar.classList.add('alert-danger');
                break;
            case 'warning':
                statusBar.classList.add('alert-warning');
                break;
            default:
                statusBar.classList.add('alert-info');
        }
        
        // Auto-hide after 5 seconds
        setTimeout(() => {
            statusBar.classList.add('d-none');
        }, 5000);
    }

    getFileIcon(fileType) {
        const iconMap = {
            'pdf': 'pdf',
            'docx': 'word',
            'doc': 'word',
            'xlsx': 'excel',
            'xls': 'excel',
            'png': 'image',
            'jpg': 'image',
            'jpeg': 'image',
            'tiff': 'image',
            'bmp': 'image'
        };
        return iconMap[fileType?.toLowerCase()] || 'file';
    }

    getFileExtension(filename) {
        return filename.split('.').pop()?.toLowerCase() || '';
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.app = new MedDocsApp();
});

// Global functions for onclick handlers
window.deleteDocument = (id) => window.app.deleteDocument(id);
window.importGoogleDriveFile = (id) => window.app.importGoogleDriveFile(id);
