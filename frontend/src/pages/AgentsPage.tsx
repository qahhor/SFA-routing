import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { agentsApi } from '../services/api'
import type { Agent } from '../types'

export default function AgentsPage() {
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [showForm, setShowForm] = useState(false)
  const [editingAgent, setEditingAgent] = useState<Agent | null>(null)
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['agents', { page, search }],
    queryFn: () => agentsApi.list({ page, size: 20, search: search || undefined }),
  })

  const deleteMutation = useMutation({
    mutationFn: agentsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents'] })
    },
  })

  const handleDelete = (id: string) => {
    if (confirm('Are you sure you want to delete this agent?')) {
      deleteMutation.mutate(id)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Agents</h1>
        <button
          onClick={() => {
            setEditingAgent(null)
            setShowForm(true)
          }}
          className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
        >
          Add Agent
        </button>
      </div>

      {/* Search */}
      <div className="bg-white rounded-lg shadow p-4">
        <input
          type="text"
          placeholder="Search agents..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
        />
      </div>

      {/* Table */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">External ID</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Clients</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Work Hours</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {isLoading ? (
              <tr>
                <td colSpan={6} className="px-6 py-4 text-center">Loading...</td>
              </tr>
            ) : data?.items.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-6 py-4 text-center text-gray-500">No agents found</td>
              </tr>
            ) : (
              data?.items.map((agent) => (
                <tr key={agent.id}>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div>
                      <div className="text-sm font-medium text-gray-900">{agent.name}</div>
                      <div className="text-sm text-gray-500">{agent.email}</div>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{agent.external_id}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{agent.clients_count || 0}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {agent.work_start} - {agent.work_end}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`px-2 py-1 text-xs rounded-full ${agent.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'}`}>
                      {agent.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                    <button
                      onClick={() => {
                        setEditingAgent(agent)
                        setShowForm(true)
                      }}
                      className="text-primary-600 hover:text-primary-900 mr-4"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => handleDelete(agent.id)}
                      className="text-red-600 hover:text-red-900"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>

        {/* Pagination */}
        {data && data.total > 20 && (
          <div className="px-6 py-4 flex items-center justify-between border-t border-gray-200">
            <div className="text-sm text-gray-500">
              Showing {(page - 1) * 20 + 1} to {Math.min(page * 20, data.total)} of {data.total} results
            </div>
            <div className="flex space-x-2">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-3 py-1 border rounded-md disabled:opacity-50"
              >
                Previous
              </button>
              <button
                onClick={() => setPage(p => p + 1)}
                disabled={page * 20 >= data.total}
                className="px-3 py-1 border rounded-md disabled:opacity-50"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Form Modal */}
      {showForm && (
        <AgentForm
          agent={editingAgent}
          onClose={() => {
            setShowForm(false)
            setEditingAgent(null)
          }}
        />
      )}
    </div>
  )
}

interface AgentFormProps {
  agent: Agent | null
  onClose: () => void
}

function AgentForm({ agent, onClose }: AgentFormProps) {
  const queryClient = useQueryClient()
  const [formData, setFormData] = useState({
    external_id: agent?.external_id || '',
    name: agent?.name || '',
    phone: agent?.phone || '',
    email: agent?.email || '',
    start_latitude: agent?.start_latitude?.toString() || '41.311081',
    start_longitude: agent?.start_longitude?.toString() || '69.279737',
    work_start: agent?.work_start || '09:00',
    work_end: agent?.work_end || '18:00',
    max_visits_per_day: agent?.max_visits_per_day || 30,
    is_active: agent?.is_active ?? true,
  })

  const createMutation = useMutation({
    mutationFn: agentsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents'] })
      onClose()
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<Agent> }) =>
      agentsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents'] })
      onClose()
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const data = {
      ...formData,
      start_latitude: parseFloat(formData.start_latitude),
      start_longitude: parseFloat(formData.start_longitude),
    }

    if (agent) {
      updateMutation.mutate({ id: agent.id, data })
    } else {
      createMutation.mutate(data as any)
    }
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <h2 className="text-xl font-bold mb-4">
            {agent ? 'Edit Agent' : 'Add Agent'}
          </h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">External ID</label>
              <input
                type="text"
                value={formData.external_id}
                onChange={(e) => setFormData({ ...formData, external_id: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
                required
                disabled={!!agent}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
                required
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Phone</label>
                <input
                  type="text"
                  value={formData.phone}
                  onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                <input
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Start Latitude</label>
                <input
                  type="number"
                  step="0.000001"
                  value={formData.start_latitude}
                  onChange={(e) => setFormData({ ...formData, start_latitude: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Start Longitude</label>
                <input
                  type="number"
                  step="0.000001"
                  value={formData.start_longitude}
                  onChange={(e) => setFormData({ ...formData, start_longitude: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
                  required
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Work Start</label>
                <input
                  type="time"
                  value={formData.work_start}
                  onChange={(e) => setFormData({ ...formData, work_start: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Work End</label>
                <input
                  type="time"
                  value={formData.work_end}
                  onChange={(e) => setFormData({ ...formData, work_end: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
                  required
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Max Visits Per Day</label>
              <input
                type="number"
                min="1"
                max="100"
                value={formData.max_visits_per_day}
                onChange={(e) => setFormData({ ...formData, max_visits_per_day: parseInt(e.target.value) })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
                required
              />
            </div>
            <div className="flex items-center">
              <input
                type="checkbox"
                checked={formData.is_active}
                onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
              />
              <label className="ml-2 block text-sm text-gray-900">Active</label>
            </div>
            <div className="flex justify-end space-x-3 pt-4">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
              >
                {agent ? 'Update' : 'Create'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}
