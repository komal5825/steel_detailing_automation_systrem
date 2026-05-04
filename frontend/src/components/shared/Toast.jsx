import React, { useEffect } from 'react';
import { CheckCircle, XCircle, AlertTriangle, Info, X } from 'lucide-react';
import { clsx } from 'clsx';
import { useNotificationStore } from '../../store/notificationStore';

const ICONS = {
  success: <CheckCircle size={14} className="text-green-400" />,
  error:   <XCircle    size={14} className="text-red-400" />,
  warning: <AlertTriangle size={14} className="text-yellow-400" />,
  info:    <Info       size={14} className="text-blue-400" />,
};

function ToastItem({ id, type = 'info', text }) {
  const remove = useNotificationStore((s) => s.remove);
  useEffect(() => {
    const t = setTimeout(() => remove(id), 4500);
    return () => clearTimeout(t);
  }, [id]);
  return (
    <div className="flex items-start gap-2.5 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2.5 shadow-lg min-w-64 max-w-80 animate-slide-in">
      <span className="mt-0.5 flex-shrink-0">{ICONS[type]}</span>
      <p className="text-xs text-slate-200 flex-1">{text}</p>
      <button onClick={() => remove(id)} className="text-slate-500 hover:text-white flex-shrink-0">
        <X size={12} />
      </button>
    </div>
  );
}

export default function ToastContainer() {
  const notifications = useNotificationStore((s) => s.notifications);
  if (!notifications.length) return null;
  return (
    <div className="fixed bottom-4 right-4 flex flex-col gap-2 z-50">
      {notifications.map((n) => <ToastItem key={n.id} {...n} />)}
    </div>
  );
}
