import { useState, useEffect } from 'react';
import { api } from '../../api/client';

const BASE_URL = import.meta.env.VITE_API_URL || '/api';

interface ResultViewerProps {
  documentId: string;
  totalPages: number;
}

// Backend job response
interface TranslationJob {
  id: string;
  document_id: string;
  status: string;
  output_filename?: string;
}

interface JobsResponse {
  document_id: string;
  total: number;
  items: TranslationJob[];
}

export default function ResultViewer({ documentId, totalPages }: ResultViewerProps) {
  const [page, setPage] = useState(1);
  const [jobId, setJobId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchJob = async () => {
      try {
        const response = await api.get<JobsResponse>(`/jobs/document/${documentId}`);
        const completedJob = response.items.find(j => j.status === 'completed');
        if (completedJob) {
          setJobId(completedJob.id);
        }
      } catch {
        // ignore
      } finally {
        setLoading(false);
      }
    };
    fetchJob();
  }, [documentId]);

  const originalUrl = `${BASE_URL}/documents/${documentId}/pages/${page}/image`;
  const translatedUrl = jobId
    ? `${BASE_URL}/documents/${documentId}/pages/${page}/translated?job_id=${jobId}`
    : null;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <svg className="animate-spin w-8 h-8 text-primary-600" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      </div>
    );
  }

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
          {translatedUrl ? (
            <img
              src={translatedUrl}
              alt={`Translated page ${page}`}
              className="w-full rounded shadow-lg"
            />
          ) : (
            <div className="flex items-center justify-center h-64 bg-gray-100 rounded">
              <p className="text-gray-500 text-sm">No translated output available</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
