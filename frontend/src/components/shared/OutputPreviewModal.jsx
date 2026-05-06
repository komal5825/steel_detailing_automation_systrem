import React from 'react';
import { X, ExternalLink, FileText, FileJson, ImageIcon } from 'lucide-react';

export default function OutputPreviewModal({ isOpen, onClose, file, downloadUrl }) {
  if (!isOpen || !file) return null;

  const isImage = ['png', 'jpg', 'jpeg', 'gif', 'svg'].includes(file.extension);
  const isJson = file.extension === 'json';
  const isText = ['txt', 'log', 'md'].includes(file.extension);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-6 backdrop-blur-sm">
      <div className="flex h-full w-full max-w-5xl flex-col rounded-lg bg-white shadow-2xl ring-1 ring-slate-200">
        <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
          <div className="flex items-center gap-2">
            {isImage ? <ImageIcon size={16} className="text-blue-600" /> : isJson ? <FileJson size={16} className="text-amber-600" /> : <FileText size={16} className="text-slate-600" />}
            <h3 className="text-sm font-bold text-slate-900">{file.name || file.relative_path}</h3>
          </div>
          <div className="flex items-center gap-2">
            <a
              href={downloadUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 rounded-md bg-slate-100 px-2 py-1 text-xxs font-semibold text-slate-700 hover:bg-slate-200"
            >
              <ExternalLink size={12} /> Open Raw
            </a>
            <button
              onClick={onClose}
              className="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-900"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-auto bg-slate-50 p-4">
          <div className="mx-auto flex min-h-full items-center justify-center rounded border border-slate-200 bg-white shadow-sm p-8">
            {isImage ? (
              <img src={downloadUrl} alt={file.name} className="max-h-full max-w-full object-contain" />
            ) : isJson || isText ? (
              <FileContent url={downloadUrl} isJson={isJson} />
            ) : (
              <div className="text-center">
                <FileText size={48} className="mx-auto mb-4 text-slate-300" />
                <p className="text-sm text-slate-500">Preview not supported for this file type.</p>
                <a
                  href={downloadUrl}
                  className="mt-4 inline-block rounded bg-blue-600 px-4 py-2 text-xs font-semibold text-white hover:bg-blue-700"
                >
                  Download to View
                </a>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function FileContent({ url, isJson }) {
  const [content, setContent] = React.useState('');
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState(null);

  React.useEffect(() => {
    fetch(url)
      .then((res) => res.text())
      .then((text) => {
        setContent(text);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [url]);

  if (loading) return <div className="animate-pulse text-xs text-slate-400">Loading content...</div>;
  if (error) return <div className="text-xs text-red-500">Error: {error}</div>;

  return (
    <pre className="w-full overflow-auto font-mono text-xs leading-relaxed text-slate-800">
      {isJson ? JSON.stringify(JSON.parse(content), null, 2) : content}
    </pre>
  );
}
