import React from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { zodResolver } from '@hookform/resolvers/zod';
import { ArrowLeft, Building2, Plus } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { useNavigate } from 'react-router-dom';
import { z } from 'zod';
import { projectsApi } from '../api/projects';
import TopBar from '../components/layout/TopBar';
import { useNotificationStore } from '../store/notificationStore';

const PROJECT_TYPES = ['Industrial Building', 'Warehouse', 'Multi-storey', 'Commercial Building', 'Process Plant', 'Other'];

const schema = z.object({
  name: z.string().min(3, 'Project name required'),
  proposal_id: z.string().min(2, 'Project ID required'),
  project_type: z.enum(PROJECT_TYPES),
  location: z.string().optional(),
});

export default function NewProject() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { add } = useNotificationStore();

  const { register, handleSubmit, formState: { errors } } = useForm({
    resolver: zodResolver(schema),
    defaultValues: { project_type: 'Industrial Building' },
  });

  const create = useMutation({
    mutationFn: projectsApi.create,
    onSuccess: (project) => {
      qc.invalidateQueries({ queryKey: ['projects'] });
      add({ type: 'success', text: `Project "${project.name}" created` });
      navigate(`/projects/${project.id}`);
    },
    onError: (error) => add({ type: 'error', text: error.message }),
  });

  return (
    <div className="flex min-h-screen flex-col">
      <TopBar
        title="New Project"
        actions={
          <button
            onClick={() => navigate('/')}
            className="flex h-8 items-center gap-1.5 rounded-md border border-slate-300 bg-white px-3 text-xs font-semibold text-slate-700 hover:border-slate-400"
          >
            <ArrowLeft size={13} /> Back
          </button>
        }
      />

      <div className="flex flex-1 justify-center overflow-y-auto p-6">
        <div className="w-full max-w-xl">
          <div className="mb-5 flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-md bg-blue-50 ring-1 ring-blue-200">
              <Building2 size={18} className="text-blue-700" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-950">Create PEB Project</h2>
              <p className="text-xs text-slate-500">Project identity for Phase 2 tracking</p>
            </div>
          </div>

          <form onSubmit={handleSubmit((data) => create.mutate(data))} className="space-y-4">
            <div className="rounded-md border border-slate-300 bg-white p-4">
              <h3 className="mb-4 text-xs font-bold uppercase tracking-wide text-slate-500">Project Identity</h3>
              <div className="space-y-4">
                <Field label="Project Name *" error={errors.name?.message}>
                  <input {...register('name')} placeholder="Warehouse Building - Chennai" className="input-field" />
                </Field>

                <div className="grid grid-cols-2 gap-3">
                  <Field label="Project / Proposal ID *" error={errors.proposal_id?.message}>
                    <input {...register('proposal_id')} placeholder="INFINITI-PRJ-2405" className="input-field" />
                  </Field>
                  <Field label="Project Type *" error={errors.project_type?.message}>
                    <select {...register('project_type')} className="input-field">
                      {PROJECT_TYPES.map((type) => <option key={type}>{type}</option>)}
                    </select>
                  </Field>
                </div>

                <Field label="Location" error={null}>
                  <input {...register('location')} placeholder="Chennai, India" className="input-field" />
                </Field>
              </div>
            </div>

            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => navigate('/')}
                className="flex-1 rounded-md border border-slate-300 bg-white py-2.5 text-xs font-semibold text-slate-700 hover:border-slate-400"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={create.isPending}
                className="flex flex-1 items-center justify-center gap-1.5 rounded-md bg-blue-700 py-2.5 text-xs font-semibold text-white hover:bg-blue-800 disabled:opacity-50"
              >
                {create.isPending ? (
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                ) : (
                  <>
                    <Plus size={13} /> Create Project
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      </div>

      <style>{`
        .input-field {
          width: 100%;
          background: #ffffff;
          border: 1px solid #cbd5e1;
          border-radius: 0.375rem;
          padding: 0.55rem 0.75rem;
          font-size: 0.75rem;
          color: #0f172a;
          outline: none;
          transition: border-color 0.2s, box-shadow 0.2s;
        }
        .input-field:focus {
          border-color: #2563eb;
          box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
        }
        .input-field::placeholder { color: #94a3b8; }
      `}</style>
    </div>
  );
}

function Field({ label, error, children }) {
  return (
    <div>
      <label className="mb-1 block text-xxs font-semibold uppercase tracking-wide text-slate-500">{label}</label>
      {children}
      {error && <p className="mt-1 text-xxs text-red-600">{error}</p>}
    </div>
  );
}
