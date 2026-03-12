const colors: Record<string, string> = {
  active: 'bg-green-100 text-green-800',
  completed: 'bg-blue-100 text-blue-800',
  escalated: 'bg-red-100 text-red-800',
  scheduled: 'bg-yellow-100 text-yellow-800',
  cancelled: 'bg-gray-100 text-gray-600',
  pending: 'bg-orange-100 text-orange-800',
  approved: 'bg-emerald-100 text-emerald-800',
  uploaded: 'bg-purple-100 text-purple-800',
  analyzed: 'bg-indigo-100 text-indigo-800',
  draft: 'bg-gray-100 text-gray-600',
  archived: 'bg-gray-200 text-gray-500',
};

export default function StatusBadge({ status }: { status: string }) {
  const cls = colors[status] || 'bg-gray-100 text-gray-800';
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${cls}`}>
      {status}
    </span>
  );
}
