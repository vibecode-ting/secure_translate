import type { Region } from '../../hooks/useRegions';

interface TextRegionHighlightProps {
  region: Region;
  scale: number;
}

export default function TextRegionHighlight({ region, scale }: TextRegionHighlightProps) {
  return (
    <div
      className="absolute group cursor-pointer"
      style={{
        left: region.x * scale,
        top: region.y * scale,
        width: region.width * scale,
        height: region.height * scale,
      }}
    >
      <div className="w-full h-full bg-green-400/20 border border-green-500/50 rounded-sm transition-colors hover:bg-green-400/30" />
      {region.text && (
        <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block z-10">
          <div className="bg-gray-900 text-white text-xs px-2 py-1 rounded shadow-lg whitespace-nowrap max-w-xs truncate">
            {region.text}
          </div>
        </div>
      )}
    </div>
  );
}
