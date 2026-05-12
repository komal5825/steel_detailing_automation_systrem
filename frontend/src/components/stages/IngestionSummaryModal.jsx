import React from 'react';
import {
  CheckCircle2,
  AlertCircle,
  FileText,
  Database,
  ShieldCheck,
  X,
  ChevronRight,
  Info
} from 'lucide-react';
import { clsx } from 'clsx';
import StatusBadge from '../shared/StatusBadge';

export default function IngestionSummaryModal({ result, onClose }) {
  if (!result) return null;

  const isSuccess = result.status === 'success';
  const governing = result.governing_file;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-2xl scale-in-center overflow-hidden rounded-xl border border-slate-200 bg-white shadow-2xl">
        {/* Header */}
        <div className={clsx(
          "flex items-center justify-between border-b px-6 py-4",
          isSuccess ? "bg-emerald-50 border-emerald-100" : "bg-amber-50 border-amber-100"
        )}>
          <div className="flex items-center gap-3">
            {isSuccess ? (
              <CheckCircle2 className="text-emerald-600" size={24} />
            ) : (
              <AlertCircle className="text-amber-600" size={24} />
            )}
            <div>
              <h2 className="text-lg font-bold text-slate-900">Ingestion Complete</h2>
              <p className="text-xs text-slate-600">Design File Injection (P2-01)</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-full p-1 text-slate-400 hover:bg-slate-200 hover:text-slate-600 transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="max-h-[70vh] overflow-y-auto p-6">
          {/* Summary Stats */}
          <div className="grid grid-cols-3 gap-4 mb-8">
            <StatCard
              label="Files Parsed"
              value={`${result.parsed_files}/${result.files_found}`}
              subValue={`${result.failed_files} failed`}
              icon={FileText}
              color="blue"
            />
            <StatCard
              label="Fields Extracted"
              value={result.extracted_fields}
              subValue={`${result.normalized_fields} normalized`}
              icon={Database}
              color="amber"
            />
            <StatCard
              label="Status"
              value={isSuccess ? "PASS" : "PARTIAL"}
              subValue="Quality Gate 1"
              icon={ShieldCheck}
              color={isSuccess ? "emerald" : "amber"}
            />
          </div>

          {/* Governing File Section */}
          <div className="mb-8 rounded-lg border border-blue-100 bg-blue-50/50 p-4">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="flex items-center gap-2 text-sm font-bold text-slate-900">
                <Info size={16} className="text-blue-600" />
                Governing Design File
              </h3>
              {governing && (
                <span className="rounded bg-blue-600 px-2 py-0.5 font-mono text-xxs font-bold text-white">
                  {governing.classification_confidence}% MATCH
                </span>
              )}
            </div>

            {governing ? (
              <div className="flex items-center justify-between gap-4">
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-blue-950">{governing.original_filename}</p>
                  <p className="mt-1 font-mono text-xxs text-blue-700 uppercase tracking-wider">
                    {governing.file_type} / {governing.source_application}
                  </p>
                </div>
                <div className="flex-shrink-0 text-right">
                  <p className="text-xxs font-semibold text-blue-600 uppercase">Role</p>
                  <p className="text-xs font-bold text-blue-900 uppercase">{governing.likely_role}</p>
                </div>
              </div>
            ) : (
              <p className="text-xs text-slate-500 italic text-center py-2">No governing file identified.</p>
            )}
          </div>

          {/* Details / Metadata List (if any) */}
          {result.governing_details && Object.keys(result.governing_details).length > 0 && (
            <div className="mb-8">
              <h3 className="mb-3 text-xs font-bold uppercase tracking-wider text-slate-500">Structural Metadata</h3>
              <div className="grid grid-cols-2 gap-x-8 gap-y-3 rounded-lg border border-slate-200 p-4">
                {Object.entries(result.governing_details).map(([key, val]) => (
                  <div key={key} className="flex items-center justify-between border-b border-slate-100 pb-2 last:border-0 last:pb-0">
                    <span className="text-xxs font-medium text-slate-500 uppercase">{key.replace(/_/g, ' ')}</span>
                    <span className="text-xs font-bold text-slate-900">{val}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 border-t bg-slate-50 px-6 py-4">
          <button
            onClick={onClose}
            className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            Review Files
          </button>
          <button
            onClick={onClose}
            className="flex items-center gap-2 rounded-md bg-slate-900 px-6 py-2 text-sm font-bold text-white hover:bg-blue-700 transition-all shadow-md"
          >
            Continue to Validation <ChevronRight size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value, subValue, icon: Icon, color }) {
  const colors = {
    blue: "text-blue-600 bg-blue-50 border-blue-100",
    amber: "text-amber-600 bg-amber-50 border-amber-100",
    emerald: "text-emerald-600 bg-emerald-50 border-emerald-100",
    slate: "text-slate-600 bg-slate-50 border-slate-100",
  };

  return (
    <div className={clsx("rounded-xl border p-4 shadow-sm", colors[color])}>
      <div className="mb-2 flex items-center justify-between">
        <Icon size={18} />
        <span className="text-[10px] font-bold uppercase tracking-wider opacity-70">{label}</span>
      </div>
      <div className="text-xl font-black">{value}</div>
      <div className="mt-1 text-[10px] font-medium uppercase opacity-60">{subValue}</div>
    </div>
  );
}
