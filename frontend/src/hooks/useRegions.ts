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

// Backend region shape
interface BackendRegion {
  id: string;
  document_id: string;
  page_number: number;
  x: number;
  y: number;
  width: number;
  height: number;
  region_type: string;
  original_text?: string;
  translated_text?: string;
  font_size?: number;
  font_family?: string;
  label?: string;
  is_auto_detected: boolean;
  created_at: string;
}

// Backend regions list response
interface RegionListResponse {
  document_id: string;
  total: number;
  regions: BackendRegion[];
}

// Map backend region to frontend Region
function mapRegion(r: BackendRegion): Region {
  return {
    id: r.id,
    document_id: r.document_id,
    page: r.page_number,
    type: r.region_type as 'text' | 'exclusion',
    x: r.x,
    y: r.y,
    width: r.width,
    height: r.height,
    text: r.original_text,
    label: r.label,
  };
}

export function useRegions() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const getRegions = useCallback(async (documentId: string, page?: number): Promise<Region[]> => {
    setLoading(true);
    setError(null);
    try {
      const params = page !== undefined ? `?page_number=${page}` : '';
      const response = await api.get<RegionListResponse>(`/regions/document/${documentId}${params}`);
      return response.regions.map(mapRegion);
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
      const response = await api.post<BackendRegion>(`/regions/document/${documentId}/exclusion`, {
        page_number: data.page,
        x: data.x,
        y: data.y,
        width: data.width,
        height: data.height,
        label: data.label,
      });
      return mapRegion(response);
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
