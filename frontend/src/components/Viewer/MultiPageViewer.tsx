import { useState, useEffect, useCallback, useRef } from 'react';
import type { Region } from '../../hooks/useRegions';
import RegionOverlay from './RegionOverlay';
import TextRegionHighlight from './TextRegionHighlight';

const BASE_URL = import.meta.env.VITE_API_URL || '/api';

interface MultiPageViewerProps {
  documentId: string;
  totalPages: number;
  regions: Region[];
  onRegionSelect?: (region: Region | null) => void;
  onExclusionDrawn?: (rect: { x: number; y: number; width: number; height: number }) => void;
  selectedRegionId?: string | null;
  drawMode?: boolean;
}

interface ImageCache {
  [page: number]: string;
}

export default function MultiPageViewer({
  documentId,
  totalPages,
  regions,
  onRegionSelect,
  onExclusionDrawn,
  selectedRegionId,
  drawMode = false,
}: MultiPageViewerProps) {
  const [currentPage, setCurrentPage] = useState(1);
  const [zoom, setZoom] = useState(1);
  const [imageSize, setImageSize] = useState({ width: 0, height: 0 });
  const [imageCache, setImageCache] = useState<ImageCache>({});
  const [loadingPages, setLoadingPages] = useState<Set<number>>(new Set());
  const [imageErrors, setImageErrors] = useState<Set<number>>(new Set());
  const viewerRef = useRef<HTMLDivElement>(null);
  const thumbnailContainerRef = useRef<HTMLDivElement>(null);

  const imageUrl = `${BASE_URL}/documents/${documentId}/pages/${currentPage}/image`;

  // Preload adjacent pages
  const preloadPages = useCallback(
    (page: number) => {
      const pagesToPreload = [page - 1, page + 1].filter((p) => p >= 1 && p <= totalPages);
      pagesToPreload.forEach((p) => {
        if (!imageCache[p] && !loadingPages.has(p)) {
          setLoadingPages((prev) => new Set(prev).add(p));
          const img = new Image();
          img.onload = () => {
            setImageCache((prev) => ({ ...prev, [p]: `${BASE_URL}/documents/${documentId}/pages/${p}/image` }));
            setLoadingPages((prev) => {
              const next = new Set(prev);
              next.delete(p);
              return next;
            });
          };
          img.onerror = () => {
            setImageErrors((prev) => new Set(prev).add(p));
            setLoadingPages((prev) => {
              const next = new Set(prev);
              next.delete(p);
              return next;
            });
          };
          img.src = `${BASE_URL}/documents/${documentId}/pages/${p}/image`;
        }
      });
    },
    [documentId, totalPages, imageCache, loadingPages],
  );

  // Load current page and preload neighbors
  useEffect(() => {
    setLoadingPages((prev) => new Set(prev).add(currentPage));
    const img = new Image();
    img.onload = () => {
      setImageCache((prev) => ({ ...prev, [currentPage]: imageUrl }));
      setLoadingPages((prev) => {
        const next = new Set(prev);
        next.delete(currentPage);
        return next;
      });
    };
    img.onerror = () => {
      setImageErrors((prev) => new Set(prev).add(currentPage));
      setLoadingPages((prev) => {
        const next = new Set(prev);
        next.delete(currentPage);
        return next;
      });
    };
    img.src = imageUrl;

    preloadPages(currentPage);
  }, [currentPage, imageUrl, preloadPages]);

  // Scroll thumbnail into view
  useEffect(() => {
    if (thumbnailContainerRef.current) {
      const activeThumb = thumbnailContainerRef.current.querySelector(`[data-page="${currentPage}"]`);
      if (activeThumb) {
        activeThumb.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    }
  }, [currentPage]);

  // Reset page when document changes
  useEffect(() => {
    setCurrentPage(1);
    setImageCache({});
    setLoadingPages(new Set());
    setImageErrors(new Set());
  }, [documentId]);

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't handle if user is typing in an input
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

      switch (e.key) {
        case 'ArrowLeft':
          e.preventDefault();
          setCurrentPage((p) => Math.max(1, p - 1));
          break;
        case 'ArrowRight':
          e.preventDefault();
          setCurrentPage((p) => Math.min(totalPages, p + 1));
          break;
        case '+':
        case '=':
          e.preventDefault();
          setZoom((z) => Math.min(3, z + 0.25));
          break;
        case '-':
          e.preventDefault();
          setZoom((z) => Math.max(0.25, z - 0.25));
          break;
        case '0':
          e.preventDefault();
          setZoom(1);
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [totalPages]);

  const handleImageLoad = useCallback((e: React.SyntheticEvent<HTMLImageElement>) => {
    const img = e.currentTarget;
    setImageSize({ width: img.naturalWidth, height: img.naturalHeight });
  }, []);

  const pageRegions = regions.filter((r) => r.page === currentPage);
  const textRegions = pageRegions.filter((r) => r.type === 'text');
  const exclusionRegions = pageRegions.filter((r) => r.type === 'exclusion');

  const isPageLoading = loadingPages.has(currentPage);
  const hasError = imageErrors.has(currentPage);

  return (
    <div ref={viewerRef} className="flex h-full rounded-lg overflow-hidden">
      {/* Thumbnail strip */}
      <div
        ref={thumbnailContainerRef}
        className="w-24 flex-shrink-0 overflow-y-auto bg-gray-100 border-r border-gray-200 p-2 space-y-2 hidden sm:block"
      >
        {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => {
          const thumbUrl = `${BASE_URL}/documents/${documentId}/pages/${page}/image`;
          const isActive = page === currentPage;
          const thumbLoading = loadingPages.has(page);
          const thumbError = imageErrors.has(page);

          return (
            <button
              key={page}
              data-page={page}
              onClick={() => setCurrentPage(page)}
              className={`w-full relative rounded-lg overflow-hidden border-2 transition-all duration-150 ${
                isActive
                  ? 'border-primary-500 ring-2 ring-primary-200'
                  : 'border-gray-200 hover:border-gray-300'
              }`}
            >
              <div className="aspect-[3/4] bg-gray-200 flex items-center justify-center">
                {thumbError ? (
                  <svg className="w-6 h-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
                  </svg>
                ) : (
                  <img
                    src={thumbUrl}
                    alt={`Page ${page}`}
                    className="w-full h-full object-cover"
                    loading="lazy"
                  />
                )}
                {thumbLoading && (
                  <div className="absolute inset-0 bg-black/10 flex items-center justify-center">
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  </div>
                )}
              </div>
              <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/60 to-transparent p-1">
                <span className="text-[10px] text-white font-medium">{page}</span>
              </div>
            </button>
          );
        })}
      </div>

      {/* Main viewer */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Toolbar */}
        <div className="flex items-center justify-between px-3 py-2 bg-gray-100 border-b border-gray-200">
          {/* Mobile page selector */}
          <div className="flex items-center gap-2 sm:hidden">
            <button
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage <= 1}
              className="btn-secondary text-xs px-2 py-1"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            <select
              value={currentPage}
              onChange={(e) => setCurrentPage(Number(e.target.value))}
              className="text-sm border border-gray-300 rounded px-2 py-1 bg-white"
            >
              {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
                <option key={page} value={page}>
                  Page {page} of {totalPages}
                </option>
              ))}
            </select>
            <button
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage >= totalPages}
              className="btn-secondary text-xs px-2 py-1"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </button>
          </div>

          {/* Desktop page navigation */}
          <div className="hidden sm:flex items-center gap-2">
            <button
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage <= 1}
              className="btn-secondary text-xs px-2 py-1"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            <span className="text-sm text-gray-600 min-w-[80px] text-center">
              Page {currentPage} of {totalPages}
            </span>
            <button
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage >= totalPages}
              className="btn-secondary text-xs px-2 py-1"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </button>
          </div>

          {/* Zoom controls */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setZoom((z) => Math.max(0.25, z - 0.25))}
              className="btn-secondary text-xs px-2 py-1"
              title="Zoom out (or press -)"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
              </svg>
            </button>
            <button
              onClick={() => setZoom(1)}
              className="text-sm text-gray-600 w-12 text-center hover:text-gray-900 transition-colors"
              title="Reset zoom (or press 0)"
            >
              {Math.round(zoom * 100)}%
            </button>
            <button
              onClick={() => setZoom((z) => Math.min(3, z + 0.25))}
              className="btn-secondary text-xs px-2 py-1"
              title="Zoom in (or press +)"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
            </button>
          </div>
        </div>

        {/* Image area */}
        <div className="flex-1 overflow-auto bg-gray-200 p-4 relative">
          {hasError ? (
            <div className="flex flex-col items-center justify-center h-full text-gray-500">
              <svg className="w-12 h-12 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
              <p className="text-sm">Failed to load page {currentPage}</p>
              <button
                onClick={() => {
                  setImageErrors((prev) => {
                    const next = new Set(prev);
                    next.delete(currentPage);
                    return next;
                  });
                }}
                className="btn-secondary text-xs mt-2"
              >
                Retry
              </button>
            </div>
          ) : (
            <div
              className="relative inline-block mx-auto"
              style={{ transform: `scale(${zoom})`, transformOrigin: 'top center' }}
            >
              <img
                src={imageUrl}
                alt={`Page ${currentPage}`}
                onLoad={handleImageLoad}
                className="block max-w-full shadow-lg"
                draggable={false}
              />

              {imageSize.width > 0 && (
                <>
                  {textRegions.map((region) => (
                    <TextRegionHighlight key={region.id} region={region} scale={1} />
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
          )}

          {/* Loading overlay */}
          {isPageLoading && !hasError && (
            <div className="absolute inset-0 flex items-center justify-center bg-gray-200/50">
              <div className="flex flex-col items-center gap-2">
                <svg className="animate-spin w-8 h-8 text-primary-600" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                <span className="text-sm text-gray-600">Loading page {currentPage}...</span>
              </div>
            </div>
          )}
        </div>

        {/* Keyboard shortcuts hint */}
        <div className="hidden sm:flex items-center justify-center gap-4 px-3 py-1 bg-gray-50 border-t border-gray-200 text-xs text-gray-500">
          <span>
            <kbd className="px-1.5 py-0.5 bg-white border border-gray-200 rounded text-gray-600">←</kbd>
            <kbd className="px-1.5 py-0.5 bg-white border border-gray-200 rounded text-gray-600 ml-1">→</kbd>
            {' '}Navigate pages
          </span>
          <span>
            <kbd className="px-1.5 py-0.5 bg-white border border-gray-200 rounded text-gray-600">+</kbd>
            <kbd className="px-1.5 py-0.5 bg-white border border-gray-200 rounded text-gray-600 ml-1">-</kbd>
            {' '}Zoom
          </span>
          <span>
            <kbd className="px-1.5 py-0.5 bg-white border border-gray-200 rounded text-gray-600">0</kbd>
            {' '}Reset zoom
          </span>
        </div>
      </div>
    </div>
  );
}
