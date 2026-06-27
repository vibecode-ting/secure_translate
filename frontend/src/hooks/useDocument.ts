import { useState, useCallback } from 'react';
import { api } from '../api/client';

export interface Document {
  id: string;
  filename: string;
  pages: number;
  status: 'uploaded' | 'detecting' | 'ready' | 'translating' | 'completed' | 'error';
  created_at: string;
  source_language?: string;
  target_language?: string;
}

// Backend response shape for document list
interface DocumentListResponse {
  total: number;
  skip: number;
  limit: number;
  items: BackendDocument[];
}

// Backend document shape (different field names)
interface BackendDocument {
  id: string;
  filename: string;
  doc_type: string;
  status: string;
  page_count: number;
  file_size_bytes: number;
  created_at: string;
  updated_at: string;
  source_language?: string;
  target_language?: string;
  progress?: number;
  error_message?: string;
}

// Backend upload response
interface UploadResponse {
  document_id: string;
  filename: string;
  page_count: number;
  doc_type: string;
  status: string;
}

// Backend detect response
interface DetectResponse {
  document_id: string;
  status: string;
  regions_detected: number;
}

// Map backend document to frontend Document
function mapDocument(doc: BackendDocument): Document {
  return {
    id: doc.id,
    filename: doc.filename,
    pages: doc.page_count,
    status: mapStatus(doc.status),
    created_at: doc.created_at,
    source_language: doc.source_language,
    target_language: doc.target_language,
  };
}

// Map backend status strings to frontend status
function mapStatus(status: string): Document['status'] {
  switch (status) {
    case 'uploaded': return 'uploaded';
    case 'processing': return 'detecting';
    case 'ready': return 'ready';
    case 'translating': return 'translating';
    case 'completed': return 'completed';
    case 'failed': return 'error';
    default: return 'uploaded';
  }
}

export function useDocument() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const uploadDocument = useCallback(async (file: File): Promise<Document> => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.upload<UploadResponse>('/documents/upload', file);
      return {
        id: response.document_id,
        filename: response.filename,
        pages: response.page_count,
        status: mapStatus(response.status),
        created_at: new Date().toISOString(),
      };
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Upload failed';
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const getDocument = useCallback(async (id: string): Promise<Document> => {
    setLoading(true);
    setError(null);
    try {
      const doc = await api.get<BackendDocument>(`/documents/${id}`);
      return mapDocument(doc);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch document';
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const detectRegions = useCallback(async (id: string): Promise<{ regions_detected: number }> => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.post<DetectResponse>(`/documents/${id}/detect`);
      return { regions_detected: response.regions_detected };
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Detection failed';
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const deleteDocument = useCallback(async (id: string): Promise<void> => {
    setLoading(true);
    setError(null);
    try {
      await api.delete(`/documents/${id}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Delete failed';
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const listDocuments = useCallback(async (): Promise<Document[]> => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.get<DocumentListResponse>('/documents/');
      return response.items.map(mapDocument);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch documents';
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  return { loading, error, uploadDocument, getDocument, detectRegions, deleteDocument, listDocuments };
}
