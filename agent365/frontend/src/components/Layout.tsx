import { ReactNode } from 'react';
import { Link } from 'react-router-dom';

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-gradient-to-r from-blue-700 to-indigo-800 text-white shadow-lg">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <Link to="/" className="text-xl font-bold tracking-tight hover:opacity-90">
            agent365
          </Link>
          <nav className="flex gap-4 text-sm">
            <Link to="/" className="hover:underline">Dashboard</Link>
          </nav>
        </div>
      </header>
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 py-8">
        {children}
      </main>
      <footer className="bg-gray-100 border-t text-center text-xs text-gray-500 py-3">
        agent365 &mdash; Enterprise DevEx Orchestrator
      </footer>
    </div>
  );
}
