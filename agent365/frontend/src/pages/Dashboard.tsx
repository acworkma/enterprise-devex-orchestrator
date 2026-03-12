import { useEffect, useState } from 'react';
import { api } from '../api/client';
import StatusBadge from '../components/StatusBadge';

export default function Dashboard() {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState('');
  const [desc, setDesc] = useState('');

  useEffect(() => {
    api.listItems().then(setItems).finally(() => setLoading(false));
  }, []);

  const handleCreate = async () => {
    if (!name.trim()) return;
    const item = await api.createItem({ name, description: desc });
    setItems(prev => [...prev, item]);
    setName('');
    setDesc('');
  };

  if (loading) return <p className="text-center py-12 text-gray-500">Loading...</p>;

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold">Dashboard</h1>

      <div className="bg-white rounded-xl shadow p-6">
        <h2 className="text-lg font-semibold mb-4">Create Item</h2>
        <div className="flex gap-3">
          <input value={name} onChange={e => setName(e.target.value)} placeholder="Name"
            className="flex-1 border rounded-lg px-3 py-2 text-sm" />
          <input value={desc} onChange={e => setDesc(e.target.value)} placeholder="Description"
            className="flex-1 border rounded-lg px-3 py-2 text-sm" />
          <button onClick={handleCreate}
            className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700">
            Add
          </button>
        </div>
      </div>

      <section>
        <h2 className="text-lg font-semibold mb-3">Items</h2>
        <div className="bg-white rounded-xl shadow overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">ID</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Description</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {items.map(i => (
                <tr key={i.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm font-mono text-gray-500">{i.id.slice(0,8)}</td>
                  <td className="px-4 py-3 text-sm font-medium">{i.name}</td>
                  <td className="px-4 py-3 text-sm text-gray-600">{i.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
