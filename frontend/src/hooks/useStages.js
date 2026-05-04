import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { stagesApi } from '../api/stages';
import { useNotificationStore } from '../store/notificationStore';

export function useStages(projectUuid) {
  return useQuery({
    queryKey: ['stages', projectUuid],
    queryFn: () => stagesApi.getStatus(projectUuid),
    enabled: !!projectUuid,
    refetchInterval: 5000,
    select: (data) => data?.stages ?? [],
  });
}

export function usePipelineStatus(projectUuid) {
  return useQuery({
    queryKey: ['pipeline', projectUuid],
    queryFn: () => stagesApi.getPipelineStatus(projectUuid),
    enabled: !!projectUuid,
    refetchInterval: 5000,
  });
}

export function useRunPipeline(projectUuid) {
  const qc = useQueryClient();
  const { add } = useNotificationStore();
  return useMutation({
    mutationFn: (fromStage) => stagesApi.runPipeline(projectUuid, fromStage),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['stages', projectUuid] });
      qc.invalidateQueries({ queryKey: ['pipeline', projectUuid] });
      add({ type: 'success', text: 'Pipeline started successfully' });
    },
    onError: (e) => add({ type: 'error', text: e.message }),
  });
}

export function useRunStage(projectUuid) {
  const qc = useQueryClient();
  const { add } = useNotificationStore();
  return useMutation({
    mutationFn: (stageCode) => stagesApi.runStage(projectUuid, stageCode),
    onSuccess: (_, stageCode) => {
      qc.invalidateQueries({ queryKey: ['stages', projectUuid] });
      add({ type: 'success', text: `Stage ${stageCode} re-run triggered` });
    },
    onError: (e) => add({ type: 'error', text: e.message }),
  });
}
