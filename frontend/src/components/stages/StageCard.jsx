import React, { useState } from 'react';
import { RefreshCw, ChevronDown, ChevronUp, Clock } from 'lucide-react';
import { clsx } from 'clsx';
import StatusBadge from '../shared/StatusBadge';
import { STATUS_META, PHASE2_STAGES, PHASE3_STAGES } from '../../constants/stages';
import { fmtDuration, fmtDateTime } from '../../utils/formatters';

function getStageInfo(code) {
  return [...PHASE2_STAGES, ...PHASE3_STAGES].find((s) => s.code === code) || { name: code, description: '' };
}

export default function StageCard({ stage, index, onRerun, isRerunning }) {
  const [expanded, setExpanded] = useState(false);
  const info = getStageInfo(stage.stage_code);
  const meta = STATUS_META[stage.status] || STATUS_META.PENDING;
  const duration = fmtDuration(stage.started_at, stage.completed_at);

  return (
    <div className={clsx('rounded-xl border transition-all duration-200', meta.border, meta.bg, 'bg-opacity-30')}>
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3">
        {/* Step number */}
        <div className={clsx(
          'w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 border',
          stage.status === 'PASSED' ? 'bg-green-900 border-green-600 text-green-300'
          : stage.status === 'FAILED' ? 'bg-red-900 border-red-600 text-red-300'
          : stage.status === 'IN_PROGRESS' ? 'bg-blue-900 border-blue-600 text-blue-300'
          : 'bg-slate-800 border-slate-700 text-slate-400'
        )}>
          {index + 1}
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xxs font-mono text-slate-500">{stage.stage_code}</span>
            <span className="text-xs font-semibold text-white truncate">{info.name}</span>
          </div>
          <p className="text-xxs text-slate-500 mt-0.5 truncate">{info.description}</p>
        </div>

        {/* Status + duration */}
        <div className="flex items-center gap-2 flex-shrink-0">
          {duration && (
            <span className="flex items-center gap-1 text-xxs text-slate-500">
              <Clock size={10} />{duration}
            </span>
          )}
          <StatusBadge status={stage.status} />
        </div>

        {/* Expand + Re-run */}
        <div className="flex items-center gap-1 flex-shrink-0">
          {onRerun && stage.status !== 'PENDING' && stage.status !== 'IN_PROGRESS' && (
            <button
              onClick={() => onRerun(stage.stage_code)}
              disabled={isRerunning}
              title="Re-run stage"
              className="w-6 h-6 rounded flex items-center justify-center text-slate-500 hover:text-white hover:bg-slate-700 transition-colors disabled:opacity-40"
            >
              <RefreshCw size={11} className={isRerunning ? 'animate-spin' : ''} />
            </button>
          )}
          <button
            onClick={() => setExpanded((v) => !v)}
            className="w-6 h-6 rounded flex items-center justify-center text-slate-500 hover:text-white hover:bg-slate-700 transition-colors"
          >
            {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          </button>
        </div>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div className="border-t border-slate-800 px-4 py-3 space-y-2 animate-fade-in">
          <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-xxs">
            <Detail label="Started" value={fmtDateTime(stage.started_at)} />
            <Detail label="Completed" value={fmtDateTime(stage.completed_at)} />
            <Detail label="Duration" value={duration || '—'} />
            <Detail label="Status" value={stage.status} />
          </div>
          {stage.error_message && (
            <div className="bg-red-950 border border-red-800 rounded-lg p-2.5 mt-2">
              <p className="text-xxs text-red-300 font-mono">{stage.error_message}</p>
            </div>
          )}
          {stage.result && Object.keys(stage.result).length > 0 && (
            <div className="bg-slate-900 rounded-lg p-2.5 mt-2">
              <p className="text-xxs text-slate-500 mb-1 font-semibold">Result</p>
              <pre className="text-xxs text-slate-300 font-mono overflow-auto max-h-32">
                {JSON.stringify(stage.result, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Detail({ label, value }) {
  return (
    <div>
      <span className="text-slate-600 uppercase tracking-wide">{label}: </span>
      <span className="text-slate-300">{value || '—'}</span>
    </div>
  );
}
