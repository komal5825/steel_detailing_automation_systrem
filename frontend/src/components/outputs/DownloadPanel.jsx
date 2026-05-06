import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Download, FileJson, FileText, File, FileArchive, FileSpreadsheet, Eye } from 'lucide-react';
import { outputsApi } from '../../api/outputs';
import { fmtFileSize } from '../../utils/formatters';
import OutputPreviewModal from '../shared/OutputPreviewModal';

const OUTPUT_TYPES = [
  { key: 'json', label: 'Status Report', ext: 'JSON', icon: FileJson },
  { key: 'pdf', label: 'Status Report', ext: 'PDF', icon: FileText },
  { key: 'docx', label: 'Status Report', ext: 'DOCX', icon: FileText },
  { key: 'xlsx', label: 'Status Report', ext: 'XLSX', icon: FileSpreadsheet },
];

function outputIcon(extension) {
  if (extension === 'json') return FileJson;
  if (extension === 'zip') return FileArchive;
  if (extension === 'xlsx' || extension === 'xls') return FileSpreadsheet;
  if (['txt', 'pdf', 'docx'].includes(extension)) return FileText;
  return File;
}

export default function DownloadPanel({ projectId, stages }) {
  const [previewFile, setPreviewFile] = useState(null);

  const { data } = useQuery({
    queryKey: ['outputs', projectId],
    queryFn: () => outputsApi.listFiles(projectId),
    enabled: !!projectId,
    refetchInterval: 7000,
  });

  if (!projectId) return null;
  const files = data?.files || [];

  return (
    <div className="rounded-md border border-slate-300 bg-white p-4">
      <div className="flex items-center gap-2 mb-3">
        <Download size={13} className="text-blue-600" />
        <h3 className="text-sm font-bold text-slate-900">Downloads</h3>
      </div>
      <div className="grid grid-cols-2 gap-2">
        {OUTPUT_TYPES.map((ot) => {
          const Icon = ot.icon;
          return (
            <a
              key={ot.key}
              href={outputsApi.reportUrl(projectId, ot.key)}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 rounded border border-slate-200 bg-slate-50 px-2 py-2 text-xs text-slate-800 transition-colors hover:border-blue-300 hover:bg-blue-50"
            >
              <Icon size={13} className="text-blue-600 flex-shrink-0" />
              <span className="flex-1 min-w-0 truncate">{ot.label}</span>
              <span className="rounded bg-white px-1 font-mono text-xxs text-slate-500">{ot.ext}</span>
            </a>
          );
        })}
      </div>

      <div className="mt-4 border-t border-slate-200 pt-3">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-xxs font-semibold uppercase tracking-wide text-slate-500">Generated Files</span>
          <span className="font-mono text-xxs text-slate-500">{files.length}</span>
        </div>
        {files.length === 0 ? (
          <p className="text-xs text-slate-500">No generated output files yet.</p>
        ) : (
          <div className="max-h-36 space-y-1 overflow-y-auto">
            {files.map((file) => {
              const Icon = outputIcon(file.extension);
              const url = outputsApi.downloadUrl(projectId, file.relative_path);
              return (
                <div
                  key={file.relative_path}
                  className="flex items-center gap-2 rounded border border-slate-200 px-2 py-1.5 text-xs text-slate-700 hover:bg-slate-50 group"
                >
                  <Icon size={13} className="text-slate-500" />
                  <span className="min-w-0 flex-1 truncate">{file.relative_path}</span>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setPreviewFile({ ...file, url })}
                      className="opacity-0 group-hover:opacity-100 p-0.5 text-blue-600 hover:bg-blue-50 rounded"
                      title="Preview"
                    >
                      <Eye size={12} />
                    </button>
                    <a
                      href={url}
                      download
                      className="text-slate-400 hover:text-blue-600"
                    >
                      <Download size={12} />
                    </a>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <OutputPreviewModal
        isOpen={!!previewFile}
        onClose={() => setPreviewFile(null)}
        file={previewFile}
        downloadUrl={previewFile?.url}
      />
    </div>
  );
}

