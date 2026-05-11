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
  Trash2,
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

export default function FileUploadPanel({ projectId, onUpload, onClearAll, onDelete, uploading }) {
  const [files, setFiles] = useState([]);
  const [dragOver, setDragOver] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
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
    setUploadProgress(0);

    try {
      const fd = new FormData();
      queued.forEach((item) => fd.append('files', item.file));
      
      const response = await onUpload(fd, (progressEvent) => {
        const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
        setUploadProgress(percentCompleted);
      });

      // Support both direct array response and wrapped { uploaded: [...] } shape.
      const uploadedFiles = Array.isArray(response)
        ? response
        : Array.isArray(response?.uploaded)
        ? response.uploaded
        : [];
      
      setFiles((prev) =>
        prev.map((item) => {
          if (item.status === 'uploading') {
            const match = uploadedFiles.find(f => f.original_filename === item.file.name);
            return { ...item, status: 'done', dbId: match?.id };
          }
          return item;
        })
      );
    } catch {
      setFiles((prev) =>
        prev.map((item) => (item.status === 'uploading' ? { ...item, status: 'error' } : item))
      );
    } finally {
      setUploadProgress(0);
    }
  };

  const handleClearAll = () => {
    setFiles([]);
    if (onClearAll) onClearAll();
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
          <p className="mt-1.5 rounded bg-amber-50 px-2 py-0.5 text-xxs font-medium text-amber-700">
            New upload resets all previous stage results
          </p>
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
            <button onClick={handleClearAll} className="text-xxs text-slate-500 hover:text-red-600">
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
                    <div className="flex items-center gap-2">
                      <p className="truncate text-xs font-medium text-slate-900">{item.file.name}</p>
                      <span className="text-[10px] font-mono font-bold text-slate-400">({fmtFileSize(item.file.size)})</span>
                    </div>
                  </div>
                  {item.status === 'done' && (
                    <button 
                      onClick={() => onDelete?.(item.dbId)} 
                      className="flex-shrink-0 text-slate-400 hover:text-red-600 transition-colors"
                      title="Remove from Project"
                    >
                      <Trash2 size={12} />
                    </button>
                  )}
                  {item.status === 'error' && (
                    <div className="flex flex-shrink-0 items-center gap-1">
                      <AlertCircle size={13} className="text-red-500" title="Upload failed" />
                      <button
                        onClick={() => removeFile(item.id)}
                        title="Remove"
                        className="rounded p-0.5 text-red-400 hover:text-red-600"
                      >
                        <X size={11} />
                      </button>
                    </div>
                  )}
                  {item.status === 'uploading' && (
                    <div className="flex items-center gap-2">
                      <div className="relative h-4 w-4">
                        <svg className="h-4 w-4 -rotate-90">
                          <circle
                            cx="8"
                            cy="8"
                            r="7"
                            fill="transparent"
                            stroke="currentColor"
                            strokeWidth="2"
                            className="text-slate-200"
                          />
                          <circle
                            cx="8"
                            cy="8"
                            r="7"
                            fill="transparent"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeDasharray={44}
                            strokeDashoffset={44 - (44 * uploadProgress) / 100}
                            className="text-blue-600 transition-all duration-300"
                          />
                        </svg>
                      </div>
                      <span className="text-[10px] font-mono font-bold text-blue-600">{uploadProgress}%</span>
                    </div>
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
        {uploading && (
          <div className="bg-blue-50 px-4 py-2 border-t border-blue-100">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[10px] font-bold text-blue-700 uppercase tracking-wider">Batch Uploading...</span>
              <span className="text-[10px] font-mono font-bold text-blue-700">{uploadProgress}%</span>
            </div>
            <div className="h-1.5 w-full bg-blue-100 rounded-full overflow-hidden">
              <div 
                className="h-full bg-blue-600 transition-all duration-300 rounded-full shadow-[0_0_8px_rgba(37,99,235,0.4)]" 
                style={{ width: `${uploadProgress}%` }} 
              />
            </div>
          </div>
        )}
        <div className="flex items-center justify-between border-t border-slate-200 px-4 py-2.5 bg-slate-50/50">
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
            {uploading
              ? `Uploading… ${uploadProgress}%`
              : files.filter((f) => f.status === 'queued').length === 1
              ? 'Upload & Run P2-01'
              : files.filter((f) => f.status === 'queued').length > 1
              ? `Upload ${files.filter((f) => f.status === 'queued').length} Files & Run P2-01`
              : 'Start P2-01'}
          </button>
        </div>
      </div>
    </div>
  );
}
