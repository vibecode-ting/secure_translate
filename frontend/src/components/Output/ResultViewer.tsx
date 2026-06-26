import { useState } from 'react';

const BASE_URL = import.meta.env.VITE_API_URL || '/api';

interface ResultViewerProps {
  documentId: string;
  totalPages: number;
}

export default function ResultViewer({ documentId, totalPages }: ResultViewerProps) {
  const [page, setPage] = useState(1);

  const originalUrl = `${BASE_URL}/documents/${documentId}/pages/${page}/image`;
  const translatedUrl = `${BASE_URL}/documents/${documentId}/pages/${page}/translated`;

  return (
    <div className="flex flex-col h-full">
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
      </div>

      <div className="flex-1 grid grid-cols-2 gap-4 p-4 bg-gray-200 rounded-b-lg overflow-auto">
        <div className="space-y-2">
          <h4 className="text-sm font-medium text-gray-700 text-center">Original</h4>
          <img
            src={originalUrl}
            alt={`Original page ${page}`}
            className="w-full rounded shadow-lg"
          />
        </div>
        <div className="space-y-2">
          <h4 className="text-sm font-medium text-gray-700 text-center">Translated</h4>
          <img
            src={translatedUrl}
            alt={`Translated page ${page}`}
            className="w-full rounded shadow-lg"
          />
        </div>
      </div>
    </div>
  );
}
