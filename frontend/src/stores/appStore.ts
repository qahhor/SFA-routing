import { create } from 'zustand'
import type { Agent, Client, Vehicle, WeeklyPlan, DeliveryRoute } from '../types'

interface AppState {
  // Selected items
  selectedAgent: Agent | null
  selectedClient: Client | null
  selectedVehicle: Vehicle | null
  selectedPlan: WeeklyPlan | null
  selectedRoute: DeliveryRoute | null

  // UI state
  isLoading: boolean
  error: string | null

  // Actions
  setSelectedAgent: (agent: Agent | null) => void
  setSelectedClient: (client: Client | null) => void
  setSelectedVehicle: (vehicle: Vehicle | null) => void
  setSelectedPlan: (plan: WeeklyPlan | null) => void
  setSelectedRoute: (route: DeliveryRoute | null) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  clearSelections: () => void
}

export const useAppStore = create<AppState>((set) => ({
  // Initial state
  selectedAgent: null,
  selectedClient: null,
  selectedVehicle: null,
  selectedPlan: null,
  selectedRoute: null,
  isLoading: false,
  error: null,

  // Actions
  setSelectedAgent: (agent) => set({ selectedAgent: agent }),
  setSelectedClient: (client) => set({ selectedClient: client }),
  setSelectedVehicle: (vehicle) => set({ selectedVehicle: vehicle }),
  setSelectedPlan: (plan) => set({ selectedPlan: plan }),
  setSelectedRoute: (route) => set({ selectedRoute: route }),
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
  clearSelections: () =>
    set({
      selectedAgent: null,
      selectedClient: null,
      selectedVehicle: null,
      selectedPlan: null,
      selectedRoute: null,
    }),
}))
