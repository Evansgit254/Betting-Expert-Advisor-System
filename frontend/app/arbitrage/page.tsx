"use client";
import React, { useEffect, useState } from 'react';

const API = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

type ArbitrageOpportunity = {
  id: string;
  market_id: string;
  home_team: string;
  away_team: string;
  sport: string;
  commence_time: string;
  profit_margin: number;
  total_stake: number;
  legs: Array<{
    bookmaker: string;
    selection: string;
    odds: number;
    stake: number;
    expected_return: number;
  }>;
  detected_at: string;
};

export default function ArbitragePage() {
  const [opportunities, setOpportunities] = useState<ArbitrageOpportunity[]>([]);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(false);

  useEffect(() => {
    fetchOpportunities();
    
    if (autoRefresh) {
      const interval = setInterval(fetchOpportunities, 30000); // 30s
      return () => clearInterval(interval);
    }
  }, [autoRefresh]);

  const fetchOpportunities = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API}/arbitrage`);
      const data = await response.json();
      setOpportunities(data.items || []);
    } catch (error) {
      console.error('Failed to fetch arbitrage opportunities:', error);
      setOpportunities([]);
    } finally {
      setLoading(false);
    }
  };

  const formatTime = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    return date.toLocaleDateString();
  };

  const stats = {
    total: opportunities.length,
    avgProfit: opportunities.length > 0
      ? (opportunities.reduce((sum, o) => sum + o.profit_margin, 0) / opportunities.length * 100).toFixed(2)
      : '0.00',
    bestProfit: opportunities.length > 0
      ? (Math.max(...opportunities.map(o => o.profit_margin)) * 100).toFixed(2)
      : '0.00',
    totalStake: opportunities.reduce((sum, o) => sum + o.total_stake, 0).toFixed(2),
  };

  return (
    <main className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold">Arbitrage Opportunities</h2>
        <div className="flex gap-2">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="rounded"
            />
            Auto-refresh (30s)
          </label>
          <button
            onClick={fetchOpportunities}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm hover:bg-blue-700"
          >
            Refresh Now
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="rounded-md border border-neutral-800 p-4">
          <div className="text-sm text-neutral-400">Opportunities</div>
          <div className="mt-2 text-2xl font-semibold text-green-400">{stats.total}</div>
        </div>
        <div className="rounded-md border border-neutral-800 p-4">
          <div className="text-sm text-neutral-400">Avg Profit</div>
          <div className="mt-2 text-2xl font-semibold text-green-400">{stats.avgProfit}%</div>
        </div>
        <div className="rounded-md border border-neutral-800 p-4">
          <div className="text-sm text-neutral-400">Best Profit</div>
          <div className="mt-2 text-2xl font-semibold text-green-400">{stats.bestProfit}%</div>
        </div>
        <div className="rounded-md border border-neutral-800 p-4">
          <div className="text-sm text-neutral-400">Total Stake</div>
          <div className="mt-2 text-2xl font-semibold">${stats.totalStake}</div>
        </div>
      </div>

      {/* Opportunities List */}
      {loading && opportunities.length === 0 ? (
        <div className="rounded-md border border-neutral-800 p-8 text-center text-neutral-400">
          Loading arbitrage opportunities...
        </div>
      ) : opportunities.length === 0 ? (
        <div className="rounded-md border border-neutral-800 p-8 text-center">
          <div className="text-neutral-400 mb-2">No arbitrage opportunities found</div>
          <div className="text-sm text-neutral-500">
            Arbitrage opportunities are rare. Check back later or enable auto-refresh.
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {opportunities.map((opp) => (
            <div key={opp.id} className="rounded-md border border-neutral-800 bg-neutral-900/50 p-4">
              {/* Header */}
              <div className="mb-4 flex items-start justify-between">
                <div>
                  <div className="text-lg font-semibold">
                    {opp.home_team} vs {opp.away_team}
                  </div>
                  <div className="mt-1 flex items-center gap-2 text-sm text-neutral-400">
                    <span>{opp.sport}</span>
                    <span>•</span>
                    <span>{new Date(opp.commence_time).toLocaleString()}</span>
                    <span>•</span>
                    <span className="text-neutral-500">{formatTime(opp.detected_at)}</span>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-2xl font-bold text-green-400">
                    {(opp.profit_margin * 100).toFixed(2)}%
                  </div>
                  <div className="text-sm text-neutral-400">Profit Margin</div>
                </div>
              </div>

              {/* Legs */}
              <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                {opp.legs.map((leg, idx) => (
                  <div key={idx} className="rounded-md border border-neutral-700 bg-neutral-900 p-3">
                    <div className="mb-2 flex items-center justify-between">
                      <div className="text-sm font-medium text-blue-400">{leg.bookmaker}</div>
                      <div className="text-xs text-neutral-500">Leg {idx + 1}</div>
                    </div>
                    <div className="mb-2">
                      <div className="font-medium">{leg.selection}</div>
                      <div className="text-sm text-neutral-400">@ {leg.odds.toFixed(2)}</div>
                    </div>
                    <div className="flex items-center justify-between border-t border-neutral-700 pt-2">
                      <div className="text-sm text-neutral-400">Stake:</div>
                      <div className="font-semibold">${leg.stake.toFixed(2)}</div>
                    </div>
                    <div className="flex items-center justify-between">
                      <div className="text-sm text-neutral-400">Return:</div>
                      <div className="font-semibold text-green-400">
                        ${leg.expected_return.toFixed(2)}
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {/* Summary */}
              <div className="mt-4 flex items-center justify-between rounded-md bg-neutral-800/50 p-3">
                <div className="flex gap-6">
                  <div>
                    <div className="text-sm text-neutral-400">Total Stake</div>
                    <div className="font-semibold">${opp.total_stake.toFixed(2)}</div>
                  </div>
                  <div>
                    <div className="text-sm text-neutral-400">Guaranteed Profit</div>
                    <div className="font-semibold text-green-400">
                      ${(opp.total_stake * opp.profit_margin).toFixed(2)}
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-neutral-400">ROI</div>
                    <div className="font-semibold text-green-400">
                      {(opp.profit_margin * 100).toFixed(2)}%
                    </div>
                  </div>
                </div>
                <button className="rounded-md bg-green-600 px-4 py-2 text-sm font-medium hover:bg-green-700">
                  Execute Arbitrage
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Info Box */}
      <div className="rounded-md border border-blue-800 bg-blue-900/20 p-4">
        <div className="mb-2 flex items-center gap-2">
          <svg className="h-5 w-5 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <div className="font-semibold text-blue-400">About Arbitrage Betting</div>
        </div>
        <div className="text-sm text-neutral-300">
          Arbitrage opportunities occur when different bookmakers offer odds that allow you to bet on all outcomes
          and guarantee a profit regardless of the result. These opportunities are rare and time-sensitive.
          Always verify odds before placing bets as they can change rapidly.
        </div>
      </div>
    </main>
  );
}
