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

export function useDocument() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const uploadDocument = useCallback(async (file: File): Promise<Document> => {
    setLoading(true);
    setError(null);
    try {
      const doc = await api.upload<Document>('/documents', file);
      return doc;
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
      return await api.get<Document>(`/documents/${id}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch document';
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const detectRegions = useCallback(async (id: string): Promise<Document> => {
    setLoading(true);
    setError(null);
    try {
      return await api.post<Document>(`/documents/${id}/detect`);
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

  return { loading, error, uploadDocument, getDocument, detectRegions, deleteDocument };
}
