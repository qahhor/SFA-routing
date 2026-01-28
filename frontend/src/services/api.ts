import axios from 'axios'
import type {
  Agent,
  Client,
  Vehicle,
  WeeklyPlan,
  DeliveryOrder,
  DeliveryRoute,
  PaginatedResponse,
} from '../types'

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Agents API
export const agentsApi = {
  list: async (params?: {
    page?: number
    size?: number
    is_active?: boolean
    search?: string
  }): Promise<PaginatedResponse<Agent>> => {
    const { data } = await api.get('/agents', { params })
    return data
  },

  get: async (id: string): Promise<Agent> => {
    const { data } = await api.get(`/agents/${id}`)
    return data
  },

  create: async (agent: Omit<Agent, 'id' | 'created_at' | 'updated_at'>): Promise<Agent> => {
    const { data } = await api.post('/agents', agent)
    return data
  },

  update: async (id: string, agent: Partial<Agent>): Promise<Agent> => {
    const { data } = await api.put(`/agents/${id}`, agent)
    return data
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/agents/${id}`)
  },
}

// Clients API
export const clientsApi = {
  list: async (params?: {
    page?: number
    size?: number
    agent_id?: string
    category?: string
    is_active?: boolean
    search?: string
  }): Promise<PaginatedResponse<Client>> => {
    const { data } = await api.get('/clients', { params })
    return data
  },

  get: async (id: string): Promise<Client> => {
    const { data } = await api.get(`/clients/${id}`)
    return data
  },

  create: async (client: Omit<Client, 'id' | 'created_at' | 'updated_at'>): Promise<Client> => {
    const { data } = await api.post('/clients', client)
    return data
  },

  update: async (id: string, client: Partial<Client>): Promise<Client> => {
    const { data } = await api.put(`/clients/${id}`, client)
    return data
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/clients/${id}`)
  },

  assignToAgent: async (clientId: string, agentId: string): Promise<Client> => {
    const { data } = await api.post(`/clients/${clientId}/assign/${agentId}`)
    return data
  },
}

// Vehicles API
export const vehiclesApi = {
  list: async (params?: {
    page?: number
    size?: number
    is_active?: boolean
    search?: string
  }): Promise<PaginatedResponse<Vehicle>> => {
    const { data } = await api.get('/vehicles', { params })
    return data
  },

  get: async (id: string): Promise<Vehicle> => {
    const { data } = await api.get(`/vehicles/${id}`)
    return data
  },

  create: async (vehicle: Omit<Vehicle, 'id' | 'created_at' | 'updated_at'>): Promise<Vehicle> => {
    const { data } = await api.post('/vehicles', vehicle)
    return data
  },

  update: async (id: string, vehicle: Partial<Vehicle>): Promise<Vehicle> => {
    const { data } = await api.put(`/vehicles/${id}`, vehicle)
    return data
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/vehicles/${id}`)
  },
}

// Planning API
export const planningApi = {
  generateWeeklyPlan: async (params: {
    agent_id: string
    week_start_date: string
    week_number?: number
  }): Promise<WeeklyPlan> => {
    const { data } = await api.post('/planning/weekly', params)
    return data
  },

  getWeeklyPlan: async (agentId: string, weekDate: string): Promise<WeeklyPlan> => {
    const { data } = await api.get(`/planning/agent/${agentId}/week/${weekDate}`)
    return data
  },

  getDailyVisits: async (agentId: string, date: string) => {
    const { data } = await api.get(`/planning/agent/${agentId}/day/${date}`)
    return data
  },

  updateVisit: async (visitId: string, update: {
    status?: string
    actual_arrival_time?: string
    actual_departure_time?: string
    notes?: string
    skip_reason?: string
  }) => {
    const { data } = await api.put(`/planning/visit/${visitId}`, update)
    return data
  },
}

// Delivery API
export const deliveryApi = {
  createOrder: async (order: Omit<DeliveryOrder, 'id' | 'status' | 'created_at' | 'updated_at'>): Promise<DeliveryOrder> => {
    const { data } = await api.post('/delivery/orders', order)
    return data
  },

  listOrders: async (params?: {
    status?: string
    client_id?: string
    date_from?: string
    date_to?: string
    limit?: number
  }): Promise<DeliveryOrder[]> => {
    const { data } = await api.get('/delivery/orders', { params })
    return data
  },

  optimizeRoutes: async (params: {
    order_ids: string[]
    vehicle_ids: string[]
    route_date: string
  }): Promise<{
    routes: DeliveryRoute[]
    unassigned_orders: string[]
    total_distance_km: number
    total_duration_minutes: number
    total_vehicles_used: number
    summary: object
    optimized_at: string
  }> => {
    const { data } = await api.post('/delivery/optimize', params)
    return data
  },

  listRoutes: async (params: {
    route_date: string
    vehicle_id?: string
    status?: string
  }): Promise<{
    items: DeliveryRoute[]
    total: number
    date: string
  }> => {
    const { data } = await api.get('/delivery/routes', { params })
    return data
  },

  getRoute: async (routeId: string): Promise<DeliveryRoute> => {
    const { data } = await api.get(`/delivery/route/${routeId}`)
    return data
  },
}

// Health API
export const healthApi = {
  check: async (): Promise<{ status: string }> => {
    const { data } = await api.get('/health')
    return data
  },

  detailed: async (): Promise<{
    status: string
    checks: Record<string, string>
  }> => {
    const { data } = await api.get('/health/detailed')
    return data
  },
}

export default api
