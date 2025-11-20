'use client';

import { useState, useEffect } from 'react';

const API = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

export default function MarketPage() {
  const [headlines, setHeadlines] = useState<any[]>([]);
  const [suggestions, setSuggestions] = useState<any[]>([]);
  const [fixtures, setFixtures] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedLeagues, setSelectedLeagues] = useState<string[]>([]);
  const [minEV, setMinEV] = useState(0.05);
  const [minConfidence, setMinConfidence] = useState(0.6);

  const leagues = [
    { id: 'soccer_epl', name: 'Premier League' },
    { id: 'soccer_spain_la_liga', name: 'La Liga' },
    { id: 'soccer_germany_bundesliga', name: 'Bundesliga' },
    { id: 'soccer_italy_serie_a', name: 'Serie A' },
    { id: 'soccer_france_ligue_one', name: 'Ligue 1' },
    { id: 'soccer_uefa_champs_league', name: 'Champions League' },
  ];

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 60000);
    return () => clearInterval(interval);
  }, [selectedLeagues, minEV, minConfidence]);

  const fetchData = async () => {
    try {
      const leagueParam = selectedLeagues.length > 0 ? `?leagues=${selectedLeagues.join(',')}` : '';
      
      const [headlinesRes, suggestionsRes, fixturesRes] = await Promise.all([
        fetch(`${API}/market/headlines${leagueParam}`),
        fetch(`${API}/market/suggestions?min_confidence=${minConfidence}${leagueParam}`),
        fetch(`${API}/market/fixtures?min_ev=${minEV}&min_confidence=${minConfidence}${leagueParam}`)
      ]);

      const headlinesData = await headlinesRes.json();
      const suggestionsData = await suggestionsRes.json();
      const fixturesData = await fixturesRes.json();

      setHeadlines(headlinesData.headlines || []);
      setSuggestions(suggestionsData.suggestions || []);
      setFixtures(fixturesData.fixtures || []);
    } catch (error) {
      console.error('Error fetching market data:', error);
    } finally {
      setLoading(false);
    }
  };

  const placeBet = async (suggestion: any) => {
    try {
      const response = await fetch(`${API}/market/manual_bet`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          fixture_id: suggestion.fixture_id,
          selection: suggestion.suggested_selection,
          odds: suggestion.suggested_odds,
          stake: 10,
          is_virtual: true
        })
      });

      const data = await response.json();
      if (data.success) {
        alert('Virtual bet placed successfully!');
      }
    } catch (error) {
      console.error('Error placing bet:', error);
      alert('Failed to place bet');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-950 text-white p-6">
        <div className="text-center">Loading market data...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white p-6">
      <h1 className="text-4xl font-bold mb-6">🔴 Live Market Intelligence</h1>

      {/* Headlines Banner */}
      <div className="mb-8">
        <h2 className="text-2xl font-semibold mb-4">📰 Market Headlines</h2>
        <div className="space-y-3">
          {headlines.map((headline, idx) => (
            <div
              key={idx}
              className={`p-4 rounded-lg border ${
                headline.priority === 'critical' ? 'bg-red-900/20 border-red-500' :
                headline.priority === 'high' ? 'bg-yellow-900/20 border-yellow-500' :
                'bg-blue-900/20 border-blue-500'
              }`}
            >
              <div className="flex justify-between items-start">
                <p className="text-lg">{headline.headline}</p>
                <span className="text-sm bg-gray-800 px-2 py-1 rounded">
                  {(headline.confidence * 100).toFixed(0)}% confidence
                </span>
              </div>
              <div className="mt-2 flex gap-2">
                {headline.drivers.map((driver: string, i: number) => (
                  <span key={i} className="text-xs bg-gray-700 px-2 py-1 rounded">
                    {driver}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Filters */}
      <div className="mb-6 p-4 bg-gray-900 rounded-lg">
        <h3 className="text-lg font-semibold mb-3">🔍 Filters</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm mb-2">Min EV: {(minEV * 100).toFixed(0)}%</label>
            <input
              type="range"
              min="0"
              max="0.5"
              step="0.01"
              value={minEV}
              onChange={(e) => setMinEV(parseFloat(e.target.value))}
              className="w-full"
            />
          </div>
          <div>
            <label className="block text-sm mb-2">Min Confidence: {(minConfidence * 100).toFixed(0)}%</label>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={minConfidence}
              onChange={(e) => setMinConfidence(parseFloat(e.target.value))}
              className="w-full"
            />
          </div>
          <div>
            <label className="block text-sm mb-2">Leagues</label>
            <select
              multiple
              value={selectedLeagues}
              onChange={(e) => setSelectedLeagues(Array.from(e.target.selectedOptions, option => option.value))}
              className="w-full bg-gray-800 text-white p-2 rounded"
            >
              {leagues.map(league => (
                <option key={league.id} value={league.id}>{league.name}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Suggestions */}
      <div className="mb-8">
        <h2 className="text-2xl font-semibold mb-4">🎯 ML-Powered Suggestions</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {suggestions.slice(0, 6).map((suggestion, idx) => (
            <div key={idx} className="bg-gray-900 p-4 rounded-lg border border-gray-700">
              <div className="flex justify-between items-start mb-2">
                <div>
                  <h3 className="font-bold">{suggestion.home_team} vs {suggestion.away_team}</h3>
                  <p className="text-sm text-gray-400">{suggestion.league}</p>
                </div>
                <span className="text-xs bg-green-600 px-2 py-1 rounded">
                  EV: +{(suggestion.ev_score * 100).toFixed(1)}%
                </span>
              </div>
              <div className="mb-3">
                <p className="text-lg">
                  <span className="font-bold text-yellow-400">{suggestion.suggested_selection.toUpperCase()}</span>
                  {' @ '}
                  <span className="font-bold">{suggestion.suggested_odds.toFixed(2)}</span>
                </p>
                <p className="text-sm text-gray-300 mt-1">{suggestion.reason}</p>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm">
                  Confidence: {(suggestion.ml_confidence * 100).toFixed(0)}%
                </span>
                <button
                  onClick={() => placeBet(suggestion)}
                  className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded text-sm"
                >
                  Place Virtual Bet
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* All Fixtures */}
      <div>
        <h2 className="text-2xl font-semibold mb-4">📊 All Fixtures ({fixtures.length})</h2>
        <div className="bg-gray-900 rounded-lg overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-800">
              <tr>
                <th className="p-3 text-left">Match</th>
                <th className="p-3 text-left">Prediction</th>
                <th className="p-3 text-left">Odds</th>
                <th className="p-3 text-left">EV</th>
                <th className="p-3 text-left">Confidence</th>
                <th className="p-3 text-left">Risk</th>
              </tr>
            </thead>
            <tbody>
              {fixtures.slice(0, 20).map((fixture, idx) => (
                <tr key={idx} className="border-t border-gray-800">
                  <td className="p-3">
                    <div className="font-medium">{fixture.home_team} vs {fixture.away_team}</div>
                    <div className="text-xs text-gray-400">{fixture.league}</div>
                  </td>
                  <td className="p-3 font-bold text-yellow-400">
                    {fixture.predicted_outcome?.toUpperCase()}
                  </td>
                  <td className="p-3">
                    {fixture.predicted_outcome === 'home' && fixture.home_odds?.toFixed(2)}
                    {fixture.predicted_outcome === 'away' && fixture.away_odds?.toFixed(2)}
                    {fixture.predicted_outcome === 'draw' && fixture.draw_odds?.toFixed(2)}
                  </td>
                  <td className="p-3">
                    <span className={fixture.ev_score > 0.1 ? 'text-green-400' : 'text-gray-400'}>
                      {(fixture.ev_score * 100).toFixed(1)}%
                    </span>
                  </td>
                  <td className="p-3">{(fixture.ml_confidence * 100).toFixed(0)}%</td>
                  <td className="p-3">
                    <span className={`px-2 py-1 rounded text-xs ${
                      fixture.risk_category === 'low' ? 'bg-green-600' :
                      fixture.risk_category === 'medium' ? 'bg-yellow-600' :
                      'bg-red-600'
                    }`}>
                      {fixture.risk_category}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
