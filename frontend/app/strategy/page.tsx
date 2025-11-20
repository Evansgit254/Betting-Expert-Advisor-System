"use client";
import React, { useEffect, useState } from 'react';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const API = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

type StrategyPerformance = {
  strategy_name: string;
  period_start: string;
  period_end: string;
  total_bets: number;
  win_count: number;
  loss_count: number;
  void_count: number;
  win_rate: number;
  total_staked: number;
  total_returned: number;
  total_profit_loss: number;
  profit_margin: number;
  max_drawdown: number;
  sharpe_ratio: number | null;
  params: any;
};

export default function StrategyPage() {
  const [performance, setPerformance] = useState<StrategyPerformance[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchPerformance();
  }, []);

  const fetchPerformance = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API}/strategy/performance`);
      const data = await response.json();
      setPerformance(data.items || []);
    } catch (error) {
      console.error('Failed to fetch strategy performance:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
  };

  const chartData = performance.map(p => ({
    period: formatDate(p.period_start),
    winRate: (p.win_rate * 100).toFixed(1),
    profitLoss: p.total_profit_loss,
    profitMargin: (p.profit_margin * 100).toFixed(1),
  }));

  const totalStats = performance.reduce((acc, p) => ({
    totalBets: acc.totalBets + p.total_bets,
    totalWins: acc.totalWins + p.win_count,
    totalLosses: acc.totalLosses + p.loss_count,
    totalStaked: acc.totalStaked + p.total_staked,
    totalPL: acc.totalPL + p.total_profit_loss,
  }), { totalBets: 0, totalWins: 0, totalLosses: 0, totalStaked: 0, totalPL: 0 });

  const overallWinRate = totalStats.totalBets > 0 
    ? (totalStats.totalWins / (totalStats.totalWins + totalStats.totalLosses) * 100).toFixed(1)
    : '0.0';

  const overallROI = totalStats.totalStaked > 0
    ? ((totalStats.totalPL / totalStats.totalStaked) * 100).toFixed(1)
    : '0.0';

  return (
    <main className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold">Strategy Performance</h2>
        <button
          onClick={fetchPerformance}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm hover:bg-blue-700"
        >
          Refresh
        </button>
      </div>

      {/* Overall Stats */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
        <div className="rounded-md border border-neutral-800 p-4">
          <div className="text-sm text-neutral-400">Total Bets</div>
          <div className="mt-2 text-2xl font-semibold">{totalStats.totalBets}</div>
        </div>
        <div className="rounded-md border border-neutral-800 p-4">
          <div className="text-sm text-neutral-400">Win Rate</div>
          <div className="mt-2 text-2xl font-semibold text-blue-400">{overallWinRate}%</div>
        </div>
        <div className="rounded-md border border-neutral-800 p-4">
          <div className="text-sm text-neutral-400">Total Staked</div>
          <div className="mt-2 text-2xl font-semibold">${totalStats.totalStaked.toFixed(2)}</div>
        </div>
        <div className="rounded-md border border-neutral-800 p-4">
          <div className="text-sm text-neutral-400">Total P/L</div>
          <div className={`mt-2 text-2xl font-semibold ${totalStats.totalPL >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            ${totalStats.totalPL.toFixed(2)}
          </div>
        </div>
        <div className="rounded-md border border-neutral-800 p-4">
          <div className="text-sm text-neutral-400">ROI</div>
          <div className={`mt-2 text-2xl font-semibold ${parseFloat(overallROI) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {overallROI}%
          </div>
        </div>
      </div>

      {loading ? (
        <div className="rounded-md border border-neutral-800 p-8 text-center text-neutral-400">
          Loading performance data...
        </div>
      ) : performance.length === 0 ? (
        <div className="rounded-md border border-neutral-800 p-8 text-center text-neutral-400">
          No performance data available
        </div>
      ) : (
        <>
          {/* Charts */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* Win Rate Chart */}
            <div className="rounded-md border border-neutral-800 bg-neutral-900/50 p-4">
              <h3 className="mb-4 text-lg font-semibold">Win Rate Over Time</h3>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#404040" />
                  <XAxis dataKey="period" stroke="#a3a3a3" />
                  <YAxis stroke="#a3a3a3" />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#171717', border: '1px solid #404040' }}
                    labelStyle={{ color: '#a3a3a3' }}
                  />
                  <Legend />
                  <Line type="monotone" dataKey="winRate" stroke="#60a5fa" name="Win Rate (%)" />
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* Profit/Loss Chart */}
            <div className="rounded-md border border-neutral-800 bg-neutral-900/50 p-4">
              <h3 className="mb-4 text-lg font-semibold">Profit/Loss Over Time</h3>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#404040" />
                  <XAxis dataKey="period" stroke="#a3a3a3" />
                  <YAxis stroke="#a3a3a3" />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#171717', border: '1px solid #404040' }}
                    labelStyle={{ color: '#a3a3a3' }}
                  />
                  <Legend />
                  <Bar dataKey="profitLoss" fill="#10b981" name="Profit/Loss ($)" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Performance Table */}
          <div className="rounded-md border border-neutral-800 bg-neutral-900/50">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="border-b border-neutral-800">
                  <tr className="text-left text-sm text-neutral-400">
                    <th className="p-4">Strategy</th>
                    <th className="p-4">Period</th>
                    <th className="p-4">Bets</th>
                    <th className="p-4">W/L/V</th>
                    <th className="p-4">Win Rate</th>
                    <th className="p-4">Staked</th>
                    <th className="p-4">P/L</th>
                    <th className="p-4">ROI</th>
                    <th className="p-4">Sharpe</th>
                  </tr>
                </thead>
                <tbody>
                  {performance.map((perf, idx) => (
                    <tr key={idx} className="border-b border-neutral-800 hover:bg-neutral-900">
                      <td className="p-4 font-medium">{perf.strategy_name}</td>
                      <td className="p-4 text-sm text-neutral-400">
                        {formatDate(perf.period_start)} - {formatDate(perf.period_end)}
                      </td>
                      <td className="p-4">{perf.total_bets}</td>
                      <td className="p-4 text-sm">
                        <span className="text-green-400">{perf.win_count}</span>
                        {' / '}
                        <span className="text-red-400">{perf.loss_count}</span>
                        {' / '}
                        <span className="text-yellow-400">{perf.void_count}</span>
                      </td>
                      <td className="p-4 font-medium text-blue-400">
                        {(perf.win_rate * 100).toFixed(1)}%
                      </td>
                      <td className="p-4">${perf.total_staked.toFixed(2)}</td>
                      <td className={`p-4 font-medium ${perf.total_profit_loss >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        ${perf.total_profit_loss.toFixed(2)}
                      </td>
                      <td className={`p-4 font-medium ${perf.profit_margin >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {(perf.profit_margin * 100).toFixed(1)}%
                      </td>
                      <td className="p-4 text-neutral-400">
                        {perf.sharpe_ratio !== null ? perf.sharpe_ratio.toFixed(2) : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </main>
  );
}
