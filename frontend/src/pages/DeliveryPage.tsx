import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { format } from 'date-fns'
import { deliveryApi, vehiclesApi } from '../services/api'
import RouteMap from '../components/Map/RouteMap'
import type { DeliveryRoute } from '../types'

export default function DeliveryPage() {
  const [routeDate, setRouteDate] = useState(() => format(new Date(), 'yyyy-MM-dd'))
  const [selectedRoute, setSelectedRoute] = useState<DeliveryRoute | null>(null)

  const { data: vehicles } = useQuery({
    queryKey: ['vehicles-list'],
    queryFn: () => vehiclesApi.list({ size: 100, is_active: true }),
  })

  const { data: orders } = useQuery({
    queryKey: ['pending-orders'],
    queryFn: () => deliveryApi.listOrders({ status: 'pending', limit: 100 }),
  })

  const { data: routes, refetch: refetchRoutes } = useQuery({
    queryKey: ['delivery-routes', routeDate],
    queryFn: () => deliveryApi.listRoutes({ route_date: routeDate }),
  })

  const optimizeMutation = useMutation({
    mutationFn: deliveryApi.optimizeRoutes,
    onSuccess: () => {
      refetchRoutes()
    },
  })

  const handleOptimize = () => {
    if (!orders?.length || !vehicles?.items.length) return

    optimizeMutation.mutate({
      order_ids: orders.map(o => o.id),
      vehicle_ids: vehicles.items.map(v => v.id),
      route_date: routeDate,
    })
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Delivery Optimization</h1>

      {/* Controls */}
      <div className="bg-white rounded-lg shadow p-4 flex flex-wrap gap-4 items-end">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Delivery Date</label>
          <input
            type="date"
            value={routeDate}
            onChange={(e) => setRouteDate(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
          />
        </div>
        <div className="flex items-center space-x-4">
          <span className="text-sm text-gray-600">
            {orders?.length || 0} pending orders
          </span>
          <span className="text-sm text-gray-600">
            {vehicles?.items.length || 0} available vehicles
          </span>
        </div>
        <button
          onClick={handleOptimize}
          disabled={!orders?.length || !vehicles?.items.length || optimizeMutation.isPending}
          className="px-6 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
        >
          {optimizeMutation.isPending ? 'Optimizing...' : 'Optimize Routes'}
        </button>
      </div>

      {/* Routes display */}
      {routes && routes.items.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Routes list */}
          <div className="lg:col-span-1 space-y-4">
            <div className="bg-white rounded-lg shadow p-4">
              <h3 className="font-semibold text-gray-900 mb-3">Optimized Routes</h3>
              <div className="space-y-2">
                {routes.items.map((route) => (
                  <button
                    key={route.id}
                    onClick={() => setSelectedRoute(route)}
                    className={`w-full p-3 rounded-lg text-left transition-colors ${
                      selectedRoute?.id === route.id
                        ? 'bg-primary-50 border-2 border-primary-500'
                        : 'bg-gray-50 hover:bg-gray-100'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium text-sm">{route.vehicle_name}</p>
                        <p className="text-xs text-gray-500">{route.vehicle_license_plate}</p>
                      </div>
                      <span className={`px-2 py-1 text-xs rounded-full ${
                        route.status === 'planned' ? 'bg-blue-100 text-blue-800' :
                        route.status === 'in_progress' ? 'bg-yellow-100 text-yellow-800' :
                        route.status === 'completed' ? 'bg-green-100 text-green-800' :
                        'bg-gray-100 text-gray-800'
                      }`}>
                        {route.status}
                      </span>
                    </div>
                    <div className="mt-2 flex justify-between text-xs text-gray-500">
                      <span>{route.total_stops} stops</span>
                      <span>{route.total_distance_km.toFixed(1)} km</span>
                      <span>{route.total_weight_kg.toFixed(0)} kg</span>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* Selected route details */}
            {selectedRoute && (
              <div className="bg-white rounded-lg shadow p-4 max-h-[400px] overflow-y-auto">
                <h4 className="font-semibold text-gray-900 mb-3">Route Stops</h4>
                <div className="space-y-2">
                  {selectedRoute.stops.map((stop) => (
                    <div
                      key={stop.id}
                      className="p-3 bg-gray-50 rounded-lg"
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex items-center space-x-2">
                          <span className="w-6 h-6 flex items-center justify-center bg-primary-600 text-white text-xs rounded-full">
                            {stop.sequence_number}
                          </span>
                          <div>
                            <p className="font-medium text-sm">{stop.client_name}</p>
                            <p className="text-xs text-gray-500">{stop.client_address}</p>
                            <p className="text-xs text-gray-400 mt-1">
                              {format(new Date(stop.planned_arrival), 'HH:mm')} - {stop.weight_kg} kg
                            </p>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Map */}
          <div className="lg:col-span-2 bg-white rounded-lg shadow overflow-hidden" style={{ height: '600px' }}>
            {selectedRoute && (
              <RouteMap
                visits={selectedRoute.stops.map(stop => ({
                  client_id: stop.client_id,
                  client_name: stop.client_name,
                  sequence_number: stop.sequence_number,
                  planned_time: format(new Date(stop.planned_arrival), 'HH:mm'),
                  estimated_arrival: format(new Date(stop.planned_arrival), 'HH:mm'),
                  estimated_departure: format(new Date(stop.planned_departure), 'HH:mm'),
                  distance_from_previous_km: stop.distance_from_previous_km,
                  duration_from_previous_minutes: stop.duration_from_previous_minutes,
                  latitude: stop.latitude,
                  longitude: stop.longitude,
                }))}
              />
            )}
          </div>
        </div>
      )}

      {/* Empty state */}
      {(!routes || routes.items.length === 0) && (
        <div className="bg-white rounded-lg shadow p-12 text-center">
          <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17a2 2 0 11-4 0 2 2 0 014 0zM19 17a2 2 0 11-4 0 2 2 0 014 0z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16V6a1 1 0 00-1-1H4a1 1 0 00-1 1v10a1 1 0 001 1h1m8-1a1 1 0 01-1 1H9m4-1V8a1 1 0 011-1h2.586a1 1 0 01.707.293l3.414 3.414a1 1 0 01.293.707V16a1 1 0 01-1 1h-1m-6-1a1 1 0 001 1h1M5 17a2 2 0 104 0m-4 0a2 2 0 114 0m6 0a2 2 0 104 0m-4 0a2 2 0 114 0" />
          </svg>
          <h3 className="mt-4 text-lg font-medium text-gray-900">No routes for this date</h3>
          <p className="mt-2 text-gray-500">Click "Optimize Routes" to generate optimized delivery routes for pending orders.</p>
        </div>
      )}
    </div>
  )
}
