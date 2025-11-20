"use client";
import React, { useEffect, useState } from 'react';

const API = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

type CircuitBreakerStatus = {
  status: string;
  fail_counter: number;
  fail_max: number;
  timeout_duration?: number;
};

type SystemStatus = {
  status: string;
  mode: string;
  circuit_breakers: Record<string, CircuitBreakerStatus>;
  database: {
    status: string;
    error?: string;
  };
  cache: {
    status: string;
  };
};

export default function HealthPage() {
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [health, setHealth] = useState<{ status: string; service: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);

  useEffect(() => {
    fetchStatus();
    
    if (autoRefresh) {
      const interval = setInterval(fetchStatus, 10000); // Refresh every 10s
      return () => clearInterval(interval);
    }
  }, [autoRefresh]);

  const fetchStatus = async () => {
    setLoading(true);
    try {
      const [statusRes, healthRes] = await Promise.all([
        fetch(`${API}/system/status`),
        fetch(`${API}/health`)
      ]);
      
      const statusData = await statusRes.json();
      const healthData = await healthRes.json();
      
      setSystemStatus(statusData);
      setHealth(healthData);
    } catch (error) {
      console.error('Failed to fetch system status:', error);
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'ok':
      case 'operational':
      case 'connected':
      case 'available':
      case 'closed':
        return 'text-green-400';
      case 'half_open':
      case 'warning':
        return 'text-yellow-400';
      case 'open':
      case 'error':
      case 'unavailable':
        return 'text-red-400';
      default:
        return 'text-neutral-400';
    }
  };

  const getStatusBadge = (status: string) => {
    const color = getStatusColor(status);
    const bgColor = color.replace('text-', 'bg-').replace('-400', '-900/30');
    
    return (
      <span className={`rounded px-2 py-1 text-xs font-medium ${color} ${bgColor}`}>
        {status.toUpperCase()}
      </span>
    );
  };

  return (
    <main className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold">System Health</h2>
        <div className="flex gap-2">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="rounded"
            />
            Auto-refresh (10s)
          </label>
          <button
            onClick={fetchStatus}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm hover:bg-blue-700"
          >
            Refresh Now
          </button>
        </div>
      </div>

      {loading && !systemStatus ? (
        <div className="rounded-md border border-neutral-800 p-8 text-center text-neutral-400">
          Loading system status...
        </div>
      ) : (
        <>
          {/* Overall Status */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="rounded-md border border-neutral-800 p-4">
              <div className="text-sm text-neutral-400">API Status</div>
              <div className="mt-2 flex items-center gap-2">
                {health && getStatusBadge(health.status)}
                <span className="text-lg font-semibold">{health?.service}</span>
              </div>
            </div>
            <div className="rounded-md border border-neutral-800 p-4">
              <div className="text-sm text-neutral-400">System Status</div>
              <div className="mt-2">
                {systemStatus && getStatusBadge(systemStatus.status)}
              </div>
            </div>
            <div className="rounded-md border border-neutral-800 p-4">
              <div className="text-sm text-neutral-400">Mode</div>
              <div className="mt-2">
                {systemStatus && (
                  <span className={`rounded px-2 py-1 text-xs font-medium ${
                    systemStatus.mode === 'LIVE' 
                      ? 'bg-red-900/30 text-red-400' 
                      : 'bg-yellow-900/30 text-yellow-400'
                  }`}>
                    {systemStatus.mode}
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Circuit Breakers */}
          {systemStatus?.circuit_breakers && (
            <div className="rounded-md border border-neutral-800 bg-neutral-900/50 p-4">
              <h3 className="mb-4 text-lg font-semibold">Circuit Breakers</h3>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {Object.entries(systemStatus.circuit_breakers).map(([name, cb]) => (
                  <div key={name} className="rounded-md border border-neutral-800 p-4">
                    <div className="mb-2 flex items-center justify-between">
                      <div className="font-medium">{name}</div>
                      {getStatusBadge(cb.status)}
                    </div>
                    <div className="space-y-1 text-sm text-neutral-400">
                      <div>Failures: {cb.fail_counter} / {cb.fail_max}</div>
                      {cb.timeout_duration && (
                        <div>Reset timeout: {cb.timeout_duration}s</div>
                      )}
                    </div>
                    {cb.status === 'open' && (
                      <div className="mt-2 text-xs text-red-400">
                        ⚠️ Service unavailable
                      </div>
                    )}
                    {cb.status === 'half_open' && (
                      <div className="mt-2 text-xs text-yellow-400">
                        🔄 Testing recovery
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Database Status */}
          {systemStatus?.database && (
            <div className="rounded-md border border-neutral-800 bg-neutral-900/50 p-4">
              <h3 className="mb-4 text-lg font-semibold">Database</h3>
              <div className="flex items-center gap-4">
                <div>
                  <div className="text-sm text-neutral-400">Status</div>
                  <div className="mt-1">
                    {getStatusBadge(systemStatus.database.status)}
                  </div>
                </div>
                {systemStatus.database.error && (
                  <div className="flex-1">
                    <div className="text-sm text-neutral-400">Error</div>
                    <div className="mt-1 text-sm text-red-400">
                      {systemStatus.database.error}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Cache Status */}
          {systemStatus?.cache && (
            <div className="rounded-md border border-neutral-800 bg-neutral-900/50 p-4">
              <h3 className="mb-4 text-lg font-semibold">Cache</h3>
              <div className="flex items-center gap-4">
                <div>
                  <div className="text-sm text-neutral-400">Status</div>
                  <div className="mt-1">
                    {getStatusBadge(systemStatus.cache.status)}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Metrics Link */}
          <div className="rounded-md border border-neutral-800 bg-neutral-900/50 p-4">
            <h3 className="mb-2 text-lg font-semibold">Prometheus Metrics</h3>
            <p className="mb-3 text-sm text-neutral-400">
              View detailed system metrics in Prometheus format
            </p>
            <a
              href={`${API}/metrics`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block rounded-md bg-blue-600 px-4 py-2 text-sm hover:bg-blue-700"
            >
              Open Metrics Endpoint
            </a>
          </div>
        </>
      )}
    </main>
  );
}
