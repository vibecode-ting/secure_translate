import { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import MultiPageViewer from '../components/Viewer/MultiPageViewer';
import LanguageSelector from '../components/Translation/LanguageSelector';
import EngineSelector from '../components/Translation/EngineSelector';
import ProgressBar from '../components/Translation/ProgressBar';
import { useDocument, type Document } from '../hooks/useDocument';
import { useRegions, type Region } from '../hooks/useRegions';
import { api } from '../api/client';

interface JobCreateResponse {
  id: string;
  document_id: string;
  status: string;
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

  const [activeJobId, setActiveJobId] = useState<string | null>(null);
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
        page: 1,
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
    setError(null);

    try {
      const job = await api.post<JobCreateResponse>('/jobs', {
        document_id: documentId,
        source_language: sourceLanguage,
        target_language: targetLanguage,
        engine,
      });

      setActiveJobId(job.id);
      await loadDocument();
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to start translation';
      setError(msg);
    }
  };

  const handleTranslationComplete = async () => {
    setActiveJobId(null);
    await loadDocument();
  };

  const handleTranslationError = (msg: string) => {
    setError(msg);
    setActiveJobId(null);
  };

  const handleTranslationCancel = async () => {
    setActiveJobId(null);
    await loadDocument();
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
  const isTranslating = activeJobId !== null;
  const isCompleted = document.status === 'completed';

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
          {isCompleted && (
            <Link to={`/results/${document.id}`} className="btn-primary">
              View Results
            </Link>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4" style={{ minHeight: '70vh' }}>
        {/* Viewer */}
        <div className="lg:col-span-3 card overflow-hidden">
          <MultiPageViewer
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
              documentId={documentId}
            />
          </div>

          {/* Engine */}
          <div className="card p-4">
            <EngineSelector engine={engine} onEngineChange={setEngine} />
          </div>

          {/* Translate button */}
          {isCompleted ? (
            <Link to={`/results/${document.id}`} className="btn-primary w-full text-base py-3 text-center">
              View Translated Document
            </Link>
          ) : (
            <button
              onClick={handleTranslate}
              disabled={isTranslating || docLoading}
              className="btn-primary w-full text-base py-3"
            >
              {isTranslating ? 'Translating...' : 'Translate Document'}
            </button>
          )}
        </div>
      </div>

      {/* Progress */}
      {isTranslating && (
        <ProgressBar
          jobId={activeJobId}
          onComplete={handleTranslationComplete}
          onError={handleTranslationError}
          onCancel={handleTranslationCancel}
        />
      )}
    </div>
  );
}
