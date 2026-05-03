import { create } from 'zustand'

interface OrgState {
  activeOrgId: number | null
  activeOrgNombre: string
  setActiveOrg: (id: number | null, nombre: string) => void
  clearActiveOrg: () => void
}

export const useOrgStore = create<OrgState>((set) => ({
  activeOrgId: null,
  activeOrgNombre: '',
  setActiveOrg: (id, nombre) => set({ activeOrgId: id, activeOrgNombre: nombre }),
  clearActiveOrg: () => set({ activeOrgId: null, activeOrgNombre: '' }),
}))
