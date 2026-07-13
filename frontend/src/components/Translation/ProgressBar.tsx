import { useEffect, useRef, useState, useCallback } from 'react';
import { api } from '../../api/client';

interface JobStatus {
  id: string;
  status: string;
  progress: number;
  pages_completed: number;
  total_pages: number;
  error_message: string | null;
  output_filename: string | null;
}

interface ProgressBarProps {
  jobId: string | null;
  onComplete?: (jobId: string) => void;
  onError?: (error: string) => void;
  onCancel?: () => void;
}

const STATUS_LABELS: Record<string, string> = {
  pending: 'Queued',
  detecting: 'Detecting text regions',
  running: 'Translating',
  rendering: 'Rendering output',
  completed: 'Complete',
  failed: 'Failed',
  cancelled: 'Cancelled',
};

export default function ProgressBar({ jobId, onComplete, onError, onCancel }: ProgressBarProps) {
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState('pending');
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const pollStatus = useCallback(async () => {
    if (!jobId) return;
    try {
      const job = await api.get<JobStatus>(`/jobs/${jobId}`);
      setProgress(job.progress * 100);
      setStatus(job.status);

      if (job.status === 'completed') {
        stopPolling();
        onComplete?.(job.id);
      } else if (job.status === 'failed' || job.status === 'cancelled') {
        stopPolling();
        if (job.error_message) {
          setError(job.error_message);
          onError?.(job.error_message);
        }
      }
    } catch (err) {
      stopPolling();
      const msg = err instanceof Error ? err.message : 'Failed to check status';
      setError(msg);
      onError?.(msg);
    }
  }, [jobId, onComplete, onError, stopPolling]);

  useEffect(() => {
    if (!jobId) return;

    // Initial poll
    pollStatus();

    // Start polling every 2 seconds
    intervalRef.current = setInterval(pollStatus, 2000);

    return () => {
      stopPolling();
    };
  }, [jobId, pollStatus, stopPolling]);

  const handleCancel = async () => {
    if (!jobId) return;
    try {
      await api.post(`/jobs/${jobId}/cancel`);
      stopPolling();
      setStatus('cancelled');
      onCancel?.();
    } catch {
      // Ignore cancel errors
    }
  };

  const displayStatus = STATUS_LABELS[status] || status;
  const isActive = ['pending', 'running', 'detecting', 'rendering'].includes(status);
  const isComplete = status === 'completed';
  const isFailed = status === 'failed';
  const isCancelled = status === 'cancelled';

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          {isActive && (
            <svg className="animate-spin w-4 h-4 text-primary-600" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          )}
          {isComplete && (
            <svg className="w-4 h-4 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          )}
          {isFailed && (
            <svg className="w-4 h-4 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          )}
          {isCancelled && (
            <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
            </svg>
          )}
          <span className={`text-sm font-medium ${
            isFailed ? 'text-red-700' :
            isCancelled ? 'text-gray-500' :
            isComplete ? 'text-green-700' :
            'text-gray-700'
          }`}>
            {displayStatus}
          </span>
        </div>
        <span className="text-sm text-gray-500">{Math.round(progress)}%</span>
      </div>

      <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ease-out ${
            isFailed ? 'bg-red-500' :
            isCancelled ? 'bg-gray-400' :
            isComplete ? 'bg-green-500' :
            'bg-primary-600'
          }`}
          style={{
            width: `${Math.min(100, Math.max(0, progress))}%`,
          }}
        />
      </div>

      {error && (
        <p className="mt-2 text-xs text-red-600">{error}</p>
      )}

      {isActive && onCancel && (
        <div className="mt-3 flex justify-end">
          <button onClick={handleCancel} className="btn-secondary text-xs">
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}
