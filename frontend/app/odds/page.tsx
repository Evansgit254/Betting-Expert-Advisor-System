"use client";
import React, { useEffect, useState } from 'react';

const API = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

type Fixture = {
  id: string;
  sport_key: string;
  sport_title: string;
  commence_time: string;
  home_team: string;
  away_team: string;
  bookmakers?: Array<{
    key: string;
    title: string;
    markets: Array<{
      key: string;
      outcomes: Array<{
        name: string;
        price: number;
      }>;
    }>;
  }>;
};

export default function OddsPage() {
  const [fixtures, setFixtures] = useState<Fixture[]>([]);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(false);

  useEffect(() => {
    fetchFixtures();
    
    if (autoRefresh) {
      const interval = setInterval(fetchFixtures, 30000); // Refresh every 30s
      return () => clearInterval(interval);
    }
  }, [autoRefresh]);

  const fetchFixtures = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API}/fixtures`);
      const data = await response.json();
      setFixtures(data.items || []);
    } catch (error) {
      console.error('Failed to fetch fixtures:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = date.getTime() - now.getTime();
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffHours / 24);

    if (diffDays > 0) {
      return `in ${diffDays}d ${diffHours % 24}h`;
    } else if (diffHours > 0) {
      return `in ${diffHours}h`;
    } else {
      return 'Soon';
    }
  };

  const getBestOdds = (fixture: Fixture, outcome: string) => {
    if (!fixture.bookmakers || fixture.bookmakers.length === 0) return null;
    
    let bestOdds = 0;
    let bestBookmaker = '';
    
    fixture.bookmakers.forEach(bookmaker => {
      bookmaker.markets.forEach(market => {
        if (market.key === 'h2h') {
          market.outcomes.forEach(o => {
            if (o.name === outcome && o.price > bestOdds) {
              bestOdds = o.price;
              bestBookmaker = bookmaker.title;
            }
          });
        }
      });
    });
    
    return bestOdds > 0 ? { odds: bestOdds, bookmaker: bestBookmaker } : null;
  };

  return (
    <main className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold">Live Odds</h2>
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
            onClick={fetchFixtures}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm hover:bg-blue-700"
          >
            Refresh Now
          </button>
        </div>
      </div>

      {loading && fixtures.length === 0 ? (
        <div className="rounded-md border border-neutral-800 p-8 text-center text-neutral-400">
          Loading fixtures...
        </div>
      ) : fixtures.length === 0 ? (
        <div className="rounded-md border border-neutral-800 p-8 text-center text-neutral-400">
          No fixtures available
        </div>
      ) : (
        <div className="space-y-4">
          {fixtures.map((fixture) => {
            const homeOdds = getBestOdds(fixture, fixture.home_team);
            const awayOdds = getBestOdds(fixture, fixture.away_team);
            const drawOdds = getBestOdds(fixture, 'Draw');

            return (
              <div key={fixture.id} className="rounded-md border border-neutral-800 bg-neutral-900/50 p-4">
                <div className="mb-3 flex items-center justify-between">
                  <div>
                    <div className="text-xs text-neutral-500">{fixture.sport_title}</div>
                    <div className="text-sm text-neutral-400">{formatDate(fixture.commence_time)}</div>
                  </div>
                  <div className="text-xs text-neutral-500">
                    {new Date(fixture.commence_time).toLocaleString()}
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-4">
                  {/* Home Team */}
                  <div className="rounded-md border border-neutral-800 p-3">
                    <div className="mb-2 font-medium">{fixture.home_team}</div>
                    {homeOdds ? (
                      <>
                        <div className="text-2xl font-bold text-blue-400">{homeOdds.odds.toFixed(2)}</div>
                        <div className="text-xs text-neutral-500">{homeOdds.bookmaker}</div>
                      </>
                    ) : (
                      <div className="text-sm text-neutral-500">No odds</div>
                    )}
                  </div>

                  {/* Draw */}
                  <div className="rounded-md border border-neutral-800 p-3">
                    <div className="mb-2 font-medium text-center">Draw</div>
                    {drawOdds ? (
                      <>
                        <div className="text-2xl font-bold text-center text-neutral-400">{drawOdds.odds.toFixed(2)}</div>
                        <div className="text-xs text-center text-neutral-500">{drawOdds.bookmaker}</div>
                      </>
                    ) : (
                      <div className="text-sm text-center text-neutral-500">No odds</div>
                    )}
                  </div>

                  {/* Away Team */}
                  <div className="rounded-md border border-neutral-800 p-3">
                    <div className="mb-2 font-medium">{fixture.away_team}</div>
                    {awayOdds ? (
                      <>
                        <div className="text-2xl font-bold text-blue-400">{awayOdds.odds.toFixed(2)}</div>
                        <div className="text-xs text-neutral-500">{awayOdds.bookmaker}</div>
                      </>
                    ) : (
                      <div className="text-sm text-neutral-500">No odds</div>
                    )}
                  </div>
                </div>

                {fixture.bookmakers && fixture.bookmakers.length > 0 && (
                  <div className="mt-3 text-xs text-neutral-500">
                    {fixture.bookmakers.length} bookmaker{fixture.bookmakers.length !== 1 ? 's' : ''} available
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </main>
  );
}
