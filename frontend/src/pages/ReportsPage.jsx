import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  BarChart2,
  Calendar,
  CheckCircle,
  Download,
  FileText,
  RefreshCw,
  AlertTriangle,
  TrendingUp,
  XCircle,
  Clock,
  ChevronDown,
  ThumbsUp,
  ThumbsDown,
} from 'lucide-react';
import TopBar from '../components/layout/TopBar';
import LoadingSpinner from '../components/shared/LoadingSpinner';
import { reportsApi } from '../api/reports';
import { projectsApi } from '../api/projects';

const REPORT_TYPES = [
  { key: 'DAILY',   label: 'Daily',   icon: Calendar,   desc: 'End-of-day operational record' },
  { key: 'WEEKLY',  label: 'Weekly',  icon: BarChart2,  desc: '7-day roll-up and trend analysis' },
  { key: 'MONTHLY', label: 'Monthly', icon: TrendingUp, desc: 'Management summary and effectiveness score' },
];

const STATUS_COLORS = {
  PASSED:             'text-green-600 bg-green-50',
  PASS_WITH_WARNINGS: 'text-yellow-600 bg-yellow-50',
  FAILED:             'text-red-600 bg-red-50',
  BLOCKED:            'text-red-700 bg-red-100',
  RUNNING:            'text-blue-600 bg-blue-50',
  PENDING:            'text-slate-500 bg-slate-100',
  IN_PROGRESS:        'text-blue-600 bg-blue-50',
  NO_DATA:            'text-slate-400 bg-slate-50',
  HEALTHY:            'text-green-600 bg-green-50',
  DEGRADED:           'text-red-600 bg-red-50',
  PARTIAL:            'text-yellow-600 bg-yellow-50',
};

function StatusBadge({ status }) {
  const cls = STATUS_COLORS[status] || 'text-slate-600 bg-slate-100';
  return (
    <span className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-semibold ${cls}`}>
      {status}
    </span>
  );
}

function KVTable({ data }) {
  if (!data || Object.keys(data).length === 0) return <p className="text-xs text-slate-400">No data.</p>;
  return (
    <table className="w-full text-xs">
      <tbody>
        {Object.entries(data).map(([k, v]) => (
          <tr key={k} className="border-b border-slate-100 last:border-0">
            <td className="py-1 pr-4 font-medium text-slate-600 w-1/3">{k.replace(/_/g, ' ')}</td>
            <td className="py-1 text-slate-800">
              {typeof v === 'object' ? JSON.stringify(v) : String(v ?? '—')}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function SectionCard({ title, icon: Icon, children }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center gap-2 border-b border-slate-100 pb-2">
        {Icon && <Icon size={14} className="text-blue-600" />}
        <h3 className="text-sm font-semibold text-slate-800">{title}</h3>
      </div>
      {children}
    </div>
  );
}

// ── Daily Report View ─────────────────────────────────────────────────────────
function DailyReportView({ report }) {
  const h    = report.header || {};
  const ex   = report.execution_summary || {};
  const sev  = report.severity_summary || {};
  const ncp  = report.next_day_critical_path || {};
  const mr   = report.manual_review_summary || {};
  const sf   = report.source_fallback_summary || {};
  const def  = report.defect_summary || {};
  const corr = report.corrections_today || [];

  return (
    <div className="space-y-4">
      {/* Header banner */}
      <div className="rounded-lg border border-blue-200 bg-blue-50 p-4">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs text-blue-400 font-semibold tracking-wide uppercase">Daily Report</p>
            <p className="text-lg font-bold text-blue-900">{h.project_name}</p>
            <p className="text-xs text-blue-600">
              {h.date} &nbsp;·&nbsp; Proposal {h.proposal_id} &nbsp;·&nbsp; Build {h.build_version}
            </p>
          </div>
          <StatusBadge status={h.project_status} />
        </div>
      </div>

      {/* Execution Summary */}
      <div className="grid grid-cols-5 gap-3">
        {[
          { label: 'Tasks Today',      val: ex.tasks_run_today,        color: 'text-blue-700' },
          { label: 'Rules Evaluated',  val: ex.rules_evaluated_total,  color: 'text-slate-700' },
          { label: 'Gates Touched',    val: ex.gates_touched_total,    color: 'text-slate-700' },
          { label: 'Re-runs Today',    val: ex.reruns_today,           color: ex.reruns_today > 0 ? 'text-orange-600' : 'text-green-600' },
          { label: 'Corrections',      val: ex.corrections_today,      color: ex.corrections_today > 0 ? 'text-purple-600' : 'text-slate-500' },
        ].map(({ label, val, color }) => (
          <div key={label} className="rounded-lg border border-slate-200 bg-white p-3 text-center shadow-sm">
            <p className={`text-2xl font-bold ${color}`}>{val ?? 0}</p>
            <p className="text-xs text-slate-500 mt-0.5">{label}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-4">
        {/* Lane Summary */}
        <SectionCard title="Lane Summary" icon={BarChart2}>
          <div className="space-y-2">
            {Object.entries(report.lane_summary || {}).map(([lane, info]) => (
              <div key={lane} className="flex items-center justify-between">
                <span className="text-xs text-slate-600">{lane}</span>
                <StatusBadge status={info.overall} />
              </div>
            ))}
          </div>
        </SectionCard>

        {/* Severity Summary */}
        <SectionCard title="Severity Summary" icon={AlertTriangle}>
          <div className="space-y-2">
            {[
              { key: 'CRITICAL',        label: 'Critical',         cls: 'text-red-700 bg-red-50' },
              { key: 'MAJOR',           label: 'Major',            cls: 'text-orange-600 bg-orange-50' },
              { key: 'MINOR',           label: 'Minor',            cls: 'text-yellow-600 bg-yellow-50' },
              { key: 'release_blockers',label: 'Release Blockers', cls: 'text-red-800 bg-red-100 font-bold' },
            ].map(({ key, label, cls }) => (
              <div key={key} className="flex items-center justify-between">
                <span className="text-xs text-slate-600">{label}</span>
                <span className={`rounded px-2 py-0.5 text-xs font-semibold ${cls}`}>
                  {sev[key] ?? 0}
                </span>
              </div>
            ))}
          </div>
        </SectionCard>
      </div>

      {/* Gate Snapshot */}
      {Object.keys(report.gate_snapshot || {}).length > 0 && (
        <SectionCard title="Gate Snapshot" icon={CheckCircle}>
          <div className="space-y-1">
            {Object.entries(report.gate_snapshot).map(([label, info]) => (
              <div key={label} className="flex items-center justify-between text-xs">
                <span className="text-slate-600 truncate max-w-xs">{label}</span>
                <StatusBadge status={info.gate_status} />
              </div>
            ))}
          </div>
        </SectionCard>
      )}

      {/* Top Blockers */}
      {(report.top_blockers || []).length > 0 && (
        <SectionCard title="Top Blockers" icon={XCircle}>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-slate-200 text-left text-slate-500">
                  <th className="pb-1 pr-3">Field Code</th>
                  <th className="pb-1 pr-3">Stage</th>
                  <th className="pb-1 pr-3">Status</th>
                  <th className="pb-1 pr-3">Severity</th>
                  <th className="pb-1">Note</th>
                </tr>
              </thead>
              <tbody>
                {report.top_blockers.map((b, i) => (
                  <tr key={i} className="border-b border-slate-100 last:border-0">
                    <td className="py-1 pr-3 font-mono font-semibold text-red-700">{b.field_code}</td>
                    <td className="py-1 pr-3 text-slate-600">{b.stage_code}</td>
                    <td className="py-1 pr-3"><StatusBadge status={b.status} /></td>
                    <td className="py-1 pr-3"><StatusBadge status={b.severity} /></td>
                    <td className="py-1 text-slate-500">{b.note || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SectionCard>
      )}

      <div className="grid grid-cols-2 gap-4">
        {/* Manual Review */}
        <SectionCard title="Manual Review Summary" icon={FileText}>
          <KVTable data={{ Total: mr.total, Open: mr.open, Resolved: mr.resolved }} />
        </SectionCard>

        {/* Defect Summary */}
        <SectionCard title="Defect Summary" icon={AlertTriangle}>
          <KVTable data={{
            'Total Escalations': def.total_escalations,
            'Open':              def.open,
            'Resolved':          def.resolved,
            'Critical Open':     def.critical_open,
          }} />
        </SectionCard>
      </div>

      {/* Source / Fallback */}
      <SectionCard title="Source / Fallback Summary" icon={FileText}>
        <KVTable data={{
          'Parser Runs Total':   sf.parser_runs_total,
          'Success':             sf.parser_runs_success,
          'Failed':              sf.parser_runs_failed,
          'Avg Confidence':      sf.avg_confidence ? `${sf.avg_confidence}%` : '—',
        }} />
      </SectionCard>

      {/* Corrections Applied Today */}
      {corr.length > 0 && (
        <SectionCard title={`Corrections Applied Today (${corr.length})`} icon={RefreshCw}>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-slate-200 text-left text-slate-500">
                  <th className="pb-1 pr-3">Field Code</th>
                  <th className="pb-1 pr-3">Stage</th>
                  <th className="pb-1 pr-3">Original</th>
                  <th className="pb-1 pr-3">Corrected</th>
                  <th className="pb-1">Source</th>
                </tr>
              </thead>
              <tbody>
                {corr.map((c, i) => (
                  <tr key={i} className="border-b border-slate-100 last:border-0">
                    <td className="py-1 pr-3 font-mono font-semibold text-purple-700">{c.field_code}</td>
                    <td className="py-1 pr-3 text-slate-600">{c.stage_code}</td>
                    <td className="py-1 pr-3 text-red-600 line-through">{c.original_value}</td>
                    <td className="py-1 pr-3 text-green-700 font-semibold">{c.corrected_value}</td>
                    <td className="py-1 text-slate-400">{c.source || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SectionCard>
      )}

      {/* Next-Day Critical Path */}
      <SectionCard title="Next-Day Critical Path" icon={Clock}>
        <p className={`mb-2 text-xs font-semibold ${ncp.action_required ? 'text-red-600' : 'text-green-600'}`}>
          {ncp.action_required ? 'Action Required' : 'No blockers — clear for next day'}
        </p>
        {(ncp.blocked_stages || []).length > 0 && (
          <div className="mb-2">
            <p className="text-xs font-semibold text-slate-600 mb-1">Blocked Stages:</p>
            {ncp.blocked_stages.map((s, i) => (
              <div key={i} className="flex items-center gap-2 text-xs text-red-700">
                <XCircle size={11} /> {s.stage_code} — {s.error || s.status}
              </div>
            ))}
          </div>
        )}
        {(ncp.critical_missing || []).length > 0 && (
          <div>
            <p className="text-xs font-semibold text-slate-600 mb-1">Critical Missing Fields:</p>
            {ncp.critical_missing.map((f, i) => (
              <div key={i} className="text-xs text-red-700 font-mono">
                {f.field_code} ({f.stage_code}) — {f.note || ''}
              </div>
            ))}
          </div>
        )}
      </SectionCard>
    </div>
  );
}

// ── Weekly Report View ────────────────────────────────────────────────────────
function WeeklyReportView({ report }) {
  const h   = report.header || {};
  const tp  = report.throughput || {};
  const val = report.validation_summary || {};
  const ps  = report.parser_stability || {};
  const def = report.defect_summary || {};

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-purple-200 bg-purple-50 p-4">
        <p className="text-xs text-purple-400 font-semibold tracking-wide uppercase">Weekly Roll-up</p>
        <p className="text-lg font-bold text-purple-900">{h.project_name}</p>
        <p className="text-xs text-purple-600">
          Week {h.week} &nbsp;·&nbsp; {h.week_start} → {h.week_end} &nbsp;·&nbsp; Build {h.build_version}
        </p>
      </div>

      <div className="grid grid-cols-4 gap-3">
        {[
          { label: 'Stages Passed',   val: tp.stages_passed,           color: 'text-green-700' },
          { label: 'Stages Failed',   val: tp.stages_failed_or_blocked, color: 'text-red-700' },
          { label: 'Re-runs',         val: tp.reruns_triggered,         color: 'text-orange-600' },
          { label: 'Close Discipline',val: `${tp.close_discipline_pct ?? 0}%`, color: 'text-blue-700' },
        ].map(({ label, val: v, color }) => (
          <div key={label} className="rounded-lg border border-slate-200 bg-white p-3 text-center shadow-sm">
            <p className={`text-2xl font-bold ${color}`}>{v ?? 0}</p>
            <p className="text-xs text-slate-500 mt-0.5">{label}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-4">
        <SectionCard title="Validation Summary" icon={CheckCircle}>
          <KVTable data={{
            'Total Rules Evaluated': val.total_rules_evaluated,
            'Critical':              val.CRITICAL,
            'Major':                 val.MAJOR,
            'Minor':                 val.MINOR,
            'Release Blockers':      val.release_blockers,
          }} />
        </SectionCard>
        <SectionCard title="Parser Stability" icon={BarChart2}>
          <KVTable data={{
            'Total Runs':      ps.total_runs,
            'Success':         ps.success,
            'Failed':          ps.failed,
            'Stability':       `${ps.stability_pct ?? 0}%`,
          }} />
          {(ps.unstable_parsers || []).length > 0 && (
            <div className="mt-2">
              <p className="text-xs font-semibold text-slate-500 mb-1">Unstable Parsers:</p>
              {ps.unstable_parsers.map((p, i) => (
                <div key={i} className="text-xs text-red-600">{p.parser}: {p.failures} failure(s)</div>
              ))}
            </div>
          )}
        </SectionCard>
      </div>

      {(report.recurring_blockers || []).length > 0 && (
        <SectionCard title="Recurring Blockers" icon={AlertTriangle}>
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-slate-200 text-left text-slate-500">
                <th className="pb-1 pr-4">Field Code</th>
                <th className="pb-1">Occurrences</th>
              </tr>
            </thead>
            <tbody>
              {report.recurring_blockers.map((b, i) => (
                <tr key={i} className="border-b border-slate-100 last:border-0">
                  <td className="py-1 pr-4 font-mono font-semibold text-red-700">{b.field_code}</td>
                  <td className="py-1 text-slate-700">{b.occurrences}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </SectionCard>
      )}

      <SectionCard title="Defect Summary" icon={AlertTriangle}>
        <KVTable data={{
          'Opened':       def.opened,
          'Resolved':     def.resolved,
          'Net Open':     def.net_open,
          'SLA Breaches': def.sla_breaches,
        }} />
      </SectionCard>

      {(report.top_10_improvement_areas || []).length > 0 && (
        <SectionCard title="Top Improvement Areas" icon={TrendingUp}>
          <ol className="list-decimal list-inside space-y-1">
            {report.top_10_improvement_areas.map((item, i) => (
              <li key={i} className="text-xs text-slate-700">{item}</li>
            ))}
          </ol>
        </SectionCard>
      )}
    </div>
  );
}

// ── Monthly Report View ───────────────────────────────────────────────────────
function MonthlyReportView({ report }) {
  const h   = report.header || {};
  const eff = report.system_effectiveness || {};
  const po  = report.pipeline_overview || {};
  const mgmt = report.management_summary || {};

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4">
        <p className="text-xs text-emerald-400 font-semibold tracking-wide uppercase">Monthly Management Report</p>
        <p className="text-lg font-bold text-emerald-900">{h.project_name}</p>
        <p className="text-xs text-emerald-600">
          {h.month} &nbsp;·&nbsp; Build {h.build_version} &nbsp;·&nbsp;
          <span className={`font-semibold ${mgmt.release_ready ? 'text-green-700' : 'text-red-700'}`}>
            {mgmt.release_ready ? 'Release Ready' : 'Not Release Ready'}
          </span>
        </p>
      </div>

      {/* Effectiveness Score */}
      <div className="rounded-lg border border-slate-200 bg-white p-4 text-center shadow-sm">
        <p className="text-xs text-slate-500 uppercase tracking-wide mb-1">System Effectiveness Score</p>
        <p className={`text-5xl font-black ${eff.score >= 80 ? 'text-green-600' : eff.score >= 60 ? 'text-yellow-600' : 'text-red-600'}`}>
          {eff.score ?? 0}
          <span className="text-2xl font-bold text-slate-400">/100</span>
        </p>
        <div className="mt-2 flex justify-center gap-4 text-xs text-slate-500">
          <span>Stage Pass: {eff.stage_pass_rate_pct ?? 0}%</span>
          <span>Parser Stability: {eff.parser_stability_pct ?? 0}%</span>
          <span>Release Blockers: {eff.release_blockers ?? 0}</span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {/* Component Health */}
        <SectionCard title="Component Health" icon={CheckCircle}>
          <div className="space-y-1">
            {Object.entries(report.component_health || {}).map(([comp, status]) => (
              <div key={comp} className="flex items-center justify-between text-xs">
                <span className="text-slate-600">{comp}</span>
                <StatusBadge status={status} />
              </div>
            ))}
          </div>
        </SectionCard>

        {/* Pipeline Overview */}
        <SectionCard title="Pipeline Overview" icon={BarChart2}>
          <KVTable data={{
            'Stages Completed':    po.stages_completed,
            'Stages Passed':       po.stages_passed,
            'Stages Failed':       po.stages_failed,
            'Re-runs':             po.reruns,
            'Files Processed':     po.files_processed,
            'Corrections Applied': po.corrections_applied,
          }} />
        </SectionCard>
      </div>

      {/* Root Cause Analysis */}
      {report.root_cause_analysis?.top_failing_fields?.length > 0 && (
        <SectionCard title="Root Cause Analysis — Top Failing Fields" icon={AlertTriangle}>
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-slate-200 text-left text-slate-500">
                <th className="pb-1 pr-4">Field Code</th>
                <th className="pb-1">Failure Count</th>
              </tr>
            </thead>
            <tbody>
              {report.root_cause_analysis.top_failing_fields.map((f, i) => (
                <tr key={i} className="border-b border-slate-100 last:border-0">
                  <td className="py-1 pr-4 font-mono text-red-700">{f.field_code}</td>
                  <td className="py-1">{f.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </SectionCard>
      )}

      {/* Improvement Register */}
      {(report.improvement_register || []).length > 0 && (
        <SectionCard title="Improvement Register (Next Version)" icon={TrendingUp}>
          <div className="space-y-1">
            {report.improvement_register.map((item, i) => (
              <div key={i} className="flex items-start gap-2 text-xs">
                <span className={`mt-0.5 rounded px-1.5 py-0.5 text-xs font-bold ${
                  item.priority === 'CRITICAL' ? 'bg-red-100 text-red-700' :
                  item.priority === 'HIGH'     ? 'bg-orange-100 text-orange-700' :
                  'bg-yellow-50 text-yellow-700'
                }`}>
                  {item.priority}
                </span>
                <span className="text-slate-700">[{item.area}] {item.item}</span>
              </div>
            ))}
          </div>
        </SectionCard>
      )}

      {/* Management Summary */}
      <SectionCard title="Management Summary" icon={FileText}>
        <KVTable data={{
          'Release Ready':      String(mgmt.release_ready),
          'Release Blockers':   mgmt.release_blockers,
          'Effectiveness Score': mgmt.effectiveness_score,
        }} />
        {(mgmt.key_risks || []).length > 0 && (
          <div className="mt-3">
            <p className="text-xs font-semibold text-slate-600 mb-1">Key Risks:</p>
            {mgmt.key_risks.map((risk, i) => (
              <p key={i} className="text-xs text-red-700">• {risk}</p>
            ))}
          </div>
        )}
      </SectionCard>
    </div>
  );
}

// ── Project Picker ────────────────────────────────────────────────────────────
function ProjectPicker({ currentProjectId }) {
  const navigate = useNavigate();
  const { data: projects = [], isLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: projectsApi.list,
  });

  return (
    <div className="relative">
      <select
        value={currentProjectId || ''}
        onChange={(e) => {
          if (e.target.value) navigate(`/reports/${e.target.value}`);
        }}
        className="w-full appearance-none rounded-md border border-slate-300 bg-white py-1.5 pl-3 pr-8 text-xs font-medium text-slate-800 shadow-sm focus:border-blue-500 focus:outline-none"
      >
        <option value="">— Select a project —</option>
        {(Array.isArray(projects) ? projects : []).map((p) => (
          <option key={p.id} value={p.id}>
            {p.proposal_id} · {p.name}
          </option>
        ))}
      </select>
      <ChevronDown size={12} className="pointer-events-none absolute right-2 top-2 text-slate-400" />
      {isLoading && <p className="mt-1 text-xxs text-slate-400">Loading projects…</p>}
    </div>
  );
}

// ── Report History List ───────────────────────────────────────────────────────
const QC_BADGE = {
  approved: 'bg-green-100 text-green-700',
  pending:  'bg-yellow-50 text-yellow-600',
  rejected: 'bg-red-100 text-red-700',
};

function ReportHistoryList({ projectId, activeType, onSelect, selectedId }) {
  const { data: records = [], isLoading } = useQuery({
    queryKey: ['reports-list', projectId, activeType],
    queryFn: () => reportsApi.list(projectId, activeType),
    enabled: !!projectId,
  });

  if (isLoading) return <LoadingSpinner size="sm" />;
  if (!records.length) return <p className="text-xs text-slate-400 px-1">No reports yet.</p>;

  return (
    <div className="space-y-1">
      {records.map((r) => (
        <button
          key={r.report_id}
          onClick={() => onSelect(r)}
          className={`w-full text-left rounded-md px-3 py-2 text-xs border transition-colors ${
            selectedId === r.report_id
              ? 'bg-blue-50 border-blue-300'
              : 'hover:bg-slate-100 border-transparent hover:border-slate-200'
          }`}
        >
          <div className="font-semibold text-slate-800">{r.report_date}
            {r.sequence > 1 && <span className="ml-1 text-xxs text-slate-400">#{r.sequence}</span>}
          </div>
          <div className="flex items-center gap-1 mt-0.5">
            <span className={`rounded px-1.5 py-0.5 text-xxs font-semibold ${QC_BADGE[r.qc_status] || QC_BADGE.pending}`}>
              {r.qc_status || 'pending'}
            </span>
            <span className="text-slate-400">{r.generated_at?.slice(0, 16).replace('T', ' ')}</span>
          </div>
        </button>
      ))}
    </div>
  );
}

// ── Scheduler Status Panel ───────────────────────────────────────────────────
function SchedulerPanel() {
  const qc = useQueryClient();
  const { data: status, isLoading } = useQuery({
    queryKey: ['scheduler-status'],
    queryFn:  reportsApi.schedulerStatus,
    refetchInterval: 60000,
  });

  const triggerMutation = useMutation({
    mutationFn: (jobType) => reportsApi.triggerNow(jobType),
    onSuccess: () => qc.invalidateQueries(['scheduler-status']),
  });

  const JOB_SCHEDULE = [
    { type: 'daily',   label: 'Daily',   schedule: 'Every day at 5:00 PM',     color: 'blue' },
    { type: 'weekly',  label: 'Weekly',  schedule: 'Every Friday at 5:15 PM',  color: 'purple' },
    { type: 'monthly', label: 'Monthly', schedule: '30th of month at 5:30 PM', color: 'emerald' },
  ];

  const jobMap = {};
  (status?.jobs || []).forEach(j => { jobMap[j.id.replace('_reports', '')] = j; });

  return (
    <div className="rounded-lg border border-slate-200 bg-white shadow-sm overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
        <div className="flex items-center gap-2">
          <Clock size={14} className="text-blue-600" />
          <span className="text-sm font-semibold text-slate-800">Automated Scheduler</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className={`h-2 w-2 rounded-full ${status?.running ? 'bg-green-500 animate-pulse' : 'bg-slate-300'}`} />
          <span className={`text-xs font-semibold ${status?.running ? 'text-green-600' : 'text-slate-400'}`}>
            {isLoading ? 'Checking…' : status?.running ? 'Running' : 'Offline'}
          </span>
        </div>
      </div>

      {status?.available === false && (
        <div className="px-4 py-3 bg-amber-50 border-b border-amber-100">
          <p className="text-xs text-amber-700 font-medium">APScheduler not installed.</p>
          <code className="text-xs text-amber-900 bg-amber-100 px-2 py-0.5 rounded mt-1 block">
            pip install apscheduler
          </code>
          <p className="text-xs text-amber-600 mt-1">Then restart the backend server.</p>
        </div>
      )}

      <div className="divide-y divide-slate-100">
        {JOB_SCHEDULE.map(({ type, label, schedule, color }) => {
          const job     = jobMap[type];
          const nextRun = job?.next_run_utc
            ? new Date(job.next_run_utc).toLocaleString()
            : '—';
          const colorMap = {
            blue:    'bg-blue-50 text-blue-700',
            purple:  'bg-purple-50 text-purple-700',
            emerald: 'bg-emerald-50 text-emerald-700',
          };
          return (
            <div key={type} className="flex items-center justify-between px-4 py-3">
              <div>
                <div className="flex items-center gap-2">
                  <span className={`rounded px-2 py-0.5 text-xs font-semibold ${colorMap[color]}`}>
                    {label}
                  </span>
                  <span className="text-xs text-slate-500">{schedule}</span>
                </div>
                {job && (
                  <p className="text-xxs text-slate-400 mt-0.5">Next: {nextRun}</p>
                )}
              </div>
              <button
                onClick={() => triggerMutation.mutate(type)}
                disabled={triggerMutation.isPending}
                title={`Run ${label} report now (test)`}
                className="flex items-center gap-1 rounded border border-slate-300 px-2 py-1 text-xs text-slate-600 hover:bg-slate-100 disabled:opacity-40"
              >
                {triggerMutation.isPending && triggerMutation.variables === type
                  ? <RefreshCw size={11} className="animate-spin" />
                  : <RefreshCw size={11} />
                }
                Run Now
              </button>
            </div>
          );
        })}
      </div>

      {triggerMutation.isSuccess && (
        <div className="px-4 py-2 bg-green-50 border-t border-green-100 text-xs text-green-700">
          ✓ {triggerMutation.data?.message}
          {triggerMutation.data?.elapsed_s && ` (${triggerMutation.data.elapsed_s}s)`}
        </div>
      )}
      {triggerMutation.isError && (
        <div className="px-4 py-2 bg-red-50 border-t border-red-100 text-xs text-red-700">
          ✗ {triggerMutation.error?.message}
        </div>
      )}
    </div>
  );
}


// ── Main Page ─────────────────────────────────────────────────────────────────
export default function ReportsPage() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const [activeType, setActiveType] = useState('DAILY');
  const [viewingReport, setViewingReport] = useState(null);
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [qcName, setQcName] = useState('');
  const [rejectReason, setRejectReason] = useState('');
  const [showRejectInput, setShowRejectInput] = useState(false);

  const generateMutation = useMutation({
    mutationFn: () => {
      if (activeType === 'DAILY')   return reportsApi.generateDaily(projectId);
      if (activeType === 'WEEKLY')  return reportsApi.generateWeekly(projectId);
      if (activeType === 'MONTHLY') return reportsApi.generateMonthly(projectId);
    },
    onSuccess: (data) => {
      setViewingReport(data.report);
      setSelectedRecord({
        report_id:     data.report_id,
        report_id_str: data.report_id_str,
        report_date:   data.report_date || data.week || data.month,
        sequence:      data.sequence,
        qc_status:     data.qc_status,
      });
      qc.invalidateQueries(['reports-list', projectId, activeType]);
    },
  });

  const getReportMutation = useMutation({
    mutationFn: (rec) => reportsApi.get(projectId, rec.report_id),
    onSuccess: (data) => {
      setViewingReport(data.report);
      setSelectedRecord({
        report_id:     data.report_id,
        report_id_str: data.report_id_str,
        report_date:   data.report_date,
        sequence:      data.sequence,
        qc_status:     data.qc_status,
      });
    },
  });

  const signOffMutation = useMutation({
    mutationFn: ({ reportId, name }) => reportsApi.signOff(projectId, reportId, name),
    onSuccess: (data) => {
      setSelectedRecord((prev) => prev ? { ...prev, qc_status: data.qc_status } : prev);
      setShowRejectInput(false);
      qc.invalidateQueries(['reports-list', projectId, activeType]);
    },
  });

  const rejectMutation = useMutation({
    mutationFn: ({ reportId, name, reason }) => reportsApi.reject(projectId, reportId, name, reason),
    onSuccess: (data) => {
      setSelectedRecord((prev) => prev ? { ...prev, qc_status: data.qc_status } : prev);
      setShowRejectInput(false);
      setRejectReason('');
      qc.invalidateQueries(['reports-list', projectId, activeType]);
    },
  });

  function handleSelectRecord(rec) {
    setSelectedRecord(rec);
    setShowRejectInput(false);
    setRejectReason('');
    getReportMutation.mutate(rec);
  }

  return (
    <div className="flex min-h-screen flex-col">
      <TopBar
        title="Automated Reports"
        subtitle="Daily · Weekly · Monthly operational records"
        actions={
          <button
            onClick={() => generateMutation.mutate()}
            disabled={generateMutation.isPending || !projectId}
            title={!projectId ? 'Select a project first' : undefined}
            className="flex h-8 items-center gap-1.5 rounded-md bg-blue-700 px-3 text-xs font-semibold text-white hover:bg-blue-800 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {generateMutation.isPending ? (
              <><RefreshCw size={13} className="animate-spin" /> Generating…</>
            ) : (
              <><RefreshCw size={13} /> Generate {activeType}</>
            )}
          </button>
        }
      />

      <div className="flex flex-1 overflow-hidden">
        {/* ── Left Panel: type selector + history ─────────────── */}
        <aside className="w-56 flex-shrink-0 border-r border-slate-200 bg-white">
          {/* Project selector */}
          <div className="p-3 border-b border-slate-200">
            <p className="mb-1.5 text-xxs font-bold tracking-widest text-slate-400 uppercase">Project</p>
            <ProjectPicker currentProjectId={projectId} />
          </div>
          <div className="p-3 border-b border-slate-200">
            {REPORT_TYPES.map(({ key, label, icon: Icon, desc }) => (
              <button
                key={key}
                onClick={() => { setActiveType(key); setViewingReport(null); setSelectedRecord(null); }}
                className={`mb-1 w-full flex items-start gap-2.5 rounded-md px-3 py-2 text-left text-xs transition-colors ${
                  activeType === key
                    ? 'bg-blue-700 text-white'
                    : 'text-slate-700 hover:bg-slate-100'
                }`}
              >
                <Icon size={14} className="mt-0.5 flex-shrink-0" />
                <div>
                  <p className="font-semibold">{label}</p>
                  <p className={`text-xxs leading-tight ${activeType === key ? 'text-blue-200' : 'text-slate-400'}`}>{desc}</p>
                </div>
              </button>
            ))}
          </div>
          <div className="p-3">
            <p className="mb-2 text-xxs font-bold tracking-widest text-slate-400 uppercase">History</p>
            <ReportHistoryList
              projectId={projectId}
              activeType={activeType}
              onSelect={handleSelectRecord}
              selectedId={selectedRecord?.report_id}
            />
          </div>
        </aside>

        {/* ── Right Panel: report content ──────────────────────── */}
        <div className="flex-1 overflow-y-auto p-6">
          {/* Scheduler status — always visible at top */}
          <div className="mb-5">
            <SchedulerPanel />
          </div>

          {/* Error */}
          {generateMutation.isError && (
            <div className="mb-4 rounded-md border border-red-200 bg-red-50 p-3 text-xs text-red-700">
              {generateMutation.error?.message || 'Failed to generate report.'}
            </div>
          )}

          {/* Loading */}
          {(generateMutation.isPending || getReportMutation.isPending) && (
            <div className="flex h-40 items-center justify-center">
              <LoadingSpinner size="lg" />
            </div>
          )}

          {/* Report View */}
          {viewingReport && !generateMutation.isPending && !getReportMutation.isPending && (
            <>
              {/* Export + QC bar */}
              <div className="mb-4 rounded-lg border border-slate-200 bg-white shadow-sm overflow-hidden">
                <div className="flex items-center justify-between px-4 py-2.5">
                  {/* Left: report identity */}
                  <div>
                    <p className="text-xs font-semibold text-slate-800">
                      {selectedRecord?.report_id_str || selectedRecord?.report_date}
                    </p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className={`rounded px-1.5 py-0.5 text-xxs font-semibold ${QC_BADGE[selectedRecord?.qc_status] || QC_BADGE.pending}`}>
                        {selectedRecord?.qc_status || 'pending'}
                      </span>
                      {selectedRecord?.sequence > 1 && (
                        <span className="text-xxs text-slate-400">Run #{selectedRecord.sequence}</span>
                      )}
                    </div>
                  </div>

                  {/* Right: QC actions + exports */}
                  <div className="flex items-center gap-2 flex-wrap justify-end">
                    {/* QC sign-off — only show when pending */}
                    {selectedRecord?.qc_status === 'pending' && (
                      <>
                        <input
                          type="text"
                          placeholder="Your name"
                          value={qcName}
                          onChange={(e) => setQcName(e.target.value)}
                          className="rounded border border-slate-300 px-2 py-1 text-xs w-28 focus:outline-none focus:border-blue-400"
                        />
                        <button
                          onClick={() => qcName.trim() && signOffMutation.mutate({ reportId: selectedRecord.report_id, name: qcName.trim() })}
                          disabled={signOffMutation.isPending || !qcName.trim()}
                          className="flex items-center gap-1 rounded border border-green-400 bg-green-50 px-2 py-1 text-xs text-green-700 hover:bg-green-100 disabled:opacity-40"
                        >
                          <ThumbsUp size={11} /> Approve
                        </button>
                        <button
                          onClick={() => setShowRejectInput((v) => !v)}
                          className="flex items-center gap-1 rounded border border-red-300 bg-red-50 px-2 py-1 text-xs text-red-700 hover:bg-red-100"
                        >
                          <ThumbsDown size={11} /> Reject
                        </button>
                      </>
                    )}

                    {/* Export links */}
                    <span className="text-xs text-slate-400 ml-1">Export:</span>
                    {['json', 'xlsx', 'docx'].map((fmt) => (
                      <a
                        key={fmt}
                        href={reportsApi.exportUrl(projectId, selectedRecord?.report_id, fmt)}
                        target="_blank"
                        rel="noreferrer"
                        className="flex items-center gap-1 rounded border border-slate-300 px-2 py-1 text-xs text-slate-600 hover:bg-slate-100"
                      >
                        <Download size={11} /> {fmt.toUpperCase()}
                      </a>
                    ))}
                  </div>
                </div>

                {/* Reject reason input — slides in below the bar */}
                {showRejectInput && (
                  <div className="border-t border-red-100 bg-red-50 px-4 py-2.5 flex items-center gap-2">
                    <input
                      type="text"
                      placeholder="Rejection reason (required)"
                      value={rejectReason}
                      onChange={(e) => setRejectReason(e.target.value)}
                      className="flex-1 rounded border border-red-300 px-2 py-1 text-xs focus:outline-none focus:border-red-500 bg-white"
                    />
                    <button
                      onClick={() => {
                        if (qcName.trim() && rejectReason.trim()) {
                          rejectMutation.mutate({
                            reportId: selectedRecord.report_id,
                            name:     qcName.trim(),
                            reason:   rejectReason.trim(),
                          });
                        }
                      }}
                      disabled={rejectMutation.isPending || !qcName.trim() || !rejectReason.trim()}
                      className="flex items-center gap-1 rounded border border-red-400 bg-red-100 px-2 py-1 text-xs text-red-800 hover:bg-red-200 disabled:opacity-40"
                    >
                      {rejectMutation.isPending ? <RefreshCw size={11} className="animate-spin" /> : <ThumbsDown size={11} />}
                      Confirm Reject
                    </button>
                    <button onClick={() => setShowRejectInput(false)} className="text-xs text-slate-400 hover:text-slate-600">Cancel</button>
                  </div>
                )}

                {/* QC feedback messages */}
                {(signOffMutation.isSuccess || rejectMutation.isSuccess) && (
                  <div className={`border-t px-4 py-1.5 text-xs ${signOffMutation.isSuccess ? 'bg-green-50 border-green-100 text-green-700' : 'bg-red-50 border-red-100 text-red-700'}`}>
                    {signOffMutation.isSuccess ? '✓ Report approved' : `✗ Report rejected`}
                  </div>
                )}
              </div>

              {activeType === 'DAILY'   && <DailyReportView   report={viewingReport} />}
              {activeType === 'WEEKLY'  && <WeeklyReportView  report={viewingReport} />}
              {activeType === 'MONTHLY' && <MonthlyReportView report={viewingReport} />}
            </>
          )}

          {/* Empty state */}
          {!viewingReport && !generateMutation.isPending && !getReportMutation.isPending && (
            <div className="flex h-64 flex-col items-center justify-center gap-3 text-center">
              <FileText size={40} className="text-slate-300" />
              {!projectId ? (
                <>
                  <p className="text-sm font-semibold text-slate-600">Select a project</p>
                  <p className="text-xs text-slate-400">
                    Choose a project from the left panel to generate or view reports.
                  </p>
                </>
              ) : (
                <>
                  <p className="text-sm font-semibold text-slate-600">No report loaded</p>
                  <p className="text-xs text-slate-400">
                    Click <strong>Generate {activeType}</strong> to create today's report,
                    or select a past report from the history panel.
                  </p>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
