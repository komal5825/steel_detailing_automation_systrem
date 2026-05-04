import { create } from 'zustand';

export const useWsStore = create((set) => ({
  connected: false,
  messages: [],
  setConnected: (v) => set({ connected: v }),
  addMessage: (msg) =>
    set((state) => ({
      messages: [...state.messages.slice(-299), { ...msg, _ts: Date.now() }],
    })),
  clearMessages: () => set({ messages: [] }),
}));
