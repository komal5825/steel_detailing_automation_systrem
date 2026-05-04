import React from 'react';
import { clsx } from 'clsx';
import { STATUS_META } from '../../constants/stages';

export default function StatusBadge({ status, size = 'sm' }) {
  const meta = STATUS_META[status] || STATUS_META.PENDING;
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 rounded-full font-medium border',
        size === 'sm' ? 'px-2 py-0.5 text-xxs' : 'px-3 py-1 text-xs',
        meta.color, meta.bg, meta.border
      )}
    >
      <span className={clsx('w-1.5 h-1.5 rounded-full flex-shrink-0', meta.dot)} />
      {meta.label}
    </span>
  );
}
