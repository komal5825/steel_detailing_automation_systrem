import { format, formatDistanceToNow } from 'date-fns';

export function fmtRelative(dateStr) {
  if (!dateStr) return '-';
  try {
    return formatDistanceToNow(new Date(dateStr), { addSuffix: true });
  } catch {
    return dateStr;
  }
}

export function fmtDateTime(dateStr) {
  if (!dateStr) return '-';
  try {
    return format(new Date(dateStr), 'dd MMM yyyy, HH:mm:ss');
  } catch {
    return dateStr;
  }
}

export function fmtTime(dateStr) {
  if (!dateStr) return '-';
  try {
    return format(new Date(dateStr), 'HH:mm:ss');
  } catch {
    return dateStr;
  }
}

export function fmtFileSize(bytes) {
  if (!bytes) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  let size = bytes;
  let index = 0;
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024;
    index += 1;
  }
  return `${size.toFixed(1)} ${units[index]}`;
}

export function fmtDuration(startStr, endStr) {
  if (!startStr || !endStr) return null;
  try {
    const ms = new Date(endStr) - new Date(startStr);
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`;
  } catch {
    return null;
  }
}
