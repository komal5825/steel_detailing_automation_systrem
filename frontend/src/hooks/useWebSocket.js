import { useEffect, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useNotificationStore } from '../store/notificationStore';
import { useWsStore } from '../store/wsStore';

export function useWebSocket(projectUuid) {
  const wsRef = useRef(null);
  const { addMessage, setConnected } = useWsStore();
  const { add: addNotification } = useNotificationStore();
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!projectUuid) return undefined;

    const wsBase = import.meta.env.VITE_WS_BASE_URL || 'ws://localhost:8000/ws';
    const wsUrl = `${wsBase}/${projectUuid}`;
    let reconnectTimer;
    let closedByHook = false;

    const connect = () => {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        ws.send('ping');
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'pong') return;
          addMessage(msg);

          if (msg.type === 'snapshot') {
            queryClient.invalidateQueries({ queryKey: ['stages', projectUuid] });
          }

          if (msg.type === 'stage_update') {
            queryClient.invalidateQueries({ queryKey: ['stages', projectUuid] });
            queryClient.invalidateQueries({ queryKey: ['pipeline', projectUuid] });
            const label = msg.stage_code ? `${msg.stage_code} -> ${msg.status}` : '';
            if (label) {
              const type = msg.status === 'PASSED' ? 'success' : msg.status === 'FAILED' ? 'error' : 'info';
              addNotification({ type, text: `Stage update: ${label}` });
            }
          }
        } catch {
          // Ignore non-JSON WebSocket payloads.
        }
      };

      ws.onclose = () => {
        setConnected(false);
        if (!closedByHook) reconnectTimer = setTimeout(connect, 3000);
      };

      ws.onerror = () => {
        ws.close();
      };
    };

    connect();

    return () => {
      closedByHook = true;
      clearTimeout(reconnectTimer);
      wsRef.current?.close();
    };
  }, [projectUuid, addMessage, setConnected, addNotification, queryClient]);

  const sendPing = () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send('ping');
    }
  };

  return { sendPing };
}
