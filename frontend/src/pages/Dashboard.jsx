import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Activity, Building2, Database, Plus, RefreshCw } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { projectsApi } from '../api/projects';
import TopBar from '../components/layout/TopBar';
import ProjectCard from '../components/project/ProjectCard';
import LoadingSpinner from '../components/shared/LoadingSpinner';

export default function Dashboard() {
  const navigate = useNavigate();
  const { data: projects, isLoading, refetch } = useQuery({
    queryKey: ['projects'],
    queryFn: projectsApi.list,
    refetchInterval: 30000,
  });

  const list = Array.isArray(projects) ? projects : [];

  return (
    <div className="flex min-h-screen flex-col">
      <TopBar
        title="Dashboard"
        subtitle={`${list.length} project${list.length !== 1 ? 's' : ''}`}
        actions={
          <div className="flex items-center gap-2">
            <button
              onClick={() => refetch()}
              className="flex h-8 w-8 items-center justify-center rounded-md border border-slate-300 bg-white text-slate-600 hover:border-slate-400"
              title="Refresh"
            >
              <RefreshCw size={13} />
            </button>
            <button
              onClick={() => navigate('/projects/new')}
              className="flex h-8 items-center gap-1.5 rounded-md bg-blue-700 px-3 text-xs font-semibold text-white hover:bg-blue-800"
            >
              <Plus size={13} /> New Project
            </button>
          </div>
        }
      />

      <div className="flex-1 overflow-y-auto p-6">
        {isLoading ? (
          <div className="flex h-40 items-center justify-center">
            <LoadingSpinner size="lg" />
          </div>
        ) : list.length === 0 ? (
          <EmptyState onNew={() => navigate('/projects/new')} />
        ) : (
          <>
            <div className="mb-6 grid grid-cols-4 gap-4">
              <StatCard label="Total Projects" value={list.length} icon={Building2} color="text-blue-700" />
              <StatCard label="Active" value={list.filter((project) => project.status !== 'COMPLETED').length} icon={Activity} color="text-emerald-700" />
              <StatCard label="Master DB" value="Ready" icon={Database} color="text-amber-600" />
              <StatCard label="Phase 2" value="Live" icon={Activity} color="text-slate-700" />
            </div>

            <div className="grid grid-cols-3 gap-4">
              {list.map((project) => (
                <ProjectCard key={project.id} project={project} />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function StatCard({ label, value, icon: Icon, color }) {
  return (
    <div className="rounded-md border border-slate-300 bg-white px-4 py-3">
      <div className="mb-2 flex items-center justify-between">
        <p className="text-xxs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
        <Icon size={14} className={color} />
      </div>
      <p className="text-2xl font-bold text-slate-950">{value}</p>
    </div>
  );
}

function EmptyState({ onNew }) {
  return (
    <div className="flex h-64 flex-col items-center justify-center text-center">
      <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-blue-50 ring-1 ring-blue-200">
        <Building2 size={24} className="text-blue-700" />
      </div>
      <h3 className="mb-1 text-sm font-bold text-slate-950">No projects yet</h3>
      <p className="mb-4 max-w-xs text-xs text-slate-500">Create a steel detailing project to begin Phase 2 tracking.</p>
      <button
        onClick={onNew}
        className="flex items-center gap-1.5 rounded-md bg-blue-700 px-4 py-2 text-xs font-semibold text-white hover:bg-blue-800"
      >
        <Plus size={13} /> Create Project
      </button>
    </div>
  );
}
