"use client";
import React, { useEffect, useState } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';

const API = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';
const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws';

type Health = { status: string; service: string };

type BetsResponse = { count: number };

export default function DashboardPage() {
  const [health, setHealth] = useState<Health | null>(null);
  const [betsCount, setBetsCount] = useState<number>(0);

  // WebSocket connection for real-time updates
  const { isConnected, opportunities, metrics } = useWebSocket(WS_URL);

  useEffect(() => {
    fetch(`${API}/health`)
      .then((r) => r.json())
      .then(setHealth)
      .catch(() => setHealth(null));

    fetch(`${API}/bets`)
      .then((r) => r.json())
      .then((d: BetsResponse) => setBetsCount(d?.count || 0))
      .catch(() => setBetsCount(0));
  }, []);

  return (
    <main className="space-y-6">
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <a href="/market" className="rounded-md border border-red-800 bg-red-900/20 p-4 hover:bg-red-900/30">
          <div className="text-sm text-red-400">🔴 Live Market</div>
          <div className="mt-2 text-2xl font-semibold text-red-400">Real-Time</div>
        </a>
        <a href="/analytics" className="rounded-md border border-blue-800 bg-blue-900/20 p-4 hover:bg-blue-900/30">
          <div className="text-sm text-blue-400">📊 Analytics</div>
          <div className="mt-2 text-2xl font-semibold text-blue-400">Dashboard</div>
        </a>
        <a href="/bets" className="rounded-md border border-neutral-800 p-4 hover:bg-neutral-900">
          <div className="text-sm text-neutral-400">Bets</div>
          <div className="mt-2 text-2xl font-semibold">{betsCount}</div>
        </a>
        <a href="/arbitrage" className="rounded-md border border-green-800 bg-green-900/20 p-4 hover:bg-green-900/30">
          <div className="text-sm text-green-400">Arbitrage</div>
          <div className="mt-2 text-2xl font-semibold text-green-400">Find</div>
        </a>
      </section>

      {/* NEW: Market Intelligence Feature */}
      <section className="grid grid-cols-1 gap-4">
        <a href="/market-intelligence" className="rounded-md border border-yellow-600 bg-gradient-to-r from-yellow-900/30 to-orange-900/30 p-6 hover:from-yellow-900/40 hover:to-orange-900/40 transition">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm text-yellow-400 mb-1">🔥 NEW FEATURE</div>
              <div className="text-2xl font-bold text-yellow-300 mb-2">Market Intelligence Dashboard</div>
              <p className="text-gray-300 text-sm">
                Real-time AI-powered betting insights fusing ML predictions, sentiment analysis, and arbitrage opportunities
              </p>
            </div>
            <div className="text-6xl">🎯</div>
          </div>
        </a>
      </section>

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <a href="/social-signals" className="rounded-md border border-purple-800 bg-purple-900/20 p-4 hover:bg-purple-900/30">
          <div className="text-sm text-purple-400">🤖 Social Signals</div>
          <div className="mt-2 text-2xl font-semibold text-purple-400">ML Powered</div>
        </a>
        <a href="/strategy" className="rounded-md border border-neutral-800 p-4 hover:bg-neutral-900">
          <div className="text-sm text-neutral-400">Strategy</div>
          <div className="mt-2 text-2xl font-semibold">View</div>
        </a>
        <a href="/health" className="rounded-md border border-neutral-800 p-4 hover:bg-neutral-900">
          <div className="text-sm text-neutral-400">System Health</div>
          <div className="mt-2 text-2xl font-semibold">{health?.status || '—'}</div>
        </a>
        <a href="/metrics" className="rounded-md border border-neutral-800 p-4 hover:bg-neutral-900">
          <div className="text-sm text-neutral-400">Metrics</div>
          <div className="mt-2 text-2xl font-semibold">View</div>
        </a>
      </section>

      <section className="rounded-md border border-neutral-800 p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Live Metrics</h2>
          <a href={`${API}/metrics`} className="text-sm text-blue-400 hover:underline">Open Prometheus</a>
        </div>
        <p className="text-sm text-neutral-400">Prometheus endpoint is exposed at /metrics.</p>
      </section>

      {/* Real-Time Status Indicator */}
      <section className="fixed bottom-4 right-4 z-50">
        <div className={`flex items-center gap-2 rounded-full px-4 py-2 shadow-lg ${isConnected ? 'bg-green-900/80 text-green-300' : 'bg-red-900/80 text-red-300'}`}>
          <div className={`h-2 w-2 rounded-full ${isConnected ? 'bg-green-400 animate-pulse' : 'bg-red-400'}`}></div>
          <span className="text-sm font-medium">{isConnected ? 'Live' : 'Offline'}</span>
        </div>
      </section>

      {/* Real-Time Opportunities */}
      {opportunities && opportunities.length > 0 && (
        <section className="rounded-lg border border-yellow-600 bg-gradient-to-r from-yellow-900/20 to-orange-900/20 p-6">
          <h2 className="text-xl font-bold text-yellow-400 mb-4">🔥 Live Value Bets</h2>
          <div className="space-y-3">
            {opportunities.map((opp: any, idx: number) => (
              <div key={idx} className="rounded-md bg-black/30 p-4 border border-yellow-700/50">
                <div className="flex justify-between items-start">
                  <div>
                    <div className="font-semibold text-white">{opp.home} vs {opp.away}</div>
                    <div className="text-sm text-yellow-400 mt-1">👉 BET: {opp.selection?.toUpperCase()}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-lg font-bold text-green-400">${opp.stake?.toFixed(2)}</div>
                    <div className="text-sm text-neutral-400">@ {opp.odds?.toFixed(2)}</div>
                  </div>
                </div>
                <div className="mt-3 flex gap-4 text-sm">
                  <span className="text-neutral-300">Prob: {(opp.p * 100)?.toFixed(1)}%</span>
                  <span className="text-green-400">EV: +{opp.ev?.toFixed(2)}</span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Real-Time Metrics */}
      {metrics && Object.keys(metrics).length > 0 && (
        <section className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="rounded-md border border-blue-700 bg-blue-900/20 p-4">
            <div className="text-sm text-blue-400">Bankroll</div>
            <div className="mt-2 text-2xl font-semibold text-blue-300">${metrics.bankroll?.toFixed(2) || '0.00'}</div>
          </div>
          <div className="rounded-md border border-purple-700 bg-purple-900/20 p-4">
            <div className="text-sm text-purple-400">Open Bets</div>
            <div className="mt-2 text-2xl font-semibold text-purple-300">{metrics.open_bets || 0}</div>
          </div>
          <div className={`rounded-md border p-4 ${(metrics.daily_pnl || 0) >= 0 ? 'border-green-700 bg-green-900/20' : 'border-red-700 bg-red-900/20'}`}>
            <div className={`text-sm ${(metrics.daily_pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>Daily P&L</div>
            <div className={`mt-2 text-2xl font-semibold ${(metrics.daily_pnl || 0) >= 0 ? 'text-green-300' : 'text-red-300'}`}>
              {(metrics.daily_pnl || 0) >= 0 ? '+' : ''}${metrics.daily_pnl?.toFixed(2) || '0.00'}
            </div>
          </div>
        </section>
      )}
    </main>
  );
}
