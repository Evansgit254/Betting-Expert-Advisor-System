"use client";
import React, { useEffect, useState } from 'react';

const API = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

type Bet = {
  id: number;
  market_id: string;
  selection: string;
  stake: number;
  odds: number;
  result: string;
  profit_loss: number | null;
  placed_at: string;
  settled_at: string | null;
  is_dry_run: boolean;
  strategy_name: string | null;
};

export default function BetsPage() {
  const [bets, setBets] = useState<Bet[]>([]);
  const [loading, setLoading] = useState(true);
  const [limit, setLimit] = useState(50);

  useEffect(() => {
    fetchBets();
  }, [limit]);

  const fetchBets = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API}/bets?limit=${limit}`);
      const data = await response.json();
      setBets(data.items || []);
    } catch (error) {
      console.error('Failed to fetch bets:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  const getResultColor = (result: string) => {
    switch (result) {
      case 'win': return 'text-green-400';
      case 'loss': return 'text-red-400';
      case 'void': return 'text-yellow-400';
      default: return 'text-neutral-400';
    }
  };

  const stats = {
    total: bets.length,
    wins: bets.filter(b => b.result === 'win').length,
    losses: bets.filter(b => b.result === 'loss').length,
    pending: bets.filter(b => b.result === 'pending').length,
    totalStake: bets.reduce((sum, b) => sum + b.stake, 0),
    totalPL: bets.reduce((sum, b) => sum + (b.profit_loss || 0), 0),
  };

  return (
    <main className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold">Bet History</h2>
        <div className="flex gap-2">
          <select
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="rounded-md border border-neutral-800 bg-neutral-900 px-3 py-2 text-sm"
          >
            <option value={10}>Last 10</option>
            <option value={50}>Last 50</option>
            <option value={100}>Last 100</option>
            <option value={200}>Last 200</option>
          </select>
          <button
            onClick={fetchBets}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm hover:bg-blue-700"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        <div className="rounded-md border border-neutral-800 p-4">
          <div className="text-sm text-neutral-400">Total Bets</div>
          <div className="mt-2 text-2xl font-semibold">{stats.total}</div>
        </div>
        <div className="rounded-md border border-neutral-800 p-4">
          <div className="text-sm text-neutral-400">Wins</div>
          <div className="mt-2 text-2xl font-semibold text-green-400">{stats.wins}</div>
        </div>
        <div className="rounded-md border border-neutral-800 p-4">
          <div className="text-sm text-neutral-400">Losses</div>
          <div className="mt-2 text-2xl font-semibold text-red-400">{stats.losses}</div>
        </div>
        <div className="rounded-md border border-neutral-800 p-4">
          <div className="text-sm text-neutral-400">Pending</div>
          <div className="mt-2 text-2xl font-semibold text-yellow-400">{stats.pending}</div>
        </div>
        <div className="rounded-md border border-neutral-800 p-4">
          <div className="text-sm text-neutral-400">Total Stake</div>
          <div className="mt-2 text-2xl font-semibold">${stats.totalStake.toFixed(2)}</div>
        </div>
        <div className="rounded-md border border-neutral-800 p-4">
          <div className="text-sm text-neutral-400">Total P/L</div>
          <div className={`mt-2 text-2xl font-semibold ${stats.totalPL >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            ${stats.totalPL.toFixed(2)}
          </div>
        </div>
      </div>

      {/* Bets Table */}
      <div className="rounded-md border border-neutral-800 bg-neutral-900/50">
        {loading ? (
          <div className="p-8 text-center text-neutral-400">Loading bets...</div>
        ) : bets.length === 0 ? (
          <div className="p-8 text-center text-neutral-400">No bets found</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="border-b border-neutral-800">
                <tr className="text-left text-sm text-neutral-400">
                  <th className="p-4">ID</th>
                  <th className="p-4">Selection</th>
                  <th className="p-4">Stake</th>
                  <th className="p-4">Odds</th>
                  <th className="p-4">Result</th>
                  <th className="p-4">P/L</th>
                  <th className="p-4">Placed</th>
                  <th className="p-4">Mode</th>
                  <th className="p-4">Strategy</th>
                </tr>
              </thead>
              <tbody>
                {bets.map((bet) => (
                  <tr key={bet.id} className="border-b border-neutral-800 hover:bg-neutral-900">
                    <td className="p-4 text-sm">{bet.id}</td>
                    <td className="p-4">
                      <div className="font-medium">{bet.selection}</div>
                      <div className="text-xs text-neutral-500">{bet.market_id}</div>
                    </td>
                    <td className="p-4">${bet.stake.toFixed(2)}</td>
                    <td className="p-4">{bet.odds.toFixed(2)}</td>
                    <td className={`p-4 font-medium ${getResultColor(bet.result)}`}>
                      {bet.result.toUpperCase()}
                    </td>
                    <td className={`p-4 font-medium ${bet.profit_loss && bet.profit_loss >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {bet.profit_loss !== null ? `$${bet.profit_loss.toFixed(2)}` : '—'}
                    </td>
                    <td className="p-4 text-sm text-neutral-400">
                      {formatDate(bet.placed_at)}
                    </td>
                    <td className="p-4">
                      <span className={`rounded px-2 py-1 text-xs ${bet.is_dry_run ? 'bg-yellow-900/30 text-yellow-400' : 'bg-green-900/30 text-green-400'}`}>
                        {bet.is_dry_run ? 'DRY RUN' : 'LIVE'}
                      </span>
                    </td>
                    <td className="p-4 text-sm text-neutral-400">
                      {bet.strategy_name || '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </main>
  );
}
