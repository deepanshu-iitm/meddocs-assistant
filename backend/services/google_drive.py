"""
Google Drive integration service for accessing medical documents
"""
import os
import io
import logging
from typing import List, Dict, Any, Optional
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.http import MediaIoBaseDownload
from config import settings
import tempfile

logger = logging.getLogger(__name__)

# Google Drive API scopes
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']


class GoogleDriveService:
    """Service for integrating with Google Drive to access medical documents"""
    
    def __init__(self):
        self.service = None
        self.credentials = None
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate with Google Drive API"""
        try:
            creds = None
            token_file = settings.google_drive_token_file
            credentials_file = settings.google_drive_credentials_file
            
            # Load existing token
            if os.path.exists(token_file):
                creds = Credentials.from_authorized_user_file(token_file, SCOPES)
            
            # If no valid credentials, get new ones
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    if not os.path.exists(credentials_file):
                        logger.error(f"Google Drive credentials file not found: {credentials_file}")
                        return
                    
                    flow = InstalledAppFlow.from_client_secrets_file(
                        credentials_file, SCOPES
                    )
                    creds = flow.run_local_server(port=0)
                
                # Save credentials for next run
                with open(token_file, 'w') as token:
                    token.write(creds.to_json())
            
            self.credentials = creds
            self.service = build('drive', 'v3', credentials=creds)
            logger.info("Successfully authenticated with Google Drive")
            
        except Exception as e:
            logger.error(f"Error authenticating with Google Drive: {e}")
            self.service = None
    
    def list_files(self, folder_id: Optional[str] = None, file_types: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        List files from Google Drive
        
        Args:
            folder_id: Optional folder ID to search in
            file_types: Optional list of file types to filter by
            
        Returns:
            List of file information dictionaries
        """
        if not self.service:
            logger.error("Google Drive service not authenticated")
            return []
        
        try:
            # Build query
            query_parts = []
            
            if folder_id:
                query_parts.append(f"'{folder_id}' in parents")
            
            if file_types:
                mime_types = []
                for file_type in file_types:
                    if file_type.lower() == 'pdf':
                        mime_types.append("mimeType='application/pdf'")
                    elif file_type.lower() in ['doc', 'docx']:
                        mime_types.append("mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document'")
                        mime_types.append("mimeType='application/msword'")
                    elif file_type.lower() in ['xls', 'xlsx']:
                        mime_types.append("mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'")
                        mime_types.append("mimeType='application/vnd.ms-excel'")
                    elif file_type.lower() in ['png', 'jpg', 'jpeg']:
                        mime_types.append("mimeType contains 'image/'")
                
                if mime_types:
                    query_parts.append(f"({' or '.join(mime_types)})")
            
            # Add condition to exclude trashed files
            query_parts.append("trashed=false")
            
            query = " and ".join(query_parts) if query_parts else "trashed=false"
            
            # Execute query
            results = self.service.files().list(
                q=query,
                pageSize=100,
                fields="nextPageToken, files(id, name, mimeType, size, createdTime, modifiedTime, webViewLink, parents)"
            ).execute()
            
            files = results.get('files', [])
            
            # Format file information
            file_list = []
            for file in files:
                file_info = {
                    'id': file['id'],
                    'name': file['name'],
                    'mime_type': file.get('mimeType', ''),
                    'size': int(file.get('size', 0)) if file.get('size') else 0,
                    'created_time': file.get('createdTime', ''),
                    'modified_time': file.get('modifiedTime', ''),
                    'web_view_link': file.get('webViewLink', ''),
                    'parents': file.get('parents', [])
                }
                file_list.append(file_info)
            
            logger.info(f"Found {len(file_list)} files in Google Drive")
            return file_list
            
        except Exception as e:
            logger.error(f"Error listing Google Drive files: {e}")
            return []
    
    def download_file(self, file_id: str, local_path: str) -> bool:
        """
        Download a file from Google Drive
        
        Args:
            file_id: Google Drive file ID
            local_path: Local path to save the file
            
        Returns:
            True if successful, False otherwise
        """
        if not self.service:
            logger.error("Google Drive service not authenticated")
            return False
        
        try:
            # Get file metadata
            file_metadata = self.service.files().get(fileId=file_id).execute()
            
            # Download file
            request = self.service.files().get_media(fileId=file_id)
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            # Download to local file
            with open(local_path, 'wb') as local_file:
                downloader = MediaIoBaseDownload(local_file, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
            
            logger.info(f"Downloaded file {file_metadata['name']} to {local_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error downloading file {file_id}: {e}")
            return False
    
    def get_file_info(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific file
        
        Args:
            file_id: Google Drive file ID
            
        Returns:
            File information dictionary or None
        """
        if not self.service:
            logger.error("Google Drive service not authenticated")
            return None
        
        try:
            file_info = self.service.files().get(
                fileId=file_id,
                fields="id, name, mimeType, size, createdTime, modifiedTime, webViewLink, parents, description"
            ).execute()
            
            return {
                'id': file_info['id'],
                'name': file_info['name'],
                'mime_type': file_info.get('mimeType', ''),
                'size': int(file_info.get('size', 0)) if file_info.get('size') else 0,
                'created_time': file_info.get('createdTime', ''),
                'modified_time': file_info.get('modifiedTime', ''),
                'web_view_link': file_info.get('webViewLink', ''),
                'parents': file_info.get('parents', []),
                'description': file_info.get('description', '')
            }
            
        except Exception as e:
            logger.error(f"Error getting file info for {file_id}: {e}")
            return None
    
    def search_files_by_name(self, name_pattern: str) -> List[Dict[str, Any]]:
        """
        Search files by name pattern
        
        Args:
            name_pattern: Name pattern to search for
            
        Returns:
            List of matching files
        """
        if not self.service:
            logger.error("Google Drive service not authenticated")
            return []
        
        try:
            query = f"name contains '{name_pattern}' and trashed=false"
            
            results = self.service.files().list(
                q=query,
                pageSize=50,
                fields="files(id, name, mimeType, size, createdTime, modifiedTime, webViewLink)"
            ).execute()
            
            files = results.get('files', [])
            
            file_list = []
            for file in files:
                file_info = {
                    'id': file['id'],
                    'name': file['name'],
                    'mime_type': file.get('mimeType', ''),
                    'size': int(file.get('size', 0)) if file.get('size') else 0,
                    'created_time': file.get('createdTime', ''),
                    'modified_time': file.get('modifiedTime', ''),
                    'web_view_link': file.get('webViewLink', '')
                }
                file_list.append(file_info)
            
            return file_list
            
        except Exception as e:
            logger.error(f"Error searching files by name: {e}")
            return []
    
    def is_authenticated(self) -> bool:
        """Check if the service is properly authenticated"""
        return self.service is not None
    
    def get_folder_contents(self, folder_id: str) -> List[Dict[str, Any]]:
        """
        Get contents of a specific folder
        
        Args:
            folder_id: Google Drive folder ID
            
        Returns:
            List of files and folders in the specified folder
        """
        return self.list_files(folder_id=folder_id)
