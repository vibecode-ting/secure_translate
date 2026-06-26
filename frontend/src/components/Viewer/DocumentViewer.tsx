import { useState, useEffect, useCallback } from 'react';
import type { Region } from '../../hooks/useRegions';
import RegionOverlay from './RegionOverlay';
import TextRegionHighlight from './TextRegionHighlight';

interface DocumentViewerProps {
  documentId: string;
  totalPages: number;
  regions: Region[];
  onRegionSelect?: (region: Region | null) => void;
  onExclusionDrawn?: (rect: { x: number; y: number; width: number; height: number }) => void;
  selectedRegionId?: string | null;
  drawMode?: boolean;
}

const BASE_URL = import.meta.env.VITE_API_URL || '/api';

export default function DocumentViewer({
  documentId,
  totalPages,
  regions,
  onRegionSelect,
  onExclusionDrawn,
  selectedRegionId,
  drawMode = false,
}: DocumentViewerProps) {
  const [page, setPage] = useState(1);
  const [zoom, setZoom] = useState(1);
  const [imageSize, setImageSize] = useState({ width: 0, height: 0 });

  const imageUrl = `${BASE_URL}/documents/${documentId}/pages/${page}/image`;

  const handleImageLoad = useCallback((e: React.SyntheticEvent<HTMLImageElement>) => {
    const img = e.currentTarget;
    setImageSize({ width: img.naturalWidth, height: img.naturalHeight });
  }, []);

  useEffect(() => {
    setPage(1);
  }, [documentId]);

  const pageRegions = regions.filter((r) => r.page === page);
  const textRegions = pageRegions.filter((r) => r.type === 'text');
  const exclusionRegions = pageRegions.filter((r) => r.type === 'exclusion');

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-3 py-2 bg-gray-100 border-b border-gray-200 rounded-t-lg">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="btn-secondary text-xs px-2 py-1"
          >
            Prev
          </button>
          <span className="text-sm text-gray-600">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
            className="btn-secondary text-xs px-2 py-1"
          >
            Next
          </button>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setZoom((z) => Math.max(0.25, z - 0.25))}
            className="btn-secondary text-xs px-2 py-1"
          >
            -
          </button>
          <span className="text-sm text-gray-600 w-12 text-center">
            {Math.round(zoom * 100)}%
          </span>
          <button
            onClick={() => setZoom((z) => Math.min(3, z + 0.25))}
            className="btn-secondary text-xs px-2 py-1"
          >
            +
          </button>
          <button
            onClick={() => setZoom(1)}
            className="btn-secondary text-xs px-2 py-1"
          >
            Reset
          </button>
        </div>
      </div>

      {/* Image area */}
      <div className="flex-1 overflow-auto bg-gray-200 p-4 rounded-b-lg">
        <div
          className="relative inline-block mx-auto"
          style={{ transform: `scale(${zoom})`, transformOrigin: 'top center' }}
        >
          <img
            src={imageUrl}
            alt={`Page ${page}`}
            onLoad={handleImageLoad}
            className="block max-w-full shadow-lg"
            draggable={false}
          />

          {imageSize.width > 0 && (
            <>
              {textRegions.map((region) => (
                <TextRegionHighlight
                  key={region.id}
                  region={region}
                  scale={1}
                />
              ))}
              <RegionOverlay
                regions={exclusionRegions}
                scale={1}
                imageWidth={imageSize.width}
                imageHeight={imageSize.height}
                onRegionSelect={onRegionSelect}
                onExclusionDrawn={onExclusionDrawn}
                selectedRegionId={selectedRegionId}
                drawMode={drawMode}
              />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
