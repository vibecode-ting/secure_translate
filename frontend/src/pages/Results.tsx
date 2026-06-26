import { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import ResultViewer from '../components/Output/ResultViewer';
import DownloadButton from '../components/Output/DownloadButton';
import { useDocument, type Document } from '../hooks/useDocument';

export default function Results() {
  const { documentId } = useParams<{ documentId: string }>();
  const { getDocument, loading } = useDocument();
  const [document, setDocument] = useState<Document | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadDocument = useCallback(async () => {
    if (!documentId) return;
    try {
      const doc = await getDocument(documentId);
      setDocument(doc);
    } catch {
      setError('Failed to load document');
    }
  }, [documentId, getDocument]);

  useEffect(() => {
    loadDocument();
  }, [loadDocument]);

  if (loading && !document) {
    return (
      <div className="flex items-center justify-center py-20">
        <svg className="animate-spin w-8 h-8 text-primary-600" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      </div>
    );
  }

  if (error || !document) {
    return (
      <div className="text-center py-20">
        <p className="text-gray-500">{error || 'Document not found.'}</p>
        <Link to="/" className="btn-primary mt-4 inline-flex">
          Go Home
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">
            Translation Results: {document.filename}
          </h1>
          <p className="text-sm text-gray-500">
            {document.pages} page{document.pages !== 1 ? 's' : ''} translated
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link to={`/editor/${document.id}`} className="btn-secondary">
            <svg className="w-4 h-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
            Edit
          </Link>
          <DownloadButton documentId={document.id} filename={document.filename} />
        </div>
      </div>

      <div className="card overflow-hidden" style={{ minHeight: '70vh' }}>
        <ResultViewer documentId={document.id} totalPages={document.pages} />
      </div>
    </div>
  );
}
