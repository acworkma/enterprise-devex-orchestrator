import { useParams, useNavigate } from 'react-router-dom';

export default function DetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  return (
    <div className="space-y-6">
      <button onClick={() => navigate('/')} className="text-blue-600 hover:underline text-sm">&larr; Back</button>
      <div className="bg-white rounded-xl shadow p-6">
        <h1 className="text-xl font-bold">Item Detail</h1>
        <p className="text-sm text-gray-500 mt-2">ID: {id}</p>
      </div>
    </div>
  );
}
