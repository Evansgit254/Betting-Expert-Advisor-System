"use client";
import React, { useEffect, useState } from 'react';

const API = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

type Fixture = {
  id: string;
  home_team: string;
  away_team: string;
  commence_time: string;
  sentiment?: any;
};

type Suggestion = {
  id: number;
  market_id: string;
  selection: string;
  stake: number;
  odds: number;
  strategy_name: string;
};

export default function ManualBettingPage() {
  const [fixtures, setFixtures] = useState<Fixture[]>([]);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedFixture, setSelectedFixture] = useState<Fixture | null>(null);
  const [betForm, setBetForm] = useState({
    selection: 'home',
    stake: 10,
    odds: 2.0,
    is_virtual: true,
    notes: '',
  });
  const [betResult, setBetResult] = useState<any>(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [fixturesRes, suggestionsRes] = await Promise.all([
        fetch(`${API}/ui/fixtures`),
        fetch(`${API}/ui/suggestions`),
      ]);
      
      const fixturesData = await fixturesRes.json();
      const suggestionsData = await suggestionsRes.json();
      
      setFixtures(fixturesData.items || []);
      setSuggestions(suggestionsData.items || []);
    } catch (error) {
      console.error('Failed to fetch data:', error);
    } finally {
      setLoading(false);
    }
  };

  const placeBet = async () => {
    if (!selectedFixture) return;
    
    try {
      const response = await fetch(`${API}/ui/manual_bet`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          market_id: selectedFixture.id,
          selection: betForm.selection,
          stake: betForm.stake,
          odds: betForm.odds,
          is_virtual: betForm.is_virtual,
          notes: betForm.notes,
        }),
      });
      
      const result = await response.json();
      setBetResult(result);
      
      if (result.success) {
        // Reset form
        setBetForm({
          selection: 'home',
          stake: 10,
          odds: 2.0,
          is_virtual: true,
          notes: '',
        });
        setSelectedFixture(null);
        
        // Refresh data
        setTimeout(() => {
          fetchData();
          setBetResult(null);
        }, 3000);
      }
    } catch (error) {
      console.error('Failed to place bet:', error);
      setBetResult({ success: false, error: 'Network error' });
    }
  };

  const getSentimentColor = (sentiment: any) => {
    if (!sentiment) return 'text-neutral-400';
    const label = sentiment.label;
    if (label === 'positive') return 'text-green-400';
    if (label === 'negative') return 'text-red-400';
    return 'text-neutral-400';
  };

  return (
    <main className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold">Manual Betting</h2>
        <button
          onClick={fetchData}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm hover:bg-blue-700"
        >
          Refresh
        </button>
      </div>

      {/* Bet Result Alert */}
      {betResult && (
        <div className={`rounded-md p-4 ${betResult.success ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'}`}>
          {betResult.success ? '✅ ' : '❌ '}
          {betResult.message || betResult.error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Fixtures List */}
        <div className="lg:col-span-2 space-y-4">
          <h3 className="text-lg font-semibold">Upcoming Fixtures</h3>
          
          {loading ? (
            <div className="rounded-md border border-neutral-800 p-8 text-center text-neutral-400">
              Loading fixtures...
            </div>
          ) : fixtures.length === 0 ? (
            <div className="rounded-md border border-neutral-800 p-8 text-center text-neutral-400">
              No fixtures available
            </div>
          ) : (
            fixtures.map((fixture) => (
              <div
                key={fixture.id}
                className={`rounded-md border p-4 cursor-pointer transition-colors ${
                  selectedFixture?.id === fixture.id
                    ? 'border-blue-500 bg-blue-900/20'
                    : 'border-neutral-800 hover:bg-neutral-900'
                }`}
                onClick={() => setSelectedFixture(fixture)}
              >
                <div className="flex items-center justify-between">
                  <div>
                    <div className="font-medium">{fixture.home_team} vs {fixture.away_team}</div>
                    <div className="text-sm text-neutral-400">
                      {new Date(fixture.commence_time).toLocaleString()}
                    </div>
                  </div>
                  
                  {fixture.sentiment && (
                    <div className="text-sm">
                      <div className={getSentimentColor(fixture.sentiment[fixture.home_team])}>
                        {fixture.home_team}: {fixture.sentiment[fixture.home_team]?.label || 'N/A'}
                      </div>
                      <div className={getSentimentColor(fixture.sentiment[fixture.away_team])}>
                        {fixture.away_team}: {fixture.sentiment[fixture.away_team]?.label || 'N/A'}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Bet Form */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold">Place Bet</h3>
          
          <div className="rounded-md border border-neutral-800 bg-neutral-900/50 p-4 space-y-4">
            {selectedFixture ? (
              <>
                <div>
                  <div className="text-sm text-neutral-400">Selected Match</div>
                  <div className="font-medium">
                    {selectedFixture.home_team} vs {selectedFixture.away_team}
                  </div>
                </div>

                <div>
                  <label className="block text-sm text-neutral-400 mb-1">Selection</label>
                  <select
                    value={betForm.selection}
                    onChange={(e) => setBetForm({ ...betForm, selection: e.target.value })}
                    className="w-full rounded-md border border-neutral-800 bg-neutral-900 px-3 py-2"
                  >
                    <option value="home">{selectedFixture.home_team}</option>
                    <option value="away">{selectedFixture.away_team}</option>
                    <option value="draw">Draw</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm text-neutral-400 mb-1">Odds</label>
                  <input
                    type="number"
                    step="0.01"
                    value={betForm.odds}
                    onChange={(e) => setBetForm({ ...betForm, odds: parseFloat(e.target.value) })}
                    className="w-full rounded-md border border-neutral-800 bg-neutral-900 px-3 py-2"
                  />
                </div>

                <div>
                  <label className="block text-sm text-neutral-400 mb-1">Stake ($)</label>
                  <input
                    type="number"
                    step="1"
                    value={betForm.stake}
                    onChange={(e) => setBetForm({ ...betForm, stake: parseFloat(e.target.value) })}
                    className="w-full rounded-md border border-neutral-800 bg-neutral-900 px-3 py-2"
                  />
                </div>

                <div>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={betForm.is_virtual}
                      onChange={(e) => setBetForm({ ...betForm, is_virtual: e.target.checked })}
                      className="rounded"
                    />
                    <span className="text-sm">Virtual Bet (Paper Trading)</span>
                  </label>
                </div>

                <div>
                  <label className="block text-sm text-neutral-400 mb-1">Notes (Optional)</label>
                  <textarea
                    value={betForm.notes}
                    onChange={(e) => setBetForm({ ...betForm, notes: e.target.value })}
                    className="w-full rounded-md border border-neutral-800 bg-neutral-900 px-3 py-2"
                    rows={2}
                  />
                </div>

                <div className="rounded-md bg-neutral-800 p-3">
                  <div className="text-sm text-neutral-400">Potential Return</div>
                  <div className="text-xl font-semibold text-green-400">
                    ${(betForm.stake * betForm.odds).toFixed(2)}
                  </div>
                  <div className="text-sm text-neutral-400">
                    Profit: ${(betForm.stake * (betForm.odds - 1)).toFixed(2)}
                  </div>
                </div>

                <button
                  onClick={placeBet}
                  className={`w-full rounded-md px-4 py-2 font-medium ${
                    betForm.is_virtual
                      ? 'bg-yellow-600 hover:bg-yellow-700'
                      : 'bg-red-600 hover:bg-red-700'
                  }`}
                >
                  {betForm.is_virtual ? 'Place Virtual Bet' : '⚠️ Place LIVE Bet'}
                </button>
              </>
            ) : (
              <div className="text-center text-neutral-400 py-8">
                Select a fixture to place a bet
              </div>
            )}
          </div>

          {/* AI Suggestions */}
          <div className="rounded-md border border-neutral-800 bg-neutral-900/50 p-4">
            <h4 className="font-semibold mb-3">AI Suggestions</h4>
            {suggestions.length === 0 ? (
              <div className="text-sm text-neutral-400">No suggestions available</div>
            ) : (
              <div className="space-y-2">
                {suggestions.slice(0, 5).map((sug) => (
                  <div key={sug.id} className="text-sm border-b border-neutral-800 pb-2">
                    <div className="font-medium">{sug.selection}</div>
                    <div className="text-neutral-400">
                      ${sug.stake} @ {sug.odds} ({sug.strategy_name})
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
