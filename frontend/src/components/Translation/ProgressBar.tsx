interface ProgressBarProps {
  progress: number;
  status: string;
  onCancel?: () => void;
}

export default function ProgressBar({ progress, status, onCancel }: ProgressBarProps) {
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-gray-700">{status}</span>
        <span className="text-sm text-gray-500">{Math.round(progress)}%</span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
        <div
          className="bg-primary-600 h-full rounded-full transition-all duration-300 ease-out"
          style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
        />
      </div>
      {onCancel && (
        <div className="mt-3 flex justify-end">
          <button onClick={onCancel} className="btn-secondary text-xs">
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}
