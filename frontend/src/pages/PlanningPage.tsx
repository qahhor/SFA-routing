import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { format, startOfWeek, addDays } from 'date-fns'
import { agentsApi, planningApi } from '../services/api'
import RouteMap from '../components/Map/RouteMap'
import type { WeeklyPlan, DailyPlan } from '../types'

export default function PlanningPage() {
  const [selectedAgentId, setSelectedAgentId] = useState('')
  const [weekStart, setWeekStart] = useState(() => {
    const today = new Date()
    const monday = startOfWeek(today, { weekStartsOn: 1 })
    return format(monday, 'yyyy-MM-dd')
  })
  const [selectedDay, setSelectedDay] = useState<DailyPlan | null>(null)
  const [weeklyPlan, setWeeklyPlan] = useState<WeeklyPlan | null>(null)

  const { data: agents } = useQuery({
    queryKey: ['agents-list'],
    queryFn: () => agentsApi.list({ size: 100, is_active: true }),
  })

  const generatePlanMutation = useMutation({
    mutationFn: planningApi.generateWeeklyPlan,
    onSuccess: (data) => {
      setWeeklyPlan(data)
      if (data.daily_plans.length > 0) {
        setSelectedDay(data.daily_plans[0])
      }
    },
  })

  const { isLoading: isLoadingPlan } = useQuery({
    queryKey: ['weekly-plan', selectedAgentId, weekStart],
    queryFn: () => planningApi.getWeeklyPlan(selectedAgentId, weekStart),
    enabled: !!selectedAgentId,
    onSuccess: (data) => {
      setWeeklyPlan(data)
      if (data.daily_plans.length > 0) {
        setSelectedDay(data.daily_plans[0])
      }
    },
    onError: () => {
      setWeeklyPlan(null)
      setSelectedDay(null)
    },
  })

  const handleGeneratePlan = () => {
    if (!selectedAgentId) return
    generatePlanMutation.mutate({
      agent_id: selectedAgentId,
      week_start_date: weekStart,
      week_number: 1,
    })
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Weekly Planning</h1>

      {/* Controls */}
      <div className="bg-white rounded-lg shadow p-4 flex flex-wrap gap-4 items-end">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Agent</label>
          <select
            value={selectedAgentId}
            onChange={(e) => setSelectedAgentId(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 min-w-[200px]"
          >
            <option value="">Select Agent</option>
            {agents?.items.map((agent) => (
              <option key={agent.id} value={agent.id}>{agent.name}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Week Start (Monday)</label>
          <input
            type="date"
            value={weekStart}
            onChange={(e) => setWeekStart(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
          />
        </div>
        <button
          onClick={handleGeneratePlan}
          disabled={!selectedAgentId || generatePlanMutation.isPending}
          className="px-6 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
        >
          {generatePlanMutation.isPending ? 'Generating...' : 'Generate Plan'}
        </button>
      </div>

      {/* Plan Display */}
      {weeklyPlan && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Day tabs and visits list */}
          <div className="lg:col-span-1 space-y-4">
            {/* Summary */}
            <div className="bg-white rounded-lg shadow p-4">
              <h3 className="font-semibold text-gray-900 mb-2">Week Summary</h3>
              <div className="space-y-1 text-sm">
                <p>Total Visits: <span className="font-medium">{weeklyPlan.total_visits}</span></p>
                <p>Total Distance: <span className="font-medium">{weeklyPlan.total_distance_km.toFixed(1)} km</span></p>
                <p>Total Duration: <span className="font-medium">{Math.round(weeklyPlan.total_duration_minutes / 60)} hours</span></p>
              </div>
            </div>

            {/* Day tabs */}
            <div className="bg-white rounded-lg shadow">
              <div className="flex border-b">
                {weeklyPlan.daily_plans.map((day, idx) => (
                  <button
                    key={day.date}
                    onClick={() => setSelectedDay(day)}
                    className={`flex-1 px-3 py-2 text-sm font-medium ${
                      selectedDay?.date === day.date
                        ? 'border-b-2 border-primary-600 text-primary-600'
                        : 'text-gray-500 hover:text-gray-700'
                    }`}
                  >
                    {day.day_of_week.slice(0, 3)}
                    <br />
                    <span className="text-xs">{day.total_visits}</span>
                  </button>
                ))}
              </div>

              {/* Visits list */}
              {selectedDay && (
                <div className="p-4 max-h-[400px] overflow-y-auto">
                  <div className="flex justify-between items-center mb-3">
                    <h4 className="font-medium">{selectedDay.day_of_week}</h4>
                    <span className="text-sm text-gray-500">
                      {selectedDay.total_distance_km.toFixed(1)} km
                    </span>
                  </div>
                  <div className="space-y-2">
                    {selectedDay.visits.map((visit, idx) => (
                      <div
                        key={`${visit.client_id}-${idx}`}
                        className="p-3 bg-gray-50 rounded-lg"
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex items-center space-x-2">
                            <span className="w-6 h-6 flex items-center justify-center bg-primary-600 text-white text-xs rounded-full">
                              {visit.sequence_number}
                            </span>
                            <div>
                              <p className="font-medium text-sm">{visit.client_name}</p>
                              <p className="text-xs text-gray-500">{visit.estimated_arrival}</p>
                            </div>
                          </div>
                          <span className="text-xs text-gray-400">
                            {visit.distance_from_previous_km.toFixed(1)} km
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Map */}
          <div className="lg:col-span-2 bg-white rounded-lg shadow overflow-hidden" style={{ height: '600px' }}>
            {selectedDay && (
              <RouteMap
                visits={selectedDay.visits}
                agentLocation={
                  agents?.items.find(a => a.id === selectedAgentId)
                    ? {
                        lat: agents.items.find(a => a.id === selectedAgentId)!.start_latitude,
                        lng: agents.items.find(a => a.id === selectedAgentId)!.start_longitude,
                      }
                    : undefined
                }
              />
            )}
          </div>
        </div>
      )}

      {/* Empty state */}
      {!weeklyPlan && !isLoadingPlan && (
        <div className="bg-white rounded-lg shadow p-12 text-center">
          <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
          <h3 className="mt-4 text-lg font-medium text-gray-900">No plan generated</h3>
          <p className="mt-2 text-gray-500">Select an agent and week, then click "Generate Plan" to create a weekly visiting plan.</p>
        </div>
      )}
    </div>
  )
}
