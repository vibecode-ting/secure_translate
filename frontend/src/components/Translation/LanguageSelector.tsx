interface LanguageSelectorProps {
  sourceLanguage: string;
  targetLanguage: string;
  onSourceChange: (lang: string) => void;
  onTargetChange: (lang: string) => void;
}

const LANGUAGES = [
  { code: 'auto', label: 'Auto-detect' },
  { code: 'en', label: 'English' },
  { code: 'my', label: 'Burmese' },
  { code: 'zh-CN', label: 'Simplified Chinese' },
  { code: 'zh-TW', label: 'Traditional Chinese' },
  { code: 'vi', label: 'Vietnamese' },
  { code: 'km', label: 'Khmer' },
  { code: 'id', label: 'Indonesian' },
];

const TARGET_LANGUAGES = LANGUAGES.filter((l) => l.code !== 'auto');

export default function LanguageSelector({
  sourceLanguage,
  targetLanguage,
  onSourceChange,
  onTargetChange,
}: LanguageSelectorProps) {
  const handleSwap = () => {
    if (sourceLanguage === 'auto') return;
    const prevSource = sourceLanguage;
    onSourceChange(targetLanguage);
    onTargetChange(prevSource);
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
            {LANGUAGES.map((lang) => (
              <option key={lang.code} value={lang.code}>
                {lang.label}
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
                {lang.label}
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
}
