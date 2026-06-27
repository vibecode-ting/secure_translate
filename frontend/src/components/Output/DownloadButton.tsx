const BASE_URL = import.meta.env.VITE_API_URL || '/api';

interface DownloadButtonProps {
  documentId: string;
  jobId?: string;
  filename?: string;
}

export default function DownloadButton({ documentId, jobId, filename }: DownloadButtonProps) {
  const handleDownload = () => {
    if (!jobId) {
      alert('No translation job available for download');
      return;
    }
    const url = `${BASE_URL}/documents/${documentId}/download/${jobId}`;
    const a = document.createElement('a');
    a.href = url;
    a.download = filename || `translated_${documentId}.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  return (
    <button onClick={handleDownload} className="btn-primary" disabled={!jobId}>
      <svg className="w-4 h-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
      </svg>
      Download Translated
    </button>
  );
}
