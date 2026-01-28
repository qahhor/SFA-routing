// Agent types
export interface Agent {
  id: string
  external_id: string
  name: string
  phone?: string
  email?: string
  start_latitude: number
  start_longitude: number
  end_latitude?: number
  end_longitude?: number
  work_start: string
  work_end: string
  max_visits_per_day: number
  is_active: boolean
  clients_count?: number
  created_at: string
  updated_at: string
}

// Client types
export type ClientCategory = 'A' | 'B' | 'C'

export interface Client {
  id: string
  external_id: string
  name: string
  address: string
  phone?: string
  contact_person?: string
  latitude: number
  longitude: number
  category: ClientCategory
  visit_duration_minutes: number
  time_window_start: string
  time_window_end: string
  agent_id?: string
  agent_name?: string
  priority: number
  is_active: boolean
  created_at: string
  updated_at: string
}

// Vehicle types
export interface Vehicle {
  id: string
  name: string
  license_plate: string
  capacity_kg: number
  capacity_volume_m3?: number
  start_latitude: number
  start_longitude: number
  end_latitude?: number
  end_longitude?: number
  work_start: string
  work_end: string
  cost_per_km?: number
  fixed_cost?: number
  driver_name?: string
  driver_phone?: string
  is_active: boolean
  created_at: string
  updated_at: string
}

// Planning types
export type VisitStatus = 'planned' | 'in_progress' | 'completed' | 'skipped' | 'cancelled'

export interface PlannedVisit {
  client_id: string
  client_name: string
  client_address?: string
  sequence_number: number
  planned_time: string
  estimated_arrival: string
  estimated_departure: string
  distance_from_previous_km: number
  duration_from_previous_minutes: number
  latitude: number
  longitude: number
}

export interface DailyPlan {
  date: string
  day_of_week: string
  visits: PlannedVisit[]
  total_visits: number
  total_distance_km: number
  total_duration_minutes: number
  geometry?: GeoJSON.LineString
}

export interface WeeklyPlan {
  agent_id: string
  agent_name: string
  week_start: string
  week_end: string
  daily_plans: DailyPlan[]
  total_visits: number
  total_distance_km: number
  total_duration_minutes: number
  generated_at: string
}

// Delivery types
export type OrderStatus = 'pending' | 'assigned' | 'in_transit' | 'delivered' | 'failed' | 'cancelled'
export type RouteStatus = 'draft' | 'planned' | 'in_progress' | 'completed' | 'cancelled'

export interface DeliveryOrder {
  id: string
  external_id: string
  client_id: string
  client_name?: string
  client_address?: string
  weight_kg: number
  volume_m3?: number
  items_count?: number
  time_window_start: string
  time_window_end: string
  service_time_minutes: number
  priority: number
  status: OrderStatus
  notes?: string
  delivery_instructions?: string
  delivered_at?: string
  failure_reason?: string
  created_at: string
  updated_at: string
}

export interface DeliveryRouteStop {
  id: string
  order_id: string
  order_external_id?: string
  client_id: string
  client_name: string
  client_address: string
  sequence_number: number
  distance_from_previous_km: number
  duration_from_previous_minutes: number
  planned_arrival: string
  planned_departure: string
  actual_arrival?: string
  actual_departure?: string
  latitude: number
  longitude: number
  weight_kg: number
}

export interface DeliveryRoute {
  id: string
  vehicle_id: string
  vehicle_name: string
  vehicle_license_plate: string
  route_date: string
  total_distance_km: number
  total_duration_minutes: number
  total_weight_kg: number
  total_stops: number
  status: RouteStatus
  planned_start?: string
  planned_end?: string
  actual_start?: string
  actual_end?: string
  stops: DeliveryRouteStop[]
  geometry?: object
  notes?: string
  created_at: string
  updated_at: string
}

// API response types
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  size: number
}
