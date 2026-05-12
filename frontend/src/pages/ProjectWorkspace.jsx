import React from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Activity,
  AlertOctagon,
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Database,
  Download,
  FileCheck2,
  FileSearch,
  FileText,
  Files,
  GitBranch,
  Lock,
  Play,
  RefreshCw,
  ShieldCheck,
  Star,
  Trash2,
  UploadCloud,
  X,
} from 'lucide-react';
import { clsx } from 'clsx';
import { projectsApi } from '../api/projects';
import { stagesApi } from '../api/stages';
import { PHASE2_STAGES, PHASE3_STAGES, STATUS_META } from '../constants/stages';
import { usePipelineStatus, useStages } from '../hooks/useStages';
import { useWebSocket } from '../hooks/useWebSocket';
import FileUploadPanel from '../components/project/FileUploadPanel';
import DownloadPanel from '../components/outputs/DownloadPanel';
import LiveLogPanel from '../components/stages/LiveLogPanel';
import StatusBadge from '../components/shared/StatusBadge';
import TopBar from '../components/layout/TopBar';
import LoadingSpinner from '../components/shared/LoadingSpinner';
import { useNotificationStore } from '../store/notificationStore';
import { fmtDateTime } from '../utils/formatters';
import FieldReviewPanel from '../components/stages/FieldReviewPanel';
import { outputsApi } from '../api/outputs';
import IngestionSummaryModal from '../components/stages/IngestionSummaryModal';
import OutputPreviewModal from '../components/shared/OutputPreviewModal';

const VALIDATORS = {
  'P2-01': 'File inventory, format check, readability check',
  'P2-02': 'Field check, data quality check, logical check',
  'P2-03': 'Data accuracy, unit check, standard check',
  'P2-04': 'Geometry, consistency, standard check',
  'P2-05': 'Code, clash, tolerance check',
  'P3-01': 'Layout, quantity, BOQ check',
  'P3-02': 'Detail, dimension, standard check',
  'P3-03': 'Mark, quantity, weight check',
  'P3-04': 'Sequence, reference, consistency check',
  'P3-05': 'End-to-end, package, approval check',
};

// Derive human-readable pending reason from checkpoint gate_data
function pendingValidatorReason(stageCode, checkpoint) {
  if (!checkpoint || checkpoint.gate_status === 'PASS') return null;
  const gd = checkpoint.gate_data || {};

  if (stageCode === 'P2-01') {
    return {
      validator: 'File Ingestion Validator',
      reason: 'Stage has not run yet or produced no parseable files',
      blocking_dependency: 'At least one valid design file must be successfully parsed',
      recommended_fix: 'Upload a valid MBS / STAAD / ETABS / DXF file and re-run P2-01',
    };
  }
  if (stageCode === 'P2-02') {
    const abMissing = gd.ab_missing || [];
    const gaMissing = gd.ga_missing || [];
    const total = new Set([...abMissing, ...gaMissing]).size;
    return {
      validator: 'Completeness Validator',
      reason: total
        ? `${total} mandatory field(s) still unresolved after fallback (AB: ${abMissing.length}, GA: ${gaMissing.length})`
        : 'Completeness gate has not been evaluated yet',
      blocking_dependency: 'All AB-required and GA-required fields must be present or fallback-resolved',
      recommended_fix: total
        ? `Provide missing fields via the Field Review panel or upload a more complete source file. Missing: ${[...new Set([...abMissing, ...gaMissing])].slice(0, 8).join(', ')}${total > 8 ? ` … +${total - 8} more` : ''}`
        : 'Run P2-02 completeness check first',
    };
  }
  if (stageCode === 'P2-03') {
    const missing = gd.missing_ab_fields || [];
    return {
      validator: 'AB Generation Validator',
      reason: missing.length
        ? `AB generation blocked — ${missing.length} required AB field(s) missing`
        : 'AB generation has not been attempted yet',
      blocking_dependency: 'All AB-required fields must be resolved before anchor bolt drawings can be generated',
      recommended_fix: missing.length
        ? `Resolve missing AB fields: ${missing.slice(0, 5).join(', ')}`
        : 'Ensure P2-02 passes with no AB blockers, then re-run P2-03',
    };
  }
  if (stageCode === 'P2-04') {
    const missing = gd.missing_ga_fields || [];
    return {
      validator: 'GA Generation Validator',
      reason: missing.length
        ? `GA generation blocked — ${missing.length} required GA field(s) missing`
        : 'GA generation has not been attempted yet',
      blocking_dependency: 'All GA-required fields must be resolved before general arrangement can be generated',
      recommended_fix: missing.length
        ? `Resolve missing GA fields: ${missing.slice(0, 5).join(', ')}`
        : 'Ensure P2-02 passes with no GA blockers, then re-run P2-04',
    };
  }
  if (stageCode === 'P2-05') {
    return {
      validator: 'AB/GA Output Validator',
      reason: 'AB and GA output files have not been validated yet',
      blocking_dependency: 'Both anchor_bolt_layout.json and general_arrangement.json must exist and pass rule checks',
      recommended_fix: 'Complete P2-03 and P2-04 successfully, then run P2-05 validation',
    };
  }
  return null;
}

// Extract per-stage field metrics from result dict
function stageFieldMetrics(stage) {
  const r = stage?.result || {};
  const code = stage?.stage_code;

  if (code === 'P2-01') {
    if (r.files_found === undefined) return null;
    return [
      { label: 'Files Found', value: r.files_found ?? '—' },
      { label: 'Parsed', value: r.parsed_files ?? '—' },
      { label: 'Failed', value: r.failed_files ?? '—', tone: r.failed_files > 0 ? 'red' : 'green' },
      { label: 'Fields Extracted', value: r.extracted_fields ?? '—' },
    ];
  }
  if (code === 'P2-02') {
    const fc = r.field_completion;
    if (!fc) return null;
    return [
      { label: 'Total Fields', value: fc.Total ?? '—' },
      { label: 'Extracted', value: fc.Extracted ?? '—', tone: 'green' },
      { label: 'Calculated', value: fc.Calculated ?? '—', tone: 'blue' },
      { label: 'Fallback', value: fc.Fallback ?? '—', tone: 'amber' },
      { label: 'Failed', value: fc.Failed ?? '—', tone: fc.Failed > 0 ? 'red' : 'green' },
    ];
  }
  if (code === 'P2-03') {
    const ab = r.ab_readiness;
    if (!ab) return null;
    return [
      { label: 'AB Required', value: ab.required_count ?? '—' },
      { label: 'Present', value: ab.present_count ?? '—', tone: 'green' },
      { label: 'Missing', value: ab.missing_count ?? '—', tone: ab.missing_count > 0 ? 'red' : 'green' },
    ];
  }
  if (code === 'P2-04') {
    const ga = r.ga_readiness;
    if (!ga) return null;
    return [
      { label: 'GA Required', value: ga.required_count ?? '—' },
      { label: 'Present', value: ga.present_count ?? '—', tone: 'green' },
      { label: 'Missing', value: ga.missing_count ?? '—', tone: ga.missing_count > 0 ? 'red' : 'green' },
    ];
  }
  return null;
}

const isRunning = (status) => status === 'RUNNING' || status === 'IN_PROGRESS';
const isDone = (status) => status === 'PASSED' || status === 'PASS_WITH_WARNINGS';

function mergeStages(defs, rows, locked = false) {
  const byCode = new Map((rows || []).map((stage) => [stage.stage_code, stage]));
  return defs.map((info) => ({
    ...info,
    stage_code: info.code,
    status: byCode.get(info.code)?.status || 'PENDING',
    started_at: byCode.get(info.code)?.started_at || null,
    completed_at: byCode.get(info.code)?.completed_at || null,
    error_message: byCode.get(info.code)?.error_message || null,
    result: byCode.get(info.code)?.result || {},
    ui_locked: locked,
  }));
}

function phaseProgress(stages) {
  if (!stages?.length) return 0;
  return Math.round((stages.filter((stage) => isDone(stage.status)).length / stages.length) * 100);
}

function designCandidates(files) {
  return [...(files || [])]
    .filter((file) => file.file_category === 'design_file' || file.likely_role === 'governing')
    .sort((a, b) => b.classification_confidence - a.classification_confidence);
}

function stageStatus(stages, code) {
  return stages.find((stage) => stage.stage_code === code)?.status || 'PENDING';
}

function summarizeStageReason(stage) {
  const msg = stage?.error_message;
  if (msg) return msg.split(':').pop().split('\n')[0].trim();
  const blockers = stage?.result?.blocking_issues;
  if (Array.isArray(blockers) && blockers.length) {
    const first = blockers[0];
    if (typeof first === 'string') return first;
    return first?.note || first?.field_code || 'Blocking issue detected';
  }
  if (stage?.ui_locked) return 'Locked by upstream gate';
  return 'No failure detail provided by backend';
}

function fullStageReason(stage) {
  if (stage?.error_message) return stage.error_message;
  const blockers = stage?.result?.blocking_issues;
  if (Array.isArray(blockers) && blockers.length) {
    return blockers
      .map((b) => (typeof b === 'string' ? b : `${b.field_code || 'UNKNOWN'}: ${b.note || 'Blocking issue'}`))
      .join('\n');
  }
  if (stage?.ui_locked) return 'Locked by upstream gate. Resolve upstream failed/blocked stage first.';
  return 'No detailed failure reason returned by backend.';
}

function blockerFixHints(stage) {
  const blockers = stage?.result?.blocking_issues;
  if (!Array.isArray(blockers) || !blockers.length) return [];
  return blockers.slice(0, 5).map((b) => {
    if (typeof b === 'string') {
      return `Review blocker: ${b}`;
    }
    const field = b.field_code || 'unknown field';
    const affects = Array.isArray(b.affects) && b.affects.length ? ` (${b.affects.join('/')})` : '';
    const note = b.note ? `: ${b.note}` : '';
    return `Provide/correct ${field}${affects}${note}`;
  });
}

function formatApiError(error) {
  if (!error) return 'Unknown error';
  const parts = [error.message || 'Request failed'];
  if (error.stage) parts.push(`Stage: ${error.stage}`);
  if (error.rootCause) parts.push(`Root cause: ${error.rootCause}`);
  if (error.suggestedFix) parts.push(`Fix: ${error.suggestedFix}`);
  return parts.join(' | ');
}

export default function ProjectWorkspace() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { add } = useNotificationStore();

  const [showIngestionModal, setShowIngestionModal] = React.useState(false);
  const [ingestionResult, setIngestionResult] = React.useState(null);
  const [selectedAgentCode, setSelectedAgentCode] = React.useState(null);

  useWebSocket(projectId);

  const { data: project, isLoading: loadingProject } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => projectsApi.getOne(projectId),
    enabled: !!projectId,
  });

  const { data: files = [], isLoading: loadingFiles } = useQuery({
    queryKey: ['projectFiles', projectId],
    queryFn: () => projectsApi.getFiles(projectId),
    enabled: !!projectId,
    refetchInterval: 5000,
  });

  const { data: stages = [], isLoading: loadingStages } = useStages(projectId);
  const { data: pipelineStatus } = usePipelineStatus(projectId);
  const { data: checkpoints = [] } = useQuery({
    queryKey: ['checkpoints', projectId],
    queryFn: () => stagesApi.getCheckpoints(projectId),
    enabled: !!projectId,
    refetchInterval: 5000,
  });
  const { data: executionLogs = [] } = useQuery({
    queryKey: ['executionLogs', projectId],
    queryFn: () => stagesApi.getExecutionLogs(projectId, 200),
    enabled: !!projectId,
    refetchInterval: 5000,
  });

  const uploadAndIngest = useMutation({
    mutationFn: async ({ formData, onProgress }) => {
      const uploaded = await projectsApi.uploadFiles(projectId, formData, {
        onUploadProgress: onProgress,
      });
      const ingestion = await stagesApi.runStage(projectId, 'P2-01');
      return { uploaded, ingestion };
    },
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['projectFiles', projectId] });
      qc.invalidateQueries({ queryKey: ['stages', projectId] });
      qc.invalidateQueries({ queryKey: ['checkpoints', projectId] });
      qc.invalidateQueries({ queryKey: ['pipeline', projectId] });
      setIngestionResult(data.ingestion);
      setShowIngestionModal(true);
      add({ type: 'success', text: 'P2-01 ingestion complete — running P2-02 → P2-05 automatically' });
      // Auto-advance: P2-01 passed so kick off the rest of the pipeline immediately.
      // runPipeline handles failures gracefully (422 → onError) so this is safe.
      runPipeline.mutate('P2-02');
    },
    onError: (error) => {
      // Queries must refresh even on failure — the upload succeeded and reset stages,
      // so the UI needs to reflect the current DB state (new files, PENDING stages).
      qc.invalidateQueries({ queryKey: ['projectFiles', projectId] });
      qc.invalidateQueries({ queryKey: ['stages', projectId] });
      qc.invalidateQueries({ queryKey: ['checkpoints', projectId] });
      qc.invalidateQueries({ queryKey: ['pipeline', projectId] });
      add({ type: 'error', text: `P2-01: ${formatApiError(error)}` });
    },
  });

  const resetIntake = useMutation({
    mutationFn: () => stagesApi.resetIntake(projectId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['projectFiles', projectId] });
      qc.invalidateQueries({ queryKey: ['stages', projectId] });
      qc.invalidateQueries({ queryKey: ['checkpoints', projectId] });
      qc.invalidateQueries({ queryKey: ['pipeline', projectId] });
      add({ type: 'success', text: 'Intake reset and files cleared' });
    },
    onError: (error) => add({ type: 'error', text: formatApiError(error) }),
  });

  const runPipeline = useMutation({
    mutationFn: (fromStage) => stagesApi.runPipeline(projectId, fromStage),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['stages', projectId] });
      qc.invalidateQueries({ queryKey: ['pipeline', projectId] });
      add({ type: 'success', text: 'Phase 2 pipeline run completed' });
    },
    onError: (error) => add({ type: 'error', text: formatApiError(error) }),
  });

  const deleteFile = useMutation({
    mutationFn: (fileId) => projectsApi.deleteFile(projectId, fileId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['projectFiles', projectId] });
      qc.invalidateQueries({ queryKey: ['stages', projectId] });
      qc.invalidateQueries({ queryKey: ['checkpoints', projectId] });
      qc.invalidateQueries({ queryKey: ['pipeline', projectId] });
      add({ type: 'success', text: 'File deleted and pipeline reset to PENDING' });
    },
    onError: (error) => add({ type: 'error', text: formatApiError(error) }),
  });

  const rerunStage = useMutation({
    mutationFn: (stageCode) => stagesApi.runStage(projectId, stageCode),
    onSuccess: (data, stageCode) => {
      qc.invalidateQueries({ queryKey: ['stages', projectId] });
      qc.invalidateQueries({ queryKey: ['projectFiles', projectId] });
      qc.invalidateQueries({ queryKey: ['checkpoints', projectId] });
      qc.invalidateQueries({ queryKey: ['pipeline', projectId] });
      // Auto-open output review for all stages (P2-01 shows file outputs, not the
      // ingestion modal — that modal is only for the upload+ingest combined flow).
      setSelectedAgentCode(stageCode);
      add({ type: 'success', text: `${stageCode} completed — output review opened` });
    },
    onError: (error) => {
      qc.invalidateQueries({ queryKey: ['stages', projectId] });
      qc.invalidateQueries({ queryKey: ['checkpoints', projectId] });
      add({ type: 'error', text: formatApiError(error) });
    },
  });


  const phase2 = React.useMemo(() => mergeStages(PHASE2_STAGES, stages), [stages]);
  const phase2Complete = phase2.every((stage) => isDone(stage.status));
  const phase3Locked = !phase2Complete && !pipelineStatus?.phase3_eligible;
  const phase3 = React.useMemo(() => mergeStages(PHASE3_STAGES, stages, phase3Locked), [stages, phase3Locked]);
  const candidates = React.useMemo(() => designCandidates(files), [files]);
  const topConfidence = candidates[0]?.classification_confidence;
  const equalCandidateGate = candidates.filter((file) => file.classification_confidence === topConfidence).length > 1;
  const parsedFiles = files.filter((file) => file.processing_status === 'PARSED').length;
  const warnings = phase2.filter((stage) => ['FAILED', 'AWAITING_INPUT', 'BLOCKED'].includes(stage.status)).length;
  const activeAgents = phase2.filter((stage) => isRunning(stage.status)).length;
  const failedStages = [...phase2, ...phase3].filter((stage) => stage.status === 'FAILED');
  const blockedStages = [...phase2, ...phase3].filter((stage) => stage.status === 'BLOCKED' || stage.ui_locked);
  const awaitingInputStages = [...phase2, ...phase3].filter((stage) => stage.status === 'AWAITING_INPUT');
  const latestCheckpointByStage = React.useMemo(() => {
    const map = new Map();
    for (const cp of checkpoints || []) {
      map.set(cp.stage_code, cp);
    }
    return map;
  }, [checkpoints]);

  if (loadingProject) {
    return (
      <div className="flex h-screen items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col">
      <TopBar
        title={project?.name || 'Project'}
        subtitle={project?.proposal_id}
        actions={
          <div className="flex items-center gap-2">
            <button
              onClick={() => navigate('/')}
              className="flex h-8 items-center gap-1.5 rounded-md border border-slate-300 bg-white px-3 text-xs font-semibold text-slate-700 hover:border-slate-400"
            >
              <ArrowLeft size={13} /> Back
            </button>
            <button
              onClick={() => runPipeline.mutate('P2-02')}
              disabled={runPipeline.isPending || stageStatus(phase2, 'P2-01') !== 'PASSED'}
              className="flex h-8 items-center gap-1.5 rounded-md bg-amber-500 px-3 text-xs font-semibold text-white hover:bg-amber-600 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Play size={13} /> Resume Pipeline
            </button>
          </div>
        }
      />

      <section className="border-b border-blue-900 bg-[#0B2355] px-6 py-5 text-white">
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <div className="mb-2 flex items-center gap-2">
              <span className="rounded border border-amber-400/60 px-2 py-0.5 font-mono text-xxs uppercase tracking-wider text-amber-300">
                ACTIVE PROJECT
              </span>
              <span className="rounded bg-white/10 px-2 py-0.5 font-mono text-xxs text-blue-100">Rev R2</span>
            </div>
            <h1 className="text-2xl font-bold leading-tight">{project?.name}</h1>
            <div className="mt-2 flex flex-wrap items-center gap-3 text-xxs text-blue-100">
              <span>{project?.project_type || 'PEB Structure'}</span>
              <span>{project?.location || 'Location not set'}</span>
              <span>Created {fmtDateTime(project?.created_at)}</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => qc.invalidateQueries()}
              className="flex h-8 items-center gap-1.5 rounded-md bg-white px-3 text-xs font-semibold text-slate-900 hover:bg-blue-50"
            >
              <RefreshCw size={13} /> Refresh
            </button>
          </div>
        </div>
        <PhaseRibbon phase2={phase2} phase3={phase3} />
      </section>

      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        <CriticalSignalsPanel
          failedStages={failedStages}
          blockedStages={blockedStages}
          awaitingInputStages={awaitingInputStages}
        />
        <ExecutionLogPanel rows={executionLogs} />

        <section className="rounded-md border border-slate-300 bg-white">
          <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
            <div className="flex items-center gap-2">
              <UploadCloud size={14} className="text-amber-500" />
              <h2 className="text-sm font-bold text-slate-900">Source File Intake</h2>
              <span className="rounded-full border border-blue-200 bg-blue-50 px-2 py-0.5 text-xxs font-semibold text-blue-700">
                P2-01
              </span>
            </div>
            <StatusBadge status={stageStatus(phase2, 'P2-01')} />
          </div>
          <div className="p-4">
            <FileUploadPanel
              projectId={projectId}
              onUpload={(formData, onProgress) => uploadAndIngest.mutateAsync({ formData, onProgress })}
              onClearAll={() => resetIntake.mutate()}
              onDelete={(id) => deleteFile.mutate(id)}
              uploading={uploadAndIngest.isPending}
            />
          </div>

        </section>

        <section className="grid grid-cols-12 gap-4">
          <div className="col-span-4 grid grid-cols-2 gap-3">
            <MetricCard icon={Activity} label="Active Agents" value={activeAgents} detail="Phase 2 tracker" tone="blue" />
            <MetricCard icon={FileCheck2} label="Files Parsed" value={`${parsedFiles}/${files.length}`} detail="Registered inventory" tone="green" />
            <MetricCard icon={AlertTriangle} label="Open Warnings" value={warnings} detail="Blocking and review items" tone="amber" />
            <MetricCard icon={GitBranch} label="Phase 2" value={`${phaseProgress(phase2)}%`} detail="AB/GA layer" tone="slate" />
          </div>
          <div className="col-span-8 flex flex-col gap-4">
            {phase2.some((s) => ['AWAITING_INPUT', 'BLOCKED'].includes(s.status)) && (
              <FieldReviewPanel 
                projectId={projectId} 
                stageCode={phase2.find((s) => ['AWAITING_INPUT', 'BLOCKED'].includes(s.status))?.stage_code} 
              />
            )}
            <LiveLogPanel />
          </div>
        </section>


        <section className="grid grid-cols-12 gap-4 items-start">
          <div className="col-span-8 flex flex-col rounded-md border border-slate-300 bg-white">
            <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
              <div className="flex items-center gap-2">
                <Files size={14} className="text-blue-600" />
                <h2 className="text-sm font-bold text-slate-900">File Inventory</h2>
              </div>
              <span className="font-mono text-xxs text-slate-500">{files.length} files</span>
            </div>
            <FileInventory files={files} loading={loadingFiles} onDelete={(id) => deleteFile.mutate(id)} />
          </div>
          <div className="col-span-4 space-y-4">
            <CandidatePanel candidates={candidates} equalCandidateGate={equalCandidateGate} />
            <DownloadPanel projectId={projectId} stages={phase2} />
          </div>
        </section>

        <section className="rounded-md border border-slate-300 bg-white">
          <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
            <div>
              <div className="flex items-center gap-2">
                <Database size={14} className="text-amber-500" />
                <h2 className="text-sm font-bold text-slate-900">Phase 2 - Design Ingestion and AB/GA Layer</h2>
              </div>
              <p className="mt-0.5 text-xxs text-slate-500">Sequential gated execution</p>
            </div>
            <span className="font-mono text-xxs text-slate-500">Stage progress {phase2.filter((stage) => isDone(stage.status)).length}/5</span>
          </div>
          <AgentGrid stages={phase2} projectId={projectId} onRun={(code) => rerunStage.mutate(code)} running={rerunStage.isPending || runPipeline.isPending || loadingStages} onViewOutputs={setSelectedAgentCode} checkpoints={latestCheckpointByStage} />
        </section>

        <section className="rounded-md border border-slate-300 bg-white">
          <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
            <div className="flex items-center gap-2">
              <ShieldCheck size={14} className="text-emerald-600" />
              <h2 className="text-sm font-bold text-slate-900">Phase 3 - Detailing and Release Layer</h2>
            </div>
            {phase3Locked ? (
              <span className="flex items-center gap-1.5 rounded-full border border-slate-300 bg-slate-100 px-2 py-0.5 text-xxs font-semibold text-slate-600">
                <Lock size={11} /> Locked by P2 gate
              </span>
            ) : (
              <StatusBadge status={phase3.some((s) => s.status === 'FAILED') ? 'FAILED' : phase3.every((s) => isDone(s.status)) ? 'PASSED' : 'PENDING'} />
            )}
          </div>
          <AgentGrid stages={phase3} projectId={projectId} locked={phase3Locked} onViewOutputs={setSelectedAgentCode} checkpoints={latestCheckpointByStage} />
        </section>
      </div>

      {showIngestionModal && (
        <IngestionSummaryModal
          result={ingestionResult}
          onClose={() => setShowIngestionModal(false)}
        />
      )}
      {selectedAgentCode && (
        <AgentOutputsModal
          projectId={projectId}
          stageCode={selectedAgentCode}
          stageName={[...PHASE2_STAGES, ...PHASE3_STAGES].find(s => s.code === selectedAgentCode)?.name || selectedAgentCode}
          onClose={() => setSelectedAgentCode(null)}
        />
      )}
    </div>
  );
}

function ExecutionLogPanel({ rows }) {
  const downloadJson = React.useCallback(() => {
    const blob = new Blob([JSON.stringify(rows, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `agent_execution_logs_${new Date().toISOString().replace(/[:.]/g, '-')}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [rows]);

  const downloadCsv = React.useCallback(() => {
    const header = [
      'id', 'project_id', 'stage_code', 'trigger_type', 'status',
      'started_at', 'completed_at', 'error_message', 'root_cause',
    ];
    const esc = (v) => {
      const s = v == null ? '' : String(v);
      return `"${s.replace(/"/g, '""')}"`;
    };
    const lines = [
      header.join(','),
      ...rows.map((r) => ([
        r.id,
        r.project_id,
        r.stage_code,
        r.trigger_type,
        r.status,
        r.started_at,
        r.completed_at,
        r.error_message || '',
        r.root_cause || '',
      ]).map(esc).join(',')),
    ];
    const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `agent_execution_logs_${new Date().toISOString().replace(/[:.]/g, '-')}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }, [rows]);

  return (
    <section className="rounded-md border border-slate-300 bg-white">
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-2.5">
        <h2 className="text-sm font-bold text-slate-900">Agent Execution Log</h2>
        <div className="flex items-center gap-2">
          <button
            onClick={downloadJson}
            className="rounded border border-slate-300 bg-white px-2 py-1 text-xxs font-semibold text-slate-700 hover:border-blue-300 hover:text-blue-700"
          >
            Download JSON
          </button>
          <button
            onClick={downloadCsv}
            className="rounded border border-slate-300 bg-white px-2 py-1 text-xxs font-semibold text-slate-700 hover:border-blue-300 hover:text-blue-700"
          >
            Download CSV
          </button>
          <span className="font-mono text-xxs text-slate-500">{rows.length} attempts</span>
        </div>
      </div>
      <div className="max-h-72 overflow-auto">
        <table className="min-w-full text-xs">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="px-3 py-2 text-left">Time</th>
              <th className="px-3 py-2 text-left">Stage</th>
              <th className="px-3 py-2 text-left">Trigger</th>
              <th className="px-3 py-2 text-left">Status</th>
              <th className="px-3 py-2 text-left">Failure</th>
              <th className="px-3 py-2 text-left">Trace</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-t border-slate-100 align-top">
                <td className="px-3 py-2 font-mono text-[10px] text-slate-500">{fmtDateTime(r.started_at)}</td>
                <td className="px-3 py-2 font-mono text-[10px] text-slate-700">{r.stage_code}</td>
                <td className="px-3 py-2 text-slate-600">{r.trigger_type}</td>
                <td className="px-3 py-2">
                  <span className={clsx(
                    'rounded px-1.5 py-0.5 font-mono text-[10px]',
                    r.status === 'FAILED' ? 'bg-red-100 text-red-700' :
                    r.status === 'BLOCKED' ? 'bg-amber-100 text-amber-700' :
                    r.status?.includes('PASS') ? 'bg-emerald-100 text-emerald-700' :
                    'bg-slate-100 text-slate-600'
                  )}>
                    {r.status}
                  </span>
                </td>
                <td className="px-3 py-2 text-[10px] text-slate-600">
                  <p className="line-clamp-2">{r.error_message || '—'}</p>
                  {r.root_cause && <p className="line-clamp-2 text-red-700">{r.root_cause}</p>}
                </td>
                <td className="px-3 py-2 text-[10px] text-slate-600">
                  <details>
                    <summary className="cursor-pointer text-blue-700">View</summary>
                    <pre className="mt-1 max-w-md overflow-auto rounded bg-slate-50 p-2 text-[9px]">
{`Input: ${r.input_payload || '{}'}\n\nOutput: ${r.output_payload || '{}'}`}
                    </pre>
                  </details>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={6} className="px-3 py-6 text-center text-slate-500">No execution attempts logged yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function PhaseRibbon({ phase2, phase3 }) {
  const phases = [
    { label: 'Phase 1 - Master DB', progress: 100, status: 'Done' },
    { label: 'Phase 2 - AB / GA', progress: phaseProgress(phase2), status: phase2.some((s) => s.status === 'FAILED') ? 'Failed' : phase2.some((s) => s.status === 'BLOCKED' || s.status === 'AWAITING_INPUT') ? 'Blocked' : phase2.some((stage) => isRunning(stage.status)) ? 'Running' : 'Active' },
    { label: 'Phase 3 - Detailing', progress: phaseProgress(phase3), status: phase3.some((s) => s.status === 'FAILED') ? 'Failed' : phase3.every((stage) => stage.ui_locked) ? 'Queued' : 'Active' },
  ];
  return (
    <div className="grid grid-cols-3 gap-3">
      {phases.map((phase) => (
        <div key={phase.label} className="rounded-md border border-white/15 bg-white/10 p-3">
          <div className="mb-2 flex items-center justify-between text-xxs">
            <span className="font-semibold text-blue-50">{phase.label}</span>
            <span className="font-mono text-amber-300">{phase.progress}% - {phase.status}</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-blue-950/80">
            <div className="h-full rounded-full bg-amber-400 transition-all duration-500" style={{ width: `${phase.progress}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

function MetricCard({ icon: Icon, label, value, detail, tone }) {
  const colors = {
    blue: 'text-blue-600',
    green: 'text-emerald-600',
    amber: 'text-amber-600',
    slate: 'text-slate-700',
  };
  return (
    <div className="rounded-md border border-slate-300 bg-white p-3">
      <div className="mb-3 flex items-center justify-between">
        <Icon size={15} className={colors[tone]} />
        <span className="text-xxs uppercase tracking-wide text-slate-500">{label}</span>
      </div>
      <div className="text-2xl font-bold text-slate-950">{value}</div>
      <div className="mt-1 text-xxs text-slate-500">{detail}</div>
    </div>
  );
}

function FileInventory({ files, loading, onDelete }) {
  if (loading) {
    return <div className="flex h-36 items-center justify-center"><LoadingSpinner size="sm" /></div>;
  }
  if (!files.length) {
    return <div className="p-8 text-center text-xs text-slate-500">No files registered.</div>;
  }
  return (
    <div className="overflow-y-auto" style={{ minHeight: '9rem', maxHeight: '480px' }}>
      <table className="w-full text-left text-xs">
        <thead className="sticky top-0 bg-slate-50 text-xxs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-4 py-2">File</th>
            <th className="px-3 py-2">Type</th>
            <th className="px-3 py-2">Role</th>
            <th className="px-3 py-2">Source</th>
            <th className="px-3 py-2">Status</th>
            <th className="px-3 py-2 text-right">Confidence</th>
            <th className="px-3 py-2"></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-200">
          {files.map((file) => (
            <tr key={file.id} className="hover:bg-slate-50">
              <td className="max-w-xs truncate px-4 py-2 font-medium text-slate-900">{file.original_filename}</td>
              <td className="px-3 py-2 font-mono text-xxs text-slate-600">{file.file_type}</td>
              <td className="px-3 py-2 text-slate-600">{file.likely_role}</td>
              <td className="px-3 py-2 text-slate-600">{file.source_application}</td>
              <td className="px-3 py-2"><StatusBadge status={file.processing_status} /></td>
              <td className="px-3 py-2 text-right font-mono text-slate-700">{file.classification_confidence}%</td>
              <td className="px-3 py-2 text-right">
                <button 
                  onClick={() => onDelete?.(file.id)}
                  className="rounded p-1 text-slate-400 hover:bg-red-50 hover:text-red-600 transition-colors"
                  title="Delete File"
                >
                  <Trash2 size={14} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CandidatePanel({ candidates, equalCandidateGate }) {
  const autoGoverning = candidates.length === 1;
  return (
    <div className="rounded-md border border-slate-300 bg-white">
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
        <div className="flex items-center gap-2">
          <FileSearch size={14} className="text-blue-600" />
          <h2 className="text-sm font-bold text-slate-900">Governing Candidates</h2>
        </div>
        {equalCandidateGate
          ? <StatusBadge status="AWAITING_INPUT" />
          : <StatusBadge status={candidates.length ? 'PASSED' : 'PENDING'} />}
      </div>
      {autoGoverning && (
        <div className="flex items-center gap-2 border-b border-amber-100 bg-amber-50 px-3 py-1.5">
          <Star size={11} className="text-amber-500 flex-shrink-0" />
          <p className="text-xxs font-semibold text-amber-800">Single file — auto-selected as governing source</p>
        </div>
      )}
      <div className="space-y-2 p-3">
        {candidates.length === 0 ? (
          <p className="text-xs text-slate-500">No governing design candidates detected yet.</p>
        ) : (
          candidates.slice(0, 5).map((file, index) => (
            <div key={file.id} className={clsx('rounded border p-2', autoGoverning ? 'border-amber-200 bg-amber-50/50' : 'border-slate-200 bg-slate-50')}>
              <div className="flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate text-xs font-semibold text-slate-900">{file.original_filename}</p>
                  <p className="font-mono text-xxs text-slate-500">{file.file_type} / {file.source_application}</p>
                </div>
                {autoGoverning ? (
                  <Star size={13} className="flex-shrink-0 text-amber-500" title="Auto-governing" />
                ) : (
                  <span className="rounded bg-white px-2 py-1 font-mono text-xxs font-bold text-slate-700">
                    #{index + 1}
                  </span>
                )}
              </div>
              <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-200">
                <div className="h-full rounded-full bg-blue-600" style={{ width: `${file.classification_confidence}%` }} />
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function AgentOutputsModal({ projectId, stageCode, stageName, onClose }) {
  const [preview, setPreview] = React.useState(null);
  const normalizedCode = stageCode.toLowerCase().replace(/-/g, '_');

  const { data, isLoading } = useQuery({
    queryKey: ['agentFiles', projectId, normalizedCode],
    queryFn: () => outputsApi.getAgentFiles(projectId, normalizedCode),
    enabled: !!projectId && !!stageCode,
  });

  const files = data?.files || [];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-6 backdrop-blur-sm">
      <div className="flex w-full max-w-2xl flex-col rounded-lg bg-white shadow-2xl ring-1 ring-slate-200">
        <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
          <div className="flex items-center gap-2">
            <Files size={16} className="text-blue-600" />
            <h3 className="text-sm font-bold text-slate-900">{stageName} — Output Files</h3>
            <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xxs text-slate-500">{stageCode}</span>
          </div>
          <button onClick={onClose} className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-900">
            <X size={18} />
          </button>
        </div>

        <div className="min-h-32 max-h-[28rem] overflow-y-auto p-4">
          {isLoading ? (
            <div className="flex items-center justify-center py-10">
              <LoadingSpinner size="sm" />
            </div>
          ) : files.length === 0 ? (
            <div className="py-10 text-center">
              <Files size={32} className="mx-auto mb-3 text-slate-300" />
              <p className="text-sm text-slate-500">No output files generated yet for this stage.</p>
              <p className="mt-1 text-xxs text-slate-400">Run the agent to generate outputs.</p>
            </div>
          ) : (
            <div className="space-y-1.5">
              {files.map((file) => {
                const fileUrl = outputsApi.downloadUrl(projectId, `${normalizedCode}/${file.relative_path}`);
                return (
                  <div
                    key={file.relative_path}
                    className="group flex items-center gap-3 rounded border border-slate-200 px-3 py-2 hover:border-blue-300 hover:bg-blue-50"
                  >
                    <FileText size={14} className="flex-shrink-0 text-slate-400" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-xs font-semibold text-slate-900">{file.name}</p>
                      <p className="font-mono text-xxs text-slate-400">
                        {file.relative_path} · {(file.size_bytes / 1024).toFixed(1)} KB
                      </p>
                    </div>
                    <div className="flex flex-shrink-0 items-center gap-1.5 opacity-0 transition-opacity group-hover:opacity-100">
                      <button
                        onClick={() => setPreview({ ...file, url: fileUrl })}
                        className="rounded border border-blue-200 bg-white px-2 py-0.5 text-[10px] font-semibold text-blue-700 hover:bg-blue-600 hover:text-white"
                      >
                        Preview
                      </button>
                      <a
                        href={fileUrl}
                        download
                        className="flex h-6 w-6 items-center justify-center rounded border border-slate-200 bg-white text-slate-500 hover:border-blue-300 hover:text-blue-600"
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

        <div className="flex items-center justify-between border-t border-slate-200 bg-slate-50 px-4 py-2.5">
          <span className="text-xxs text-slate-500">{files.length} file{files.length !== 1 ? 's' : ''}</span>
          <button
            onClick={onClose}
            className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-100"
          >
            Close
          </button>
        </div>
      </div>

      {preview && (
        <OutputPreviewModal
          isOpen
          onClose={() => setPreview(null)}
          file={preview}
          downloadUrl={preview.url}
        />
      )}
    </div>
  );
}

function CriticalSignalsPanel({ failedStages, blockedStages, awaitingInputStages }) {
  if (!failedStages.length && !blockedStages.length && !awaitingInputStages.length) {
    return null;
  }

  return (
    <section className="rounded-md border border-red-300 bg-red-50">
      <div className="flex items-center gap-2 border-b border-red-200 px-4 py-2.5">
        <AlertOctagon size={14} className="text-red-700" />
        <h2 className="text-sm font-bold text-red-900">Critical Workflow Signals</h2>
      </div>
      <div className="grid grid-cols-3 gap-3 p-3 text-xs">
        <SignalList
          title={`Failures (${failedStages.length})`}
          tone="red"
          items={failedStages.map((s) => `${s.stage_code}: ${summarizeStageReason(s)}`)}
        />
        <SignalList
          title={`Blocked (${blockedStages.length})`}
          tone="amber"
          items={blockedStages.map((s) => `${s.stage_code}: ${s.ui_locked ? 'Locked by upstream gate' : summarizeStageReason(s)}`)}
        />
        <SignalList
          title={`Awaiting Input (${awaitingInputStages.length})`}
          tone="blue"
          items={awaitingInputStages.map((s) => `${s.stage_code}: operator input required`)}
        />
      </div>
    </section>
  );
}

function SignalList({ title, tone, items }) {
  const toneClasses = {
    red: 'border-red-200 bg-white text-red-900',
    amber: 'border-amber-200 bg-white text-amber-900',
    blue: 'border-blue-200 bg-white text-blue-900',
  };
  return (
    <div className={clsx('rounded border p-2', toneClasses[tone])}>
      <p className="mb-1 font-semibold">{title}</p>
      {items.length ? (
        <div className="space-y-1">
          {items.slice(0, 4).map((item) => (
            <p key={item} className="font-mono text-[10px]">{item}</p>
          ))}
        </div>
      ) : (
        <p className="text-[10px] opacity-70">None</p>
      )}
    </div>
  );
}

function AgentGrid({ stages, projectId, onRun, running, locked = false, onViewOutputs, checkpoints }) {
  return (
    <div className="grid grid-cols-5 gap-3 p-4">
      {stages.map((stage, index) => (
        <AgentCard
          key={stage.stage_code}
          stage={stage}
          projectId={projectId}
          index={index}
          onRun={onRun}
          running={running}
          locked={locked}
          onViewOutputs={onViewOutputs}
          checkpoint={checkpoints?.get(stage.stage_code)}
        />
      ))}
    </div>
  );
}

function AgentCard({ stage, projectId, index, onRun, running, locked, onViewOutputs, checkpoint }) {
  const meta = STATUS_META[stage.status] || STATUS_META.PENDING;
  const canRun = onRun && !locked && !isRunning(stage.status);
  const errorSummary = summarizeStageReason(stage);
  const errorFull = fullStageReason(stage);
  const fixHints = blockerFixHints(stage);
  // When no checkpoint record exists yet, infer gate state from the stage status
  // so the validator doesn't show PENDING for a stage that already passed.
  const checkpointState = checkpoint?.gate_status
    || (isDone(stage.status) ? 'PASS' : stage.status === 'FAILED' ? 'FAIL' : 'PENDING');
  const validatorStatus = checkpointState === 'PASS' ? 'PASSED' : checkpointState === 'FAIL' ? 'FAILED' : 'PENDING';

  // Pending validator context — shown when validator hasn't cleared
  const pendingReason = validatorStatus === 'PENDING'
    ? pendingValidatorReason(stage.stage_code, checkpoint)
    : null;

  // Field metrics for completed stages
  const metrics = isDone(stage.status) ? stageFieldMetrics(stage) : null;

  // Structured warnings for PASS_WITH_WARNINGS
  const warnings = stage.status === 'PASS_WITH_WARNINGS'
    ? (stage.result?.warnings || [])
    : [];

  // Failed field IDs for P2-02 with failures
  const failedFieldIds = stage.stage_code === 'P2-02' && stage.result?.failed_field_ids?.length
    ? stage.result.failed_field_ids
    : [];

  return (
    <div className={clsx('relative flex flex-col rounded-md border bg-white p-3 shadow-sm transition-all', meta.border)}>
      {/* Header */}
      <div className="mb-3 flex items-center justify-between">
        <span className={clsx('flex h-7 w-7 items-center justify-center rounded font-mono text-xxs font-bold', meta.bg, meta.color)}>
          {String(index + 1).padStart(2, '0')}
        </span>
        <div className="flex items-center gap-1.5">
          <StatusBadge status={stage.status} />
        </div>
      </div>

      <div className="flex-1 space-y-2">
        <div>
          <p className="font-mono text-xxs font-semibold text-slate-500">{stage.stage_code}</p>
          <h3 className="mt-1 text-sm font-bold text-slate-900">{stage.name}</h3>
          <p className="mt-1 text-xxs leading-4 text-slate-500 line-clamp-2">{stage.description}</p>
        </div>

        {/* ── FAILED / BLOCKED error panel ── */}
        {(stage.status === 'FAILED' || stage.status === 'BLOCKED' || stage.ui_locked) && (
          <div className="rounded border border-red-200 bg-red-50 p-2 text-[10px] text-red-800 space-y-1">
            <div className="flex items-center gap-1 font-bold">
              <AlertTriangle size={10} className="flex-shrink-0" />
              <span>
                {stage.status === 'BLOCKED' ? 'Stage Blocked' : stage.ui_locked ? 'Locked by Upstream Gate' : 'Stage Failed'}
              </span>
            </div>
            {errorSummary && <p className="font-medium">{errorSummary}</p>}
            <details className="mt-1">
              <summary className="cursor-pointer font-semibold text-red-700">Full diagnostic</summary>
              <pre className="mt-1 whitespace-pre-wrap font-mono text-[9px] text-red-700 leading-3">{errorFull}</pre>
            </details>
            {fixHints.length > 0 && (
              <div className="mt-1 border-t border-red-200 pt-1">
                <p className="font-bold text-red-900 mb-0.5">Recommended fixes</p>
                {fixHints.map((hint) => (
                  <p key={hint} className="font-mono text-[9px]">• {hint}</p>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ── PASS_WITH_WARNINGS warning panel ── */}
        {warnings.length > 0 && (
          <div className="rounded border border-amber-200 bg-amber-50 p-2 text-[10px] text-amber-900 space-y-1.5">
            <p className="font-bold flex items-center gap-1">
              <AlertTriangle size={10} className="flex-shrink-0 text-amber-600" />
              {warnings.length} Warning{warnings.length > 1 ? 's' : ''} Detected
            </p>
            {warnings.map((w, i) => (
              <details key={i} className="rounded border border-amber-200 bg-white/60 p-1.5">
                <summary className="cursor-pointer font-semibold text-amber-800 text-[9px]">
                  [{w.severity}] {w.title}
                </summary>
                <div className="mt-1 space-y-0.5 text-[9px] font-mono">
                  <p><span className="font-bold">Issue:</span> {w.issue}</p>
                  <p><span className="font-bold">Root Cause:</span> {w.root_cause}</p>
                  <p><span className="font-bold">Parser:</span> {w.parser}</p>
                  <p><span className="font-bold">Fix:</span> {w.recommended_fix}</p>
                  <p className={clsx('font-bold', w.can_continue ? 'text-green-700' : 'text-red-700')}>
                    Pipeline can continue: {w.can_continue ? 'Yes' : 'No'}
                  </p>
                </div>
              </details>
            ))}
          </div>
        )}

        {/* ── Field extraction metrics (completed stages) ── */}
        {metrics && (
          <div className="rounded border border-emerald-200 bg-emerald-50 p-2 text-[10px]">
            <p className="mb-1.5 font-bold text-emerald-800 flex items-center gap-1">
              <CheckCircle2 size={10} /> Field Extraction Summary
            </p>
            <div className="grid grid-cols-2 gap-x-3 gap-y-0.5">
              {metrics.map(({ label, value, tone }) => (
                <div key={label} className="flex items-center justify-between">
                  <span className="text-slate-600">{label}</span>
                  <span className={clsx(
                    'font-mono font-bold',
                    tone === 'red' && value > 0 ? 'text-red-700'
                    : tone === 'amber' && value > 0 ? 'text-amber-700'
                    : tone === 'blue' ? 'text-blue-700'
                    : 'text-emerald-700'
                  )}>{value}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── P2-02 failed field IDs ── */}
        {failedFieldIds.length > 0 && (
          <details className="rounded border border-red-200 bg-red-50/60 p-2 text-[10px]">
            <summary className="cursor-pointer font-bold text-red-800">
              {failedFieldIds.length} Unresolved Field{failedFieldIds.length > 1 ? 's' : ''} — click to expand
            </summary>
            <div className="mt-1.5 flex flex-wrap gap-1">
              {failedFieldIds.map((fc) => (
                <span key={fc} className="rounded bg-red-100 px-1 py-0.5 font-mono text-[9px] text-red-700 border border-red-200">
                  {fc}
                </span>
              ))}
            </div>
            <p className="mt-1.5 text-[9px] text-red-700 font-mono">
              Download missing_field_report.json from Outputs for root-cause details per field.
            </p>
          </details>
        )}
      </div>

      {/* ── Validator block ── */}
      <div className="mt-3 rounded border border-slate-200 bg-slate-50 p-2 text-xxs text-slate-600">
        <div className="mb-1 flex items-center justify-between gap-1.5 font-semibold text-slate-700">
          <div className="flex items-center gap-1.5">
            <ShieldCheck size={11} className="text-blue-600" /> Validator {index + 1}
          </div>
          <StatusBadge size="sm" status={validatorStatus} />
        </div>
        <p className="italic text-[10px] text-slate-500 line-clamp-1">{VALIDATORS[stage.stage_code]}</p>
        <p className="mt-0.5 font-mono text-[9px] text-slate-400">
          Gate: {checkpointState}{checkpoint?.label ? ` · ${checkpoint.label}` : checkpoint ? '' : ' (inferred)'}
        </p>

        {/* Pending validator explanation */}
        {pendingReason && (
          <details className="mt-1.5 rounded border border-blue-200 bg-blue-50/60 p-1.5 text-[9px]">
            <summary className="cursor-pointer font-bold text-blue-800">Why is this validator pending?</summary>
            <div className="mt-1 space-y-0.5 font-mono text-blue-900">
              <p><span className="font-bold">Validator:</span> {pendingReason.validator}</p>
              <p><span className="font-bold">Reason:</span> {pendingReason.reason}</p>
              <p><span className="font-bold">Dependency:</span> {pendingReason.blocking_dependency}</p>
              <p><span className="font-bold">Fix:</span> {pendingReason.recommended_fix}</p>
            </div>
          </details>
        )}

        {/* FAIL validator explanation from gate_data */}
        {validatorStatus === 'FAILED' && checkpoint?.gate_data && (
          <details className="mt-1.5 rounded border border-red-200 bg-red-50/60 p-1.5 text-[9px]">
            <summary className="cursor-pointer font-bold text-red-800">Validator failure detail</summary>
            <pre className="mt-1 whitespace-pre-wrap font-mono text-[8px] text-red-800 leading-3">
              {JSON.stringify(checkpoint.gate_data, null, 2)}
            </pre>
          </details>
        )}
      </div>

      {/* ── Footer actions ── */}
      <div className="mt-3 flex items-center justify-between border-t border-slate-200 pt-3">
        <button
          onClick={() => onViewOutputs?.(stage.stage_code)}
          className="flex h-7 items-center gap-1.5 rounded border border-blue-200 bg-blue-50 px-2 text-[10px] font-bold text-blue-700 hover:bg-blue-600 hover:text-white transition-colors"
          title="View output files"
        >
          <Files size={10} /> Outputs
        </button>
        {canRun ? (
          <button
            onClick={() => onRun(stage.stage_code)}
            disabled={running}
            className="flex h-7 items-center gap-1 rounded bg-slate-900 px-2 text-xxs font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
          >
            <Play size={11} /> Run
          </button>
        ) : locked ? (
          <Lock size={13} className="text-slate-400" />
        ) : isDone(stage.status) ? (
          <CheckCircle2 size={15} className="text-emerald-600" />
        ) : isRunning(stage.status) ? (
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
        ) : null}
      </div>
    </div>
  );
}
