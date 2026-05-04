import { create } from 'zustand';

export const useNotificationStore = create((set) => ({
  notifications: [],
  add: (n) =>
    set((s) => ({
      notifications: [...s.notifications, { ...n, id: Date.now() + Math.random() }],
    })),
  remove: (id) =>
    set((s) => ({ notifications: s.notifications.filter((n) => n.id !== id) })),
}));
