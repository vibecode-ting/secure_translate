import { useState, useEffect, useCallback } from 'react';
import { api } from '../../api/client';

interface Language {
  code: string;
  name: string;
}

interface DetectionResult {
  detected_language: string;
  confidence: number;
  language_name: string;
}

interface LanguageSelectorProps {
  sourceLanguage: string;
  targetLanguage: string;
  onSourceChange: (lang: string) => void;
  onTargetChange: (lang: string) => void;
  documentId?: string;
}

const ALL_LANGUAGES: Language[] = [
  { code: 'auto', name: 'Auto-detect' },
  { code: 'en', name: 'English' },
  { code: 'my', name: 'Burmese' },
  { code: 'zh-CN', name: 'Simplified Chinese' },
  { code: 'zh-TW', name: 'Traditional Chinese' },
  { code: 'vi', name: 'Vietnamese' },
  { code: 'km', name: 'Khmer' },
  { code: 'id', name: 'Indonesian' },
  { code: 'ja', name: 'Japanese' },
  { code: 'ko', name: 'Korean' },
  { code: 'th', name: 'Thai' },
];

const TARGET_LANGUAGES = ALL_LANGUAGES.filter((l) => l.code !== 'auto');

export default function LanguageSelector({
  sourceLanguage,
  targetLanguage,
  onSourceChange,
  onTargetChange,
  documentId,
}: LanguageSelectorProps) {
  const [detection, setDetection] = useState<DetectionResult | null>(null);
  const [detecting, setDetecting] = useState(false);

  const detectLanguage = useCallback(async () => {
    if (!documentId) return;
    setDetecting(true);
    try {
      const result = await api.post<DetectionResult>('/languages/detect', {
        document_id: documentId,
      });
      setDetection(result);
      // Auto-set source language if currently on auto
      if (sourceLanguage === 'auto' && result.detected_language) {
        onSourceChange(result.detected_language);
      }
    } catch {
      // Detection failure is non-critical
    } finally {
      setDetecting(false);
    }
  }, [documentId, sourceLanguage, onSourceChange]);

  useEffect(() => {
    if (documentId) {
      detectLanguage();
    }
  }, [documentId, detectLanguage]);

  const handleSwap = () => {
    if (sourceLanguage === 'auto') return;
    const prevSource = sourceLanguage;
    onSourceChange(targetLanguage);
    onTargetChange(prevSource);
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'text-green-600';
    if (confidence >= 0.5) return 'text-yellow-600';
    return 'text-gray-500';
  };

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-medium text-gray-700">Languages</h3>
      <div className="flex items-center gap-2">
        <div className="flex-1">
          <label className="block text-xs text-gray-500 mb-1">Source</label>
          <select
            value={sourceLanguage}
            onChange={(e) => onSourceChange(e.target.value)}
            className="input"
          >
            {ALL_LANGUAGES.map((lang) => (
              <option key={lang.code} value={lang.code}>
                {lang.name}
              </option>
            ))}
          </select>
        </div>

        <button
          onClick={handleSwap}
          disabled={sourceLanguage === 'auto'}
          className="mt-5 p-2 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          title="Swap languages"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
          </svg>
        </button>

        <div className="flex-1">
          <label className="block text-xs text-gray-500 mb-1">Target</label>
          <select
            value={targetLanguage}
            onChange={(e) => onTargetChange(e.target.value)}
            className="input"
          >
            {TARGET_LANGUAGES.map((lang) => (
              <option key={lang.code} value={lang.code}>
                {lang.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Detection result */}
      {detecting && (
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <svg className="animate-spin w-3 h-3" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Detecting language...
        </div>
      )}
      {!detecting && detection && (
        <div className="text-xs text-gray-500">
          Detected:{' '}
          <span className="font-medium text-gray-700">{detection.language_name}</span>{' '}
          <span className={getConfidenceColor(detection.confidence)}>
            ({Math.round(detection.confidence * 100)}%)
          </span>
        </div>
      )}
    </div>
  );
}
