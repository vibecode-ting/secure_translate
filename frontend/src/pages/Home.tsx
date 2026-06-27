import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import FileUploader from '../components/Upload/FileUploader';
import { useDocument, type Document } from '../hooks/useDocument';

export default function Home() {
  const [recentDocs, setRecentDocs] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const { listDocuments } = useDocument();

  useEffect(() => {
    const fetchRecent = async () => {
      try {
        const docs = await listDocuments();
        setRecentDocs(docs.slice(0, 5));
      } catch {
        // Silently fail — recent docs are non-critical
      } finally {
        setLoading(false);
      }
    };
    fetchRecent();
  }, [listDocuments]);

  return (
    <div className="max-w-4xl mx-auto space-y-12">
      {/* Hero */}
      <section className="text-center py-12">
        <h1 className="text-4xl font-bold text-gray-900 mb-4">
          Translate Documents Securely
        </h1>
        <p className="text-lg text-gray-600 max-w-2xl mx-auto mb-8">
          Upload images or PDFs, detect text regions with OCR, select exclusion zones,
          and translate with your preferred engine. Your documents stay private.
        </p>
        <div className="flex items-center justify-center gap-6 text-sm text-gray-500">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 bg-green-500 rounded-full" />
            OCR Detection
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 bg-blue-500 rounded-full" />
            Multiple Engines
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 bg-purple-500 rounded-full" />
            Region Exclusion
          </div>
        </div>
      </section>

      {/* Upload */}
      <section className="card p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Upload Document</h2>
        <FileUploader />
      </section>

      {/* Recent Documents */}
      <section>
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Recent Documents</h2>
        {loading ? (
          <div className="card p-8 text-center text-gray-500">
            <svg className="animate-spin w-6 h-6 mx-auto mb-2 text-gray-400" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Loading...
          </div>
        ) : recentDocs.length === 0 ? (
          <div className="card p-8 text-center text-gray-500">
            <p>No documents yet. Upload one to get started.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {recentDocs.map((doc) => (
              <Link
                key={doc.id}
                to={
                  doc.status === 'completed'
                    ? `/results/${doc.id}`
                    : `/editor/${doc.id}`
                }
                className="card p-4 flex items-center justify-between hover:shadow-md transition-shadow"
              >
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-primary-100 rounded-lg flex items-center justify-center">
                    <svg className="w-5 h-5 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                  </div>
                  <div>
                    <p className="font-medium text-gray-900">{doc.filename}</p>
                    <p className="text-sm text-gray-500">{doc.pages} page{doc.pages !== 1 ? 's' : ''}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span
                    className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                      doc.status === 'completed'
                        ? 'bg-green-100 text-green-800'
                        : doc.status === 'error'
                          ? 'bg-red-100 text-red-800'
                          : doc.status === 'translating'
                            ? 'bg-blue-100 text-blue-800'
                            : 'bg-gray-100 text-gray-800'
                    }`}
                  >
                    {doc.status}
                  </span>
                  <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
