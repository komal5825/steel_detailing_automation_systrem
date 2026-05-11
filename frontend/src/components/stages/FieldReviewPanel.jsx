import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CheckCircle2, Play, Save, Send, ShieldAlert } from 'lucide-react';
import { stagesApi } from '../../api/stages';
import LoadingSpinner from '../shared/LoadingSpinner';

export default function FieldReviewPanel({ projectId, stageCode }) {
  const qc = useQueryClient();
  const [overrides, setOverrides] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { data: fields = [], isLoading } = useQuery({
    queryKey: ['fields', projectId, stageCode],
    queryFn: () => stagesApi.getFields(projectId, stageCode),
    enabled: !!projectId && !!stageCode,
  });

  const overrideMutation = useMutation({
    mutationFn: (data) => stagesApi.overrideFields(projectId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['fields', projectId, stageCode] });
      qc.invalidateQueries({ queryKey: ['stages', projectId] });
      setOverrides({});
    },
  });

  const approveMutation = useMutation({
    mutationFn: () => stagesApi.approveStage(projectId, stageCode),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['stages', projectId] });
    },
  });

  const resumeMutation = useMutation({
    mutationFn: (fromStage) => stagesApi.runPipeline(projectId, fromStage),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['stages', projectId] });
      qc.invalidateQueries({ queryKey: ['pipeline', projectId] });
      qc.invalidateQueries({ queryKey: ['fields', projectId, stageCode] });
    },
  });

  if (isLoading) return <div className="p-4"><LoadingSpinner size="sm" /></div>;
  
  const missingFields = fields.filter(f => f.status === 'MISSING');
  if (missingFields.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-8 text-center bg-emerald-50 border border-emerald-200 rounded-md">
        <CheckCircle2 size={32} className="text-emerald-600 mb-2" />
        <h3 className="text-sm font-bold text-emerald-900">All Fields Resolved</h3>
        <p className="text-xs text-emerald-700 mt-1">No missing fields detected for this stage.</p>
        <button
          onClick={() => approveMutation.mutate()}
          className="mt-4 flex items-center gap-2 rounded-md bg-emerald-600 px-4 py-2 text-xs font-semibold text-white hover:bg-emerald-700"
        >
          <Send size={14} /> Approve Stage
        </button>
      </div>
    );
  }

  const handleOverrideChange = (code, val) => {
    setOverrides(prev => ({ ...prev, [code]: val }));
  };

  const submitOverrides = async () => {
    setIsSubmitting(true);
    const payload = Object.entries(overrides).map(([code, value]) => ({
      field_code: code,
      value: value,
      note: 'User override via FieldReviewPanel'
    }));
    await overrideMutation.mutateAsync(payload);
    setIsSubmitting(false);
  };

  const applyAndResume = async () => {
    setIsSubmitting(true);
    const payload = Object.entries(overrides).map(([code, value]) => ({
      field_code: code,
      value: value,
      note: 'User override via FieldReviewPanel'
    }));
    if (payload.length > 0) {
      await overrideMutation.mutateAsync(payload);
    }
    await resumeMutation.mutateAsync(stageCode);
    setIsSubmitting(false);
  };

  return (
    <div className="rounded-md border border-amber-300 bg-amber-50">
      <div className="flex items-center gap-2 border-b border-amber-200 px-4 py-3 bg-amber-100/50">
        <ShieldAlert size={16} className="text-amber-600" />
        <h3 className="text-sm font-bold text-amber-900">Action Required: {missingFields.length} Missing Fields</h3>
      </div>
      
      <div className="p-4 space-y-4">
        <p className="text-xs text-amber-800 leading-relaxed">
          The following critical fields were not detected in the governing source. 
          Please provide manual values to resolve these blockers.
        </p>

        <div className="space-y-3">
          {missingFields.map((field) => (
            <div key={field.id} className="grid grid-cols-12 gap-3 items-center">
              <div className="col-span-4">
                <span className="font-mono text-xxs font-bold text-amber-900 bg-amber-200 px-1.5 py-0.5 rounded">
                  {field.field_code}
                </span>
                <p className="text-xxs text-amber-700 mt-1 truncate" title={field.note}>{field.note || 'No description available'}</p>
              </div>
              <div className="col-span-8 flex gap-2">
                <input
                  type="text"
                  value={overrides[field.field_code] || ''}
                  onChange={(e) => handleOverrideChange(field.field_code, e.target.value)}
                  placeholder="Enter value..."
                  className="flex-1 rounded border border-amber-300 bg-white px-3 py-1.5 text-xs focus:ring-2 focus:ring-amber-500 focus:outline-none"
                />
              </div>
            </div>
          ))}
        </div>

        <div className="flex items-center justify-between pt-2">
          <p className="text-xxs text-amber-800">
            Resume control: pipeline will restart from <span className="font-mono font-bold">{stageCode}</span> after applying values.
          </p>
          <div className="flex gap-2">
            <button
              onClick={submitOverrides}
              disabled={Object.keys(overrides).length === 0 || isSubmitting}
              className="flex items-center gap-2 rounded-md bg-amber-600 px-4 py-2 text-xs font-semibold text-white hover:bg-amber-700 disabled:opacity-50"
            >
              <Save size={14} /> {isSubmitting ? 'Saving...' : 'Apply Overrides'}
            </button>
            <button
              onClick={applyAndResume}
              disabled={isSubmitting || resumeMutation.isPending}
              className="flex items-center gap-2 rounded-md bg-blue-700 px-4 py-2 text-xs font-semibold text-white hover:bg-blue-800 disabled:opacity-50"
            >
              <Play size={14} /> {resumeMutation.isPending ? 'Resuming...' : 'Apply + Resume'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
