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
  bookmakers?: any[];
};

export default function FixturesPage() {
  const [fixtures, setFixtures] = useState<Fixture[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');

  useEffect(() => {
    fetchFixtures();
  }, []);

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

  const leagues = Array.from(new Set(fixtures.map(f => f.sport_title)));
  const filteredFixtures = filter === 'all' 
    ? fixtures 
    : fixtures.filter(f => f.sport_title === filter);

  return (
    <main className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold">Upcoming Fixtures</h2>
        <div className="flex gap-2">
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="rounded-md border border-neutral-800 bg-neutral-900 px-3 py-2 text-sm"
          >
            <option value="all">All Leagues</option>
            {leagues.map(league => (
              <option key={league} value={league}>{league}</option>
            ))}
          </select>
          <button
            onClick={fetchFixtures}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm hover:bg-blue-700"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="rounded-md border border-neutral-800 p-4">
          <div className="text-sm text-neutral-400">Total Fixtures</div>
          <div className="mt-2 text-2xl font-semibold">{fixtures.length}</div>
        </div>
        <div className="rounded-md border border-neutral-800 p-4">
          <div className="text-sm text-neutral-400">Leagues</div>
          <div className="mt-2 text-2xl font-semibold">{leagues.length}</div>
        </div>
        <div className="rounded-md border border-neutral-800 p-4">
          <div className="text-sm text-neutral-400">Today</div>
          <div className="mt-2 text-2xl font-semibold">
            {fixtures.filter(f => {
              const date = new Date(f.commence_time);
              const today = new Date();
              return date.toDateString() === today.toDateString();
            }).length}
          </div>
        </div>
        <div className="rounded-md border border-neutral-800 p-4">
          <div className="text-sm text-neutral-400">This Week</div>
          <div className="mt-2 text-2xl font-semibold">
            {fixtures.filter(f => {
              const date = new Date(f.commence_time);
              const weekFromNow = new Date();
              weekFromNow.setDate(weekFromNow.getDate() + 7);
              return date <= weekFromNow;
            }).length}
          </div>
        </div>
      </div>

      {/* Fixtures List */}
      {loading ? (
        <div className="rounded-md border border-neutral-800 p-8 text-center text-neutral-400">
          Loading fixtures...
        </div>
      ) : filteredFixtures.length === 0 ? (
        <div className="rounded-md border border-neutral-800 p-8 text-center text-neutral-400">
          No fixtures found
        </div>
      ) : (
        <div className="space-y-3">
          {filteredFixtures.map((fixture) => (
            <div key={fixture.id} className="rounded-md border border-neutral-800 bg-neutral-900/50 p-4">
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <div className="mb-1 text-xs text-neutral-500">{fixture.sport_title}</div>
                  <div className="flex items-center gap-3">
                    <div className="font-medium">{fixture.home_team}</div>
                    <div className="text-neutral-500">vs</div>
                    <div className="font-medium">{fixture.away_team}</div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-sm font-medium text-blue-400">
                    {formatDate(fixture.commence_time)}
                  </div>
                  <div className="text-xs text-neutral-500">
                    {new Date(fixture.commence_time).toLocaleString()}
                  </div>
                </div>
              </div>
              {fixture.bookmakers && fixture.bookmakers.length > 0 && (
                <div className="mt-2 text-xs text-neutral-500">
                  {fixture.bookmakers.length} bookmaker{fixture.bookmakers.length !== 1 ? 's' : ''} available
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
