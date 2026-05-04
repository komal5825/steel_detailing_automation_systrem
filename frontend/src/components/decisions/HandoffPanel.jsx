import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { CheckCircle, XCircle, Package, ExternalLink } from 'lucide-react';
import { handoffsApi } from '../../api/handoffs';
import { useNotificationStore } from '../../store/notificationStore';
import LoadingSpinner from '../shared/LoadingSpinner';

export default function HandoffPanel({ projectId, allPassed }) {
  const [engineerName, setEngineerName] = useState('');
  const qc = useQueryClient();
  const { add } = useNotificationStore();

  const { data: handoffList, isLoading } = useQuery({
    queryKey: ['handoffs', projectId],
    queryFn: () => handoffsApi.list(projectId),
    enabled: !!projectId && allPassed,
  });

  const approve = useMutation({
    mutationFn: ({ handoffId, decision }) =>
      handoffsApi.approve(projectId, handoffId, engineerName || 'Engineer', decision),
    onSuccess: (_, { decision }) => {
      qc.invalidateQueries({ queryKey: ['handoffs', projectId] });
      add({ type: decision === 1 ? 'success' : 'warning', text: decision === 1 ? 'Handoff approved — Phase 3 unlocked' : 'Handoff rejected' });
    },
    onError: (e) => add({ type: 'error', text: e.message }),
  });

  if (!allPassed) return null;

  const latest = handoffList?.[0];

  return (
    <div className="bg-green-950 border border-green-800 rounded-xl p-4 animate-fade-in">
      <div className="flex items-center gap-2 mb-3">
        <Package size={15} className="text-green-400" />
        <h3 className="text-sm font-semibold text-green-300">Phase 2 → Phase 3 Handoff Package</h3>
        {latest?.approved === 1 && (
          <span className="ml-auto text-xs text-green-400 font-medium">✓ Approved</span>
        )}
      </div>

      {isLoading && <LoadingSpinner size="sm" />}

      {latest ? (
        <div className="space-y-2">
          <div className="grid grid-cols-3 gap-3 text-xxs">
            <InfoBox label="From" value={latest.from_stage} />
            <InfoBox label="To" value={latest.to_stage} />
            <InfoBox label="Status" value={latest.approved === 1 ? 'Approved' : latest.approved === -1 ? 'Rejected' : 'Pending'} />
          </div>

          {latest.approved === null && (
            <>
              <div className="mt-3 flex items-center gap-2">
                <input
                  type="text"
                  placeholder="Your name (for audit trail)"
                  value={engineerName}
                  onChange={(e) => setEngineerName(e.target.value)}
                  className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-steel"
                />
              </div>
              <div className="flex gap-2 mt-2">
                <button
                  onClick={() => approve.mutate({ handoffId: latest.id, decision: 1 })}
                  disabled={approve.isPending}
                  className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 bg-green-700 hover:bg-green-600 text-white text-xs font-semibold rounded-lg transition-colors disabled:opacity-50"
                >
                  <CheckCircle size={12} /> Approve — Unlock Phase 3
                </button>
                <button
                  onClick={() => approve.mutate({ handoffId: latest.id, decision: -1 })}
                  disabled={approve.isPending}
                  className="px-3 py-2 bg-slate-800 hover:bg-red-950 border border-slate-700 hover:border-red-700 text-slate-300 hover:text-red-300 text-xs font-semibold rounded-lg transition-colors disabled:opacity-50"
                >
                  <XCircle size={12} className="inline mr-1" /> Reject
                </button>
              </div>
            </>
          )}
        </div>
      ) : (
        <p className="text-xs text-green-400">All Phase 2 stages passed. Generating handoff package…</p>
      )}
    </div>
  );
}

function InfoBox({ label, value }) {
  return (
    <div className="bg-green-900 bg-opacity-40 border border-green-800 rounded-lg px-3 py-2">
      <p className="text-green-600 uppercase tracking-wide mb-0.5">{label}</p>
      <p className="text-green-200 font-mono font-semibold">{value || '—'}</p>
    </div>
  );
}
