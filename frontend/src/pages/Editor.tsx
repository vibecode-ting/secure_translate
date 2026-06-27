import { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import DocumentViewer from '../components/Viewer/DocumentViewer';
import LanguageSelector from '../components/Translation/LanguageSelector';
import EngineSelector from '../components/Translation/EngineSelector';
import ProgressBar from '../components/Translation/ProgressBar';
import { useDocument, type Document } from '../hooks/useDocument';
import { useRegions, type Region } from '../hooks/useRegions';
import { api } from '../api/client';

// Backend job response
interface TranslationJob {
  id: string;
  document_id: string;
  status: string;
  progress: number;
  pages_completed: number;
  total_pages: number;
  error_message?: string;
  output_filename?: string;
}

export default function Editor() {
  const { documentId } = useParams<{ documentId: string }>();
  const { getDocument, detectRegions, loading: docLoading } = useDocument();
  const { getRegions, createExclusion, deleteRegion, loading: regionsLoading } = useRegions();

  const [document, setDocument] = useState<Document | null>(null);
  const [regions, setRegions] = useState<Region[]>([]);
  const [selectedRegion, setSelectedRegion] = useState<Region | null>(null);
  const [drawMode, setDrawMode] = useState(false);

  const [sourceLanguage, setSourceLanguage] = useState('auto');
  const [targetLanguage, setTargetLanguage] = useState('en');
  const [engine, setEngine] = useState('gemini');

  const [translating, setTranslating] = useState(false);
  const [translationProgress, setTranslationProgress] = useState(0);
  const [translationStatus, setTranslationStatus] = useState('');
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
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

  const loadRegions = useCallback(async () => {
    if (!documentId) return;
    try {
      const regs = await getRegions(documentId);
      setRegions(regs);
    } catch {
      // regions may not exist yet
    }
  }, [documentId, getRegions]);

  useEffect(() => {
    loadDocument();
    loadRegions();
  }, [loadDocument, loadRegions]);

  const handleDetect = async () => {
    if (!documentId) return;
    try {
      await detectRegions(documentId);
      await loadRegions();
      await loadDocument();
    } catch {
      setError('Detection failed');
    }
  };

  const handleExclusionDrawn = async (rect: {
    x: number;
    y: number;
    width: number;
    height: number;
  }) => {
    if (!documentId) return;
    try {
      const region = await createExclusion(documentId, {
        page: 1, // current page from viewer — simplified
        ...rect,
      });
      setRegions((prev) => [...prev, region]);
      setDrawMode(false);
    } catch {
      setError('Failed to create exclusion zone');
    }
  };

  const handleDeleteRegion = async () => {
    if (!selectedRegion) return;
    try {
      await deleteRegion(selectedRegion.id);
      setRegions((prev) => prev.filter((r) => r.id !== selectedRegion.id));
      setSelectedRegion(null);
    } catch {
      setError('Failed to delete region');
    }
  };

  const handleTranslate = async () => {
    if (!documentId) return;
    setTranslating(true);
    setTranslationProgress(0);
    setTranslationStatus('Starting translation...');
    setError(null);

    try {
      // Create a translation job via the jobs API
      const job = await api.post<TranslationJob>('/jobs/', {
        document_id: documentId,
        source_language: sourceLanguage,
        target_language: targetLanguage,
        engine,
      });

      setCurrentJobId(job.id);
      setTranslationStatus('Translation job created...');

      // Poll for progress using the job ID
      const poll = setInterval(async () => {
        try {
          const jobStatus = await api.get<TranslationJob>(`/jobs/${job.id}`);

          setTranslationProgress(jobStatus.progress);
          setTranslationStatus(
            jobStatus.status === 'running'
              ? `Translating page ${jobStatus.pages_completed} of ${jobStatus.total_pages}...`
              : jobStatus.status
          );

          if (jobStatus.status === 'completed') {
            clearInterval(poll);
            setTranslating(false);
            setCurrentJobId(null);
            await loadDocument();
          } else if (jobStatus.status === 'failed') {
            clearInterval(poll);
            setTranslating(false);
            setCurrentJobId(null);
            setError(jobStatus.error_message || 'Translation failed');
          } else if (jobStatus.status === 'cancelled') {
            clearInterval(poll);
            setTranslating(false);
            setCurrentJobId(null);
            setTranslationStatus('Translation cancelled');
          }
        } catch {
          clearInterval(poll);
          setTranslating(false);
          setCurrentJobId(null);
          setError('Failed to check translation status');
        }
      }, 2000);
    } catch (err) {
      setTranslating(false);
      setError(err instanceof Error ? err.message : 'Translation failed');
    }
  };

  const handleCancelTranslation = async () => {
    if (!currentJobId) return;
    try {
      await api.post(`/jobs/${currentJobId}/cancel`);
    } catch {
      // ignore
    }
    setTranslating(false);
    setTranslationProgress(0);
    setTranslationStatus('');
    setCurrentJobId(null);
  };

  if (docLoading && !document) {
    return (
      <div className="flex items-center justify-center py-20">
        <svg className="animate-spin w-8 h-8 text-primary-600" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      </div>
    );
  }

  if (!document) {
    return (
      <div className="text-center py-20">
        <p className="text-gray-500">Document not found.</p>
        <Link to="/" className="btn-primary mt-4 inline-flex">
          Go Home
        </Link>
      </div>
    );
  }

  const textRegions = regions.filter((r) => r.type === 'text');
  const exclusionRegions = regions.filter((r) => r.type === 'exclusion');

  return (
    <div className="space-y-4">
      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-red-500 hover:text-red-700">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      )}

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">{document.filename}</h1>
          <p className="text-sm text-gray-500">
            {document.pages} page{document.pages !== 1 ? 's' : ''} · Status: {document.status}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {document.status === 'completed' && (
            <Link to={`/results/${document.id}`} className="btn-primary">
              View Results
            </Link>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4" style={{ minHeight: '70vh' }}>
        {/* Viewer */}
        <div className="lg:col-span-3 card overflow-hidden">
          <DocumentViewer
            documentId={document.id}
            totalPages={document.pages}
            regions={regions}
            onRegionSelect={setSelectedRegion}
            onExclusionDrawn={handleExclusionDrawn}
            selectedRegionId={selectedRegion?.id}
            drawMode={drawMode}
          />
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          {/* Detection */}
          <div className="card p-4 space-y-3">
            <h3 className="text-sm font-medium text-gray-700">OCR Detection</h3>
            <button
              onClick={handleDetect}
              disabled={docLoading}
              className="btn-primary w-full"
            >
              {docLoading ? 'Detecting...' : 'Detect Text Regions'}
            </button>
            <div className="text-xs text-gray-500 space-y-1">
              <p>{textRegions.length} text region{textRegions.length !== 1 ? 's' : ''} found</p>
              <p>{exclusionRegions.length} exclusion zone{exclusionRegions.length !== 1 ? 's' : ''}</p>
            </div>
          </div>

          {/* Region controls */}
          <div className="card p-4 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium text-gray-700">Exclusion Zones</h3>
              <button
                onClick={() => setDrawMode(!drawMode)}
                className={`text-xs px-2 py-1 rounded ${
                  drawMode
                    ? 'bg-red-100 text-red-700'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {drawMode ? 'Cancel Draw' : 'Draw Zone'}
              </button>
            </div>
            {drawMode && (
              <p className="text-xs text-amber-600 bg-amber-50 p-2 rounded">
                Click and drag on the document to draw an exclusion zone.
              </p>
            )}
            {selectedRegion && selectedRegion.type === 'exclusion' && (
              <div className="flex items-center justify-between p-2 bg-red-50 rounded">
                <span className="text-xs text-red-700">
                  Selected: {selectedRegion.label || 'Exclusion zone'}
                </span>
                <button onClick={handleDeleteRegion} className="btn-danger text-xs px-2 py-1">
                  Delete
                </button>
              </div>
            )}
            {regionsLoading && (
              <p className="text-xs text-gray-500">Loading regions...</p>
            )}
          </div>

          {/* Language */}
          <div className="card p-4">
            <LanguageSelector
              sourceLanguage={sourceLanguage}
              targetLanguage={targetLanguage}
              onSourceChange={setSourceLanguage}
              onTargetChange={setTargetLanguage}
            />
          </div>

          {/* Engine */}
          <div className="card p-4">
            <EngineSelector engine={engine} onEngineChange={setEngine} />
          </div>

          {/* Translate button */}
          <button
            onClick={handleTranslate}
            disabled={translating || docLoading}
            className="btn-primary w-full text-base py-3"
          >
            {translating ? 'Translating...' : 'Translate Document'}
          </button>
        </div>
      </div>

      {/* Progress */}
      {translating && (
        <ProgressBar
          progress={translationProgress}
          status={translationStatus}
          onCancel={handleCancelTranslation}
        />
      )}
    </div>
  );
}
