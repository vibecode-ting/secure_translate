import { useState, useCallback } from 'react';
import { api } from '../api/client';

export interface Region {
  id: string;
  document_id: string;
  page: number;
  type: 'text' | 'exclusion';
  x: number;
  y: number;
  width: number;
  height: number;
  text?: string;
  label?: string;
}

export interface ExclusionData {
  page: number;
  x: number;
  y: number;
  width: number;
  height: number;
  label?: string;
}

export function useRegions() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const getRegions = useCallback(async (documentId: string, page?: number): Promise<Region[]> => {
    setLoading(true);
    setError(null);
    try {
      const params = page !== undefined ? `?page=${page}` : '';
      return await api.get<Region[]>(`/documents/${documentId}/regions${params}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch regions';
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const createExclusion = useCallback(async (documentId: string, data: ExclusionData): Promise<Region> => {
    setLoading(true);
    setError(null);
    try {
      return await api.post<Region>(`/documents/${documentId}/regions`, {
        ...data,
        type: 'exclusion',
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create exclusion';
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const deleteRegion = useCallback(async (regionId: string): Promise<void> => {
    setLoading(true);
    setError(null);
    try {
      await api.delete(`/regions/${regionId}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to delete region';
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  return { loading, error, getRegions, createExclusion, deleteRegion };
}
