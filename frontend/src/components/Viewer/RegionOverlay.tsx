import { useState, useRef, useCallback } from 'react';
import type { Region } from '../../hooks/useRegions';

interface RegionOverlayProps {
  regions: Region[];
  scale: number;
  imageWidth: number;
  imageHeight: number;
  onRegionSelect?: (region: Region | null) => void;
  onExclusionDrawn?: (rect: { x: number; y: number; width: number; height: number }) => void;
  selectedRegionId?: string | null;
  drawMode?: boolean;
}

export default function RegionOverlay({
  regions,
  scale,
  imageWidth,
  imageHeight,
  onRegionSelect,
  onExclusionDrawn,
  selectedRegionId,
  drawMode = false,
}: RegionOverlayProps) {
  const [drawing, setDrawing] = useState(false);
  const [start, setStart] = useState<{ x: number; y: number } | null>(null);
  const [current, setCurrent] = useState<{ x: number; y: number } | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const getCoords = useCallback(
    (e: React.MouseEvent) => {
      const rect = svgRef.current?.getBoundingClientRect();
      if (!rect) return { x: 0, y: 0 };
      return {
        x: (e.clientX - rect.left) / scale,
        y: (e.clientY - rect.top) / scale,
      };
    },
    [scale],
  );

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (!drawMode) return;
      const coords = getCoords(e);
      setDrawing(true);
      setStart(coords);
      setCurrent(coords);
    },
    [drawMode, getCoords],
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (!drawing) return;
      setCurrent(getCoords(e));
    },
    [drawing, getCoords],
  );

  const handleMouseUp = useCallback(() => {
    if (!drawing || !start || !current) return;
    setDrawing(false);

    const x = Math.min(start.x, current.x);
    const y = Math.min(start.y, current.y);
    const width = Math.abs(current.x - start.x);
    const height = Math.abs(current.y - start.y);

    if (width > 5 && height > 5) {
      onExclusionDrawn?.({
        x: Math.round(x),
        y: Math.round(y),
        width: Math.round(width),
        height: Math.round(height),
      });
    }

    setStart(null);
    setCurrent(null);
  }, [drawing, start, current, onExclusionDrawn]);

  const rect =
    drawing && start && current
      ? {
          x: Math.min(start.x, current.x) * scale,
          y: Math.min(start.y, current.y) * scale,
          width: Math.abs(current.x - start.x) * scale,
          height: Math.abs(current.y - start.y) * scale,
        }
      : null;

  return (
    <svg
      ref={svgRef}
      className="absolute inset-0 w-full h-full"
      viewBox={`0 0 ${imageWidth * scale} ${imageHeight * scale}`}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      style={{ cursor: drawMode ? 'crosshair' : 'default' }}
    >
      {regions.map((region) => {
        const isExclusion = region.type === 'exclusion';
        const isSelected = region.id === selectedRegionId;
        return (
          <g key={region.id}>
            <rect
              x={region.x * scale}
              y={region.y * scale}
              width={region.width * scale}
              height={region.height * scale}
              fill={isExclusion ? 'rgba(239, 68, 68, 0.15)' : 'rgba(34, 197, 94, 0.15)'}
              stroke={isSelected ? '#2563eb' : isExclusion ? '#ef4444' : '#22c55e'}
              strokeWidth={isSelected ? 2 : 1}
              className="cursor-pointer"
              onClick={(e) => {
                e.stopPropagation();
                onRegionSelect?.(region);
              }}
            />
            {region.label && (
              <text
                x={region.x * scale + 4}
                y={region.y * scale + 14}
                fill={isExclusion ? '#ef4444' : '#22c55e'}
                fontSize="11"
                fontWeight="500"
              >
                {region.label}
              </text>
            )}
          </g>
        );
      })}

      {rect && (
        <rect
          x={rect.x}
          y={rect.y}
          width={rect.width}
          height={rect.height}
          fill="rgba(239, 68, 68, 0.2)"
          stroke="#ef4444"
          strokeWidth={2}
          strokeDasharray="6 3"
        />
      )}
    </svg>
  );
}
