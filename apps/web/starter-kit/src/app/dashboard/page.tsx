'use client';

import { useSession } from 'next-auth/react';

export default function Dashboard() {
  const { data: session } = useSession();

  return (
    <div className="flex min-h-screen flex-col items-center justify-center p-8 text-white bg-slate-950">
      <div className="w-full max-w-2xl bg-slate-900 border border-slate-800 rounded-xl p-8 shadow-xl text-center">
        <h1 className="text-3xl font-bold mb-4 text-emerald-400">Sovereign Shard Dashboard</h1>
        <p className="text-slate-300 mb-6">Welcome back to your decentralized coop OS.</p>
        <div className="p-4 bg-slate-800 rounded-lg border border-slate-700 font-mono text-sm inline-block">
          {session?.user?.email || "User Authenticated"}
        </div>
      </div>
    </div>
  );
}
