import React, { useCallback, useRef, useState } from 'react';
import {
  AlertCircle,
  CheckCircle,
  DraftingCompass,
  File,
  FileArchive,
  FileCode2,
  FileSpreadsheet,
  FileText,
  Upload,
  X,
} from 'lucide-react';
import { clsx } from 'clsx';
import { fmtFileSize } from '../../utils/formatters';

const ACCEPTED_EXTS = ['.std', '.mbs', '.xml', '.xlsx', '.xls', '.dwg', '.dxf', '.pdf', '.zip', '.rar', '.docx', '.doc'];

function FileKindIcon({ name }) {
  const ext = name.split('.').pop().toLowerCase();
  const className = 'h-4 w-4 text-slate-500';
  if (['zip', 'rar'].includes(ext)) return <FileArchive className={className} />;
  if (['dwg', 'dxf'].includes(ext)) return <DraftingCompass className={className} />;
  if (ext === 'pdf') return <FileText className={className} />;
  if (['xlsx', 'xls'].includes(ext)) return <FileSpreadsheet className={className} />;
  if (['std', 'mbs', 'xml'].includes(ext)) return <FileCode2 className={className} />;
  return <File className={className} />;
}

export default function FileUploadPanel({ projectId, onUpload, uploading }) {
  const [files, setFiles] = useState([]);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef(null);

  const addFiles = useCallback((incoming) => {
    const arr = Array.from(incoming).map((file) => ({
      file,
      id: Math.random().toString(36).slice(2),
      status: 'queued',
    }));
    setFiles((prev) => [...prev, ...arr]);
  }, []);

  const onDrop = useCallback((event) => {
    event.preventDefault();
    setDragOver(false);
    addFiles(event.dataTransfer.files);
  }, [addFiles]);

  const removeFile = (id) => setFiles((prev) => prev.filter((file) => file.id !== id));
  const totalSize = files.reduce((acc, item) => acc + item.file.size, 0);

  const handleUpload = async () => {
    if (!projectId || files.length === 0) return;
    const queued = files.filter((item) => item.status === 'queued');
    if (queued.length === 0) return;

    setFiles((prev) =>
      prev.map((item) => (item.status === 'queued' ? { ...item, status: 'uploading' } : item))
    );

    try {
      const fd = new FormData();
      queued.forEach((item) => fd.append('files', item.file));
      await onUpload(fd);
      setFiles((prev) =>
        prev.map((item) => (item.status === 'uploading' ? { ...item, status: 'done' } : item))
      );
    } catch {
      setFiles((prev) =>
        prev.map((item) => (item.status === 'uploading' ? { ...item, status: 'error' } : item))
      );
    }
  };

  return (
    <div className="grid grid-cols-2 gap-4">
      <div
        onDragOver={(event) => {
          event.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        className={clsx(
          'flex cursor-pointer flex-col items-center justify-center gap-3 rounded-md border-2 border-dashed py-10 transition-colors',
          dragOver ? 'border-blue-500 bg-blue-50' : 'border-slate-300 bg-slate-50 hover:border-slate-400'
        )}
        onClick={() => inputRef.current?.click()}
      >
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-white shadow-sm ring-1 ring-slate-200">
          <Upload size={18} className="text-blue-600" />
        </div>
        <div className="text-center">
          <p className="text-xs font-semibold text-slate-900">Drop files or click to browse</p>
          <p className="mt-1 text-xxs text-slate-500">STD, MBS, DWG, DXF, PDF, XLSX, DOCX, ZIP and RAR</p>
        </div>
        <button
          type="button"
          className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-800 transition-colors hover:border-blue-300 hover:bg-blue-50"
          onClick={(event) => {
            event.stopPropagation();
            inputRef.current?.click();
          }}
        >
          Select files
        </button>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPTED_EXTS.join(',')}
          className="hidden"
          onChange={(event) => addFiles(event.target.files)}
        />
      </div>

      <div className="flex flex-col rounded-md border border-slate-300 bg-white">
        <div className="flex items-center justify-between border-b border-slate-200 px-4 py-2.5">
          <span className="text-xs font-bold text-slate-900">Upload Queue</span>
          {files.length > 0 && (
            <button onClick={() => setFiles([])} className="text-xxs text-slate-500 hover:text-red-600">
              Clear all
            </button>
          )}
        </div>
        <div className="min-h-36 max-h-52 flex-1 overflow-y-auto">
          {files.length === 0 ? (
            <p className="mt-6 text-center text-xxs italic text-slate-500">No files queued.</p>
          ) : (
            <ul className="divide-y divide-slate-200">
              {files.map((item) => (
                <li key={item.id} className="flex items-center gap-2.5 px-3 py-2">
                  <FileKindIcon name={item.file.name} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-medium text-slate-900">{item.file.name}</p>
                    <p className="text-xxs text-slate-500">{fmtFileSize(item.file.size)}</p>
                  </div>
                  {item.status === 'done' && <CheckCircle size={13} className="flex-shrink-0 text-emerald-600" />}
                  {item.status === 'error' && <AlertCircle size={13} className="flex-shrink-0 text-red-600" />}
                  {item.status === 'uploading' && (
                    <div className="h-3 w-3 flex-shrink-0 animate-spin rounded-full border border-blue-500 border-t-transparent" />
                  )}
                  {item.status === 'queued' && (
                    <button onClick={() => removeFile(item.id)} className="flex-shrink-0 text-slate-400 hover:text-red-600">
                      <X size={12} />
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="flex items-center justify-between border-t border-slate-200 px-4 py-2.5">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-xxs uppercase tracking-wide text-slate-500">Files queued</p>
              <p className="text-sm font-bold text-slate-900">{files.filter((file) => file.status === 'queued').length}</p>
            </div>
            <div>
              <p className="text-xxs uppercase tracking-wide text-slate-500">Total size</p>
              <p className="text-sm font-bold text-slate-900">{fmtFileSize(totalSize)}</p>
            </div>
          </div>
          <button
            onClick={handleUpload}
            disabled={files.length === 0 || uploading || files.every((file) => file.status !== 'queued')}
            className={clsx(
              'rounded-md px-3 py-2 text-xs font-semibold transition-colors',
              files.length > 0 && !uploading && files.some((file) => file.status === 'queued')
                ? 'bg-amber-500 text-white hover:bg-amber-600'
                : 'cursor-not-allowed bg-slate-100 text-slate-400'
            )}
          >
            {uploading ? 'Uploading...' : 'Start P2-01'}
          </button>
        </div>
      </div>
    </div>
  );
}
