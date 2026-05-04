import { create } from 'zustand';

export const useProjectStore = create((set) => ({
  activeProjectUuid: null,
  projects: [],
  engineerName: 'Engineer',
  setActiveProject: (uuid) => set({ activeProjectUuid: uuid }),
  setProjects: (projects) => set({ projects }),
  setEngineerName: (name) => set({ engineerName: name }),
}));
