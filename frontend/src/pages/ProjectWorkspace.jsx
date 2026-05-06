import React from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Activity,
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

const isRunning = (status) => status === 'RUNNING' || status === 'IN_PROGRESS';
const isDone = (status) => status === 'PASSED' || status === 'PASS_WITH_WARNINGS';

function mergeStages(defs, rows, locked = false) {
  const byCode = new Map((rows || []).map((stage) => [stage.stage_code, stage]));
  return defs.map((info) => ({
    ...info,
    stage_code: info.code,
    status: locked ? 'BLOCKED' : byCode.get(info.code)?.status || 'PENDING',
    started_at: byCode.get(info.code)?.started_at || null,
    completed_at: byCode.get(info.code)?.completed_at || null,
    error_message: byCode.get(info.code)?.error_message || null,
    result: byCode.get(info.code)?.result || {},
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

  const uploadAndIngest = useMutation({
    mutationFn: async (formData) => {
      // Pass a dummy onProgress for now or handle it in FileUploadPanel via projectsApi update
      const uploaded = await projectsApi.uploadFiles(projectId, formData);
      const ingestion = await stagesApi.runStage(projectId, 'P2-01');
      return { uploaded, ingestion };
    },
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['projectFiles', projectId] });
      qc.invalidateQueries({ queryKey: ['stages', projectId] });
      qc.invalidateQueries({ queryKey: ['pipeline', projectId] });
      setIngestionResult(data.ingestion);
      setShowIngestionModal(true);
      add({ type: 'success', text: 'Files uploaded and P2-01 ingestion completed' });
    },
    onError: (error) => add({ type: 'error', text: error.message }),
  });

  const resetIntake = useMutation({
    mutationFn: () => stagesApi.resetIntake(projectId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['projectFiles', projectId] });
      qc.invalidateQueries({ queryKey: ['stages', projectId] });
      qc.invalidateQueries({ queryKey: ['pipeline', projectId] });
      add({ type: 'success', text: 'Intake reset and files cleared' });
    },
    onError: (error) => add({ type: 'error', text: error.message }),
  });

  const runPipeline = useMutation({
    mutationFn: (fromStage) => stagesApi.runPipeline(projectId, fromStage),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['stages', projectId] });
      qc.invalidateQueries({ queryKey: ['pipeline', projectId] });
      add({ type: 'success', text: 'Phase 2 pipeline run completed' });
    },
    onError: (error) => add({ type: 'error', text: error.message }),
  });

  const deleteFile = useMutation({
    mutationFn: (fileId) => projectsApi.deleteFile(projectId, fileId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['projectFiles', projectId] });
      qc.invalidateQueries({ queryKey: ['stages', projectId] });
      qc.invalidateQueries({ queryKey: ['pipeline', projectId] });
      add({ type: 'success', text: 'File deleted and stages reset' });
    },
    onError: (error) => add({ type: 'error', text: error.message }),
  });

  const rerunStage = useMutation({
    mutationFn: (stageCode) => stagesApi.runStage(projectId, stageCode),
    onSuccess: (data, stageCode) => {
      qc.invalidateQueries({ queryKey: ['stages', projectId] });
      qc.invalidateQueries({ queryKey: ['projectFiles', projectId] });
      if (stageCode === 'P2-01') {
        setIngestionResult(data);
        setShowIngestionModal(true);
      }
      add({ type: 'success', text: `${stageCode} run completed` });
    },
    onError: (error) => add({ type: 'error', text: error.message }),
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
              onUpload={(formData, onProgress) => projectsApi.uploadFiles(projectId, formData, { onUploadProgress: onProgress })}
              onClearAll={() => resetIntake.mutate()}
              onDelete={(id) => deleteFile.mutate(id)}
              uploading={uploadAndIngest.isPending || resetIntake.isPending}
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
            {phase2.some(s => s.status === 'AWAITING_INPUT') && (
              <FieldReviewPanel 
                projectId={projectId} 
                stageCode={phase2.find(s => s.status === 'AWAITING_INPUT')?.stage_code} 
              />
            )}
            <LiveLogPanel />
          </div>
        </section>


        <section className="grid grid-cols-12 gap-4">
          <div className="col-span-8 rounded-md border border-slate-300 bg-white">
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
          <AgentGrid stages={phase2} projectId={projectId} onRun={(code) => rerunStage.mutate(code)} running={rerunStage.isPending || runPipeline.isPending || loadingStages} onViewOutputs={setSelectedAgentCode} />
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
              <StatusBadge status="PASSED" />
            )}
          </div>
          <AgentGrid stages={phase3} projectId={projectId} locked={phase3Locked} onViewOutputs={setSelectedAgentCode} />
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

function PhaseRibbon({ phase2, phase3 }) {
  const phases = [
    { label: 'Phase 1 - Master DB', progress: 100, status: 'Done' },
    { label: 'Phase 2 - AB / GA', progress: phaseProgress(phase2), status: phase2.some((stage) => isRunning(stage.status)) ? 'Running' : 'Active' },
    { label: 'Phase 3 - Detailing', progress: phaseProgress(phase3), status: phase3.every((stage) => stage.status === 'BLOCKED') ? 'Queued' : 'Active' },
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
    <div className="max-h-80 overflow-auto">
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

function AgentGrid({ stages, projectId, onRun, running, locked = false, onViewOutputs }) {
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
        />
      ))}
    </div>
  );
}

function AgentCard({ stage, projectId, index, onRun, running, locked, onViewOutputs }) {
  const meta = STATUS_META[stage.status] || STATUS_META.PENDING;
  const canRun = onRun && !locked && !isRunning(stage.status);
  const errorSummary = stage.error_message 
    ? stage.error_message.split(':').pop().split('\n')[0].trim()
    : null;

  return (
    <div className={clsx('relative flex flex-col rounded-md border bg-white p-3 shadow-sm transition-all', meta.border)}>
      <div className="mb-3 flex items-center justify-between">
        <span className={clsx('flex h-7 w-7 items-center justify-center rounded font-mono text-xxs font-bold', meta.bg, meta.color)}>
          {String(index + 1).padStart(2, '0')}
        </span>
        <div className="flex items-center gap-1.5">
          <StatusBadge status={stage.status} />
        </div>
      </div>
      <div className="min-h-20 flex-1">
        <p className="font-mono text-xxs font-semibold text-slate-500">{stage.stage_code}</p>
        <h3 className="mt-1 text-sm font-bold text-slate-900">{stage.name}</h3>
        <p className="mt-2 text-xxs leading-4 text-slate-500 line-clamp-2">{stage.description}</p>
        
        {stage.status === 'FAILED' && errorSummary && (
          <div className="mt-2 flex items-start gap-1.5 rounded border border-red-100 bg-red-50 p-1.5 text-[10px] text-red-700">
            <AlertTriangle size={10} className="mt-0.5 flex-shrink-0" />
            <p className="font-medium leading-tight line-clamp-2">{errorSummary}</p>
          </div>
        )}
      </div>

      <div className="mt-3 rounded border border-slate-200 bg-slate-50 p-2 text-xxs text-slate-600">
        <div className="mb-1 flex items-center gap-1.5 font-semibold text-slate-700">
          <ShieldCheck size={11} className="text-blue-600" /> Validator {index + 1}
        </div>
        <p className="line-clamp-1 italic">{VALIDATORS[stage.stage_code]}</p>
      </div>
      
      <div className="mt-3 flex items-center justify-between border-t border-slate-200 pt-3">
        <div className="flex items-center gap-2">
          <button
            onClick={() => onViewOutputs?.(stage.stage_code)}
            className="flex h-7 items-center gap-1.5 rounded border border-blue-200 bg-blue-50 px-2 text-[10px] font-bold text-blue-700 hover:bg-blue-600 hover:text-white transition-colors"
            title="View output files"
          >
            <Files size={10} /> Outputs
          </button>
        </div>
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

