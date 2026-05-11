import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { ClipboardList, RefreshCw } from 'lucide-react';
import TopBar from '../components/layout/TopBar';
import LoadingSpinner from '../components/shared/LoadingSpinner';
import { projectsApi } from '../api/projects';
import { outputsApi } from '../api/outputs';

function prettyDetail(detail) {
  try {
    return JSON.stringify(detail || {}, null, 2);
  } catch {
    return String(detail || '');
  }
}

export default function AuditLogsPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const projectId = searchParams.get('projectId') || '';

  const { data: projects = [] } = useQuery({
    queryKey: ['projects'],
    queryFn: projectsApi.list,
    refetchInterval: 30000,
  });

  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['auditEvents', projectId],
    queryFn: () => outputsApi.getAuditEvents(projectId, 300),
    enabled: !!projectId,
    refetchInterval: 5000,
  });

  const events = data?.events || [];

  return (
    <div className="flex min-h-screen flex-col">
      <TopBar
        title="Audit Logs"
        subtitle={projectId ? `Project ${projectId.slice(0, 8)}` : 'Select a project'}
        actions={(
          <div className="flex items-center gap-2">
            <button
              onClick={() => navigate('/')}
              className="flex h-8 items-center rounded-md border border-slate-300 bg-white px-3 text-xs font-semibold text-slate-700 hover:border-slate-400"
            >
              Back
            </button>
            <button
              onClick={() => refetch()}
              disabled={!projectId || isFetching}
              className="flex h-8 items-center gap-1.5 rounded-md border border-slate-300 bg-white px-3 text-xs font-semibold text-slate-700 hover:border-slate-400 disabled:opacity-50"
            >
              <RefreshCw size={12} /> Refresh
            </button>
          </div>
        )}
      />

      <div className="flex-1 overflow-y-auto p-6">
        <div className="mb-4 rounded-md border border-slate-300 bg-white p-4">
          <label className="mb-2 block text-xs font-semibold text-slate-600">Project</label>
          <select
            value={projectId}
            onChange={(e) => {
              const next = e.target.value;
              if (!next) {
                searchParams.delete('projectId');
                setSearchParams(searchParams);
                return;
              }
              setSearchParams({ projectId: next });
            }}
            className="w-full max-w-lg rounded border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Select project...</option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.proposal_id || p.id.slice(0, 8)})
              </option>
            ))}
          </select>
        </div>

        {!projectId ? (
          <div className="rounded-md border border-slate-300 bg-white p-8 text-sm text-slate-600">
            Pick a project to view immutable runtime audit events.
          </div>
        ) : isLoading ? (
          <div className="flex h-40 items-center justify-center rounded-md border border-slate-300 bg-white">
            <LoadingSpinner size="lg" />
          </div>
        ) : (
          <div className="rounded-md border border-slate-300 bg-white">
            <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
              <div className="flex items-center gap-2">
                <ClipboardList size={14} className="text-blue-600" />
                <h2 className="text-sm font-bold text-slate-900">Runtime Audit Events</h2>
              </div>
              <span className="text-xs text-slate-500">{events.length} events shown</span>
            </div>
            {events.length === 0 ? (
              <div className="p-6 text-sm text-slate-500">No audit events found for this project.</div>
            ) : (
              <div className="max-h-[65vh] overflow-auto">
                <table className="w-full text-left text-xs">
                  <thead className="sticky top-0 bg-slate-50 text-xxs uppercase tracking-wide text-slate-500">
                    <tr>
                      <th className="px-3 py-2">Time</th>
                      <th className="px-3 py-2">Event</th>
                      <th className="px-3 py-2">Stage</th>
                      <th className="px-3 py-2">Actor</th>
                      <th className="px-3 py-2">Field</th>
                      <th className="px-3 py-2">Detail</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200">
                    {events.map((evt) => (
                      <tr key={evt.id} className="align-top hover:bg-slate-50">
                        <td className="whitespace-nowrap px-3 py-2 font-mono text-slate-600">{evt.created_at || '—'}</td>
                        <td className="px-3 py-2 font-semibold text-slate-900">{evt.event_type}</td>
                        <td className="px-3 py-2 font-mono text-slate-700">{evt.stage_code || '—'}</td>
                        <td className="px-3 py-2 text-slate-700">{evt.actor || 'system'}</td>
                        <td className="px-3 py-2 font-mono text-slate-700">{evt.field_code || '—'}</td>
                        <td className="px-3 py-2">
                          <details>
                            <summary className="cursor-pointer text-blue-700">View</summary>
                            <pre className="mt-1 max-w-[42rem] whitespace-pre-wrap rounded bg-slate-100 p-2 font-mono text-[10px] text-slate-700">
                              {prettyDetail(evt.detail)}
                            </pre>
                          </details>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

