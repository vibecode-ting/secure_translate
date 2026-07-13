interface EngineSelectorProps {
  engine: string;
  onEngineChange: (engine: string) => void;
}

const ENGINES = [
  {
    id: 'mymemory',
    name: 'MyMemory (Free)',
    description: 'Free translation engine, no API key required',
  },
  {
    id: 'gemini',
    name: 'Gemini',
    description: 'Google AI with strong multilingual support',
  },
  {
    id: 'azure',
    name: 'Azure Translator',
    description: 'Microsoft translation with enterprise reliability',
  },
  {
    id: 'google',
    name: 'Google Translate',
    description: 'Fast and widely supported translation service',
  },
];

export default function EngineSelector({ engine, onEngineChange }: EngineSelectorProps) {
  return (
    <div className="space-y-3">
      <h3 className="text-sm font-medium text-gray-700">Translation Engine</h3>
      <div className="space-y-2">
        {ENGINES.map((e) => (
          <label
            key={e.id}
            className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
              engine === e.id
                ? 'border-primary-500 bg-primary-50'
                : 'border-gray-200 hover:border-gray-300'
            }`}
          >
            <input
              type="radio"
              name="engine"
              value={e.id}
              checked={engine === e.id}
              onChange={() => onEngineChange(e.id)}
              className="mt-0.5 text-primary-600 focus:ring-primary-500"
            />
            <div>
              <div className="text-sm font-medium text-gray-900">{e.name}</div>
              <div className="text-xs text-gray-500">{e.description}</div>
            </div>
          </label>
        ))}
      </div>
    </div>
  );
}
