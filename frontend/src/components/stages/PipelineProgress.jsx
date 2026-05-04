import React from 'react';
import { clsx } from 'clsx';
import { PHASE2_STAGES, STATUS_META } from '../../constants/stages';

function PhaseBar({ label, stages, stageData, active }) {
  const total = stages.length;
  const passed = stages.filter((s) => {
    const d = stageData?.find((x) => x.stage_code === s.code);
    return d?.status === 'PASSED';
  }).length;
  const pct = total ? Math.round((passed / total) * 100) : 0;
  const running = stages.some((s) => {
    const d = stageData?.find((x) => x.stage_code === s.code);
    return d?.status === 'IN_PROGRESS';
  });

  return (
    <div className={clsx('flex-1 border-r border-slate-800 last:border-0', active ? 'opacity-100' : 'opacity-40')}>
      <div className="px-4 py-2">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-xxs text-slate-400 font-medium">{label}</span>
          <span className={clsx('text-xxs font-semibold', running ? 'text-blue-400' : pct === 100 ? 'text-green-400' : 'text-slate-400')}>
            {running ? 'Running' : pct === 100 ? 'Done' : `${pct}%`}
          </span>
        </div>
        <div className="h-1 bg-slate-800 rounded-full overflow-hidden">
          <div
            className={clsx(
              'h-full rounded-full transition-all duration-700',
              running ? 'bg-blue-500 animate-pulse-slow' : pct === 100 ? 'bg-green-500' : 'bg-steel'
            )}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
    </div>
  );
}

export default function PipelineProgress({ stages }) {
  const phase2Stages = PHASE2_STAGES;
  const hasPhase2 = stages?.some((s) => s.stage_code?.startsWith('P2'));
  const hasPhase3 = stages?.some((s) => s.stage_code?.startsWith('P3'));

  return (
    <div className="flex bg-navy-dark border border-slate-800 rounded-xl overflow-hidden">
      <PhaseBar label="Phase 1 · Master DB" stages={[]} stageData={[]} active={true} />
      <PhaseBar label="Phase 2 · AB / GA" stages={phase2Stages} stageData={stages} active={hasPhase2} />
      <PhaseBar label="Phase 3 · Detailing" stages={[]} stageData={stages} active={hasPhase3} />
    </div>
  );
}
