import React from 'react';
import { Bell, Wifi, WifiOff } from 'lucide-react';
import { clsx } from 'clsx';
import { useWsStore } from '../../store/wsStore';

export default function TopBar({ title, subtitle, actions }) {
  const connected = useWsStore((state) => state.connected);

  return (
    <header className="sticky top-0 z-30 flex h-12 items-center justify-between border-b border-slate-200 bg-white px-6">
      <div className="flex items-center gap-3">
        {title && (
          <>
            <h1 className="text-sm font-bold text-slate-950">{title}</h1>
            {subtitle && <span className="font-mono text-xs text-slate-500">{subtitle}</span>}
          </>
        )}
      </div>
      <div className="flex items-center gap-4">
        {actions}
        <div className={clsx('flex items-center gap-1.5 rounded-full border px-2 py-1 text-xxs font-bold', connected ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-slate-200 bg-slate-50 text-slate-500')}>
          {connected ? <Wifi size={12} /> : <WifiOff size={12} />}
          <span>{connected ? 'ENGINE ONLINE' : 'OFFLINE'}</span>
        </div>
        <button className="flex h-8 w-8 items-center justify-center rounded-md border border-slate-300 bg-white text-slate-500 hover:border-slate-400 hover:text-slate-900">
          <Bell size={13} />
        </button>
      </div>
    </header>
  );
}
