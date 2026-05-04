import React, { useEffect, useRef, useState } from 'react';
import { Activity, Trash2 } from 'lucide-react';
import { clsx } from 'clsx';
import { useWsStore } from '../../store/wsStore';
import { fmtTime } from '../../utils/formatters';

function stageTag(message) {
  if (message.stage_code) return message.stage_code;
  if (message.stages) return 'SNAPSHOT';
  return null;
}

function statusColor(status) {
  if (status === 'PASSED') return 'text-emerald-700';
  if (status === 'FAILED') return 'text-red-700';
  if (status === 'RUNNING' || status === 'IN_PROGRESS') return 'text-blue-700';
  if (status === 'AWAITING_INPUT') return 'text-amber-700';
  return 'text-slate-600';
}

export default function LiveLogPanel() {
  const messages = useWsStore((state) => state.messages);
  const clearMessages = useWsStore((state) => state.clearMessages);
  const connected = useWsStore((state) => state.connected);
  const bottomRef = useRef(null);
  const [autoScroll, setAutoScroll] = useState(true);

  useEffect(() => {
    if (autoScroll) bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, autoScroll]);

  return (
    <div className="overflow-hidden rounded-md border border-slate-300 bg-white">
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-2.5">
        <div className="flex items-center gap-2">
          <Activity size={13} className="text-blue-600" />
          <span className="text-sm font-bold text-slate-900">Live Activity Stream</span>
          <span className="text-xxs text-slate-500">WebSocket and polling</span>
        </div>
        <div className="flex items-center gap-2">
          <div className={clsx('flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xxs font-bold', connected ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-slate-200 bg-slate-50 text-slate-500')}>
            <span className={clsx('h-1.5 w-1.5 rounded-full', connected ? 'bg-emerald-500' : 'bg-slate-400')} />
            {connected ? 'LIVE' : 'OFFLINE'}
          </div>
          <button
            onClick={clearMessages}
            className="flex h-6 w-6 items-center justify-center rounded text-slate-500 hover:bg-slate-100 hover:text-slate-900"
            title="Clear stream"
          >
            <Trash2 size={11} />
          </button>
        </div>
      </div>

      <div
        className="h-52 space-y-1 overflow-y-auto p-3 font-mono text-xxs"
        onScroll={(event) => {
          const element = event.currentTarget;
          setAutoScroll(element.scrollTop + element.clientHeight >= element.scrollHeight - 20);
        }}
      >
        {messages.length === 0 ? (
          <p className="italic text-slate-500">Waiting for agent events.</p>
        ) : (
          messages.map((message, index) => {
            const tag = stageTag(message);
            return (
              <div key={`${message._ts}-${index}`} className="flex items-start gap-2 leading-relaxed">
                <span className="flex-shrink-0 text-slate-400">{fmtTime(new Date(message._ts).toISOString())}</span>
                {tag && (
                  <span className="flex-shrink-0 rounded border border-blue-200 bg-blue-50 px-1.5 py-0.5 text-blue-700">
                    {tag}
                  </span>
                )}
                {message.status && (
                  <span className={clsx('font-bold', statusColor(message.status))}>{message.status}</span>
                )}
                {message.type === 'snapshot' && (
                  <span className="text-slate-600">Pipeline snapshot - {message.stages?.length ?? 0} stages</span>
                )}
                {message.type === 'stage_update' && (
                  <span className="text-slate-700">Stage update received</span>
                )}
                {message.type !== 'stage_update' && message.type !== 'snapshot' && message.type !== 'pong' && (
                  <span className="text-slate-500">{message.type || 'event'}: {JSON.stringify(message).slice(0, 90)}</span>
                )}
              </div>
            );
          })
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
