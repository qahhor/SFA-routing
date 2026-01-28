import { useQuery } from '@tanstack/react-query'
import { healthApi, agentsApi, clientsApi, vehiclesApi } from '../services/api'

export default function Dashboard() {
  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: healthApi.detailed,
    refetchInterval: 30000,
  })

  const { data: agents } = useQuery({
    queryKey: ['agents', { page: 1, size: 5 }],
    queryFn: () => agentsApi.list({ page: 1, size: 5, is_active: true }),
  })

  const { data: clients } = useQuery({
    queryKey: ['clients', { page: 1, size: 5 }],
    queryFn: () => clientsApi.list({ page: 1, size: 5, is_active: true }),
  })

  const { data: vehicles } = useQuery({
    queryKey: ['vehicles', { page: 1, size: 5 }],
    queryFn: () => vehiclesApi.list({ page: 1, size: 5, is_active: true }),
  })

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>

      {/* System Status */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold mb-4">System Status</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {health?.checks &&
            Object.entries(health.checks).map(([service, status]) => (
              <div key={service} className="flex items-center space-x-2">
                <div
                  className={`w-3 h-3 rounded-full ${
                    status === 'healthy' ? 'bg-green-500' : 'bg-red-500'
                  }`}
                />
                <span className="text-sm capitalize">{service}</span>
              </div>
            ))}
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <StatCard
          title="Active Agents"
          value={agents?.total || 0}
          icon={
            <svg className="w-8 h-8 text-primary-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
            </svg>
          }
        />
        <StatCard
          title="Active Clients"
          value={clients?.total || 0}
          icon={
            <svg className="w-8 h-8 text-primary-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
            </svg>
          }
        />
        <StatCard
          title="Active Vehicles"
          value={vehicles?.total || 0}
          icon={
            <svg className="w-8 h-8 text-primary-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17a2 2 0 11-4 0 2 2 0 014 0zM19 17a2 2 0 11-4 0 2 2 0 014 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16V6a1 1 0 00-1-1H4a1 1 0 00-1 1v10a1 1 0 001 1h1m8-1a1 1 0 01-1 1H9m4-1V8a1 1 0 011-1h2.586a1 1 0 01.707.293l3.414 3.414a1 1 0 01.293.707V16a1 1 0 01-1 1h-1m-6-1a1 1 0 001 1h1M5 17a2 2 0 104 0m-4 0a2 2 0 114 0m6 0a2 2 0 104 0m-4 0a2 2 0 114 0" />
            </svg>
          }
        />
      </div>

      {/* Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold mb-4">Recent Agents</h2>
          <div className="space-y-3">
            {agents?.items.map((agent) => (
              <div key={agent.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div>
                  <p className="font-medium">{agent.name}</p>
                  <p className="text-sm text-gray-500">{agent.clients_count || 0} clients</p>
                </div>
                <span className={`px-2 py-1 text-xs rounded-full ${agent.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'}`}>
                  {agent.is_active ? 'Active' : 'Inactive'}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold mb-4">Recent Clients</h2>
          <div className="space-y-3">
            {clients?.items.map((client) => (
              <div key={client.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div>
                  <p className="font-medium">{client.name}</p>
                  <p className="text-sm text-gray-500">Category: {client.category}</p>
                </div>
                <span className={`px-2 py-1 text-xs rounded-full ${
                  client.category === 'A' ? 'bg-green-100 text-green-800' :
                  client.category === 'B' ? 'bg-blue-100 text-blue-800' :
                  'bg-gray-100 text-gray-800'
                }`}>
                  {client.category}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

interface StatCardProps {
  title: string
  value: number
  icon: React.ReactNode
}

function StatCard({ title, value, icon }: StatCardProps) {
  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-500">{title}</p>
          <p className="text-3xl font-bold text-gray-900">{value}</p>
        </div>
        {icon}
      </div>
    </div>
  )
}
