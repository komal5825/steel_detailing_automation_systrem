import React from 'react';
import { Building2, Calendar, ChevronRight, MapPin } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { fmtRelative } from '../../utils/formatters';

export default function ProjectCard({ project }) {
  const navigate = useNavigate();

  return (
    <button
      onClick={() => navigate(`/projects/${project.id}`)}
      className="group w-full rounded-md border border-slate-300 bg-white p-4 text-left transition-colors hover:border-blue-300 hover:bg-blue-50/40"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-1 items-start gap-3">
          <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-md bg-blue-50 ring-1 ring-blue-200">
            <Building2 size={16} className="text-blue-700" />
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-bold text-slate-950">{project.name}</p>
            <p className="mt-0.5 truncate font-mono text-xxs text-slate-500">{project.proposal_id || project.id?.slice(0, 8)}</p>
            {project.location && (
              <p className="mt-1 flex items-center gap-1 truncate text-xxs text-slate-500">
                <MapPin size={10} /> {project.location}
              </p>
            )}
          </div>
        </div>
        <ChevronRight size={14} className="mt-1 flex-shrink-0 text-slate-400 transition-colors group-hover:text-blue-700" />
      </div>
      <div className="mt-3 flex items-center gap-3 text-xxs text-slate-500">
        <span className="flex items-center gap-1">
          <Calendar size={10} />
          {fmtRelative(project.created_at)}
        </span>
        {project.project_type && (
          <span className="rounded bg-slate-100 px-1.5 py-0.5 text-slate-600">{project.project_type}</span>
        )}
      </div>
    </button>
  );
}
