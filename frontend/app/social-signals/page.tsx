'use client';

import { useEffect, useState } from 'react';
import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Suggestion {
  match_id: string;
  home_team: string;
  away_team: string;
  suggested_selection: string;
  suggested_odds: number;
  sentiment_score: number;
  confidence: number;
  sample_count: number;
  reason: string;
  created_at: string;
}

interface ArbitrageOpportunity {
  match_id: string;
  home_team: string;
  away_team: string;
  profit_margin: number;
  commission_adjusted_profit: number;
  total_stake: number;
  legs: Array<{
    bookmaker: string;
    selection: string;
    odds: number;
    stake: number;
  }>;
}

export default function SocialSignalsPage() {
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [arbitrage, setArbitrage] = useState<ArbitrageOpportunity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'suggestions' | 'arbitrage'>('suggestions');
  const [minConfidence, setMinConfidence] = useState(0.5);

  useEffect(() => {
    fetchData();
    // Refresh every 5 minutes
    const interval = setInterval(fetchData, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [minConfidence]);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const [suggestionsRes, arbitrageRes] = await Promise.all([
        axios.get(`${API_BASE_URL}/social/suggestions`, {
          params: { limit: 20, min_confidence: minConfidence }
        }),
        axios.get(`${API_BASE_URL}/social/arbitrage`)
      ]);

      setSuggestions(suggestionsRes.data.suggestions || []);
      setArbitrage(arbitrageRes.data.opportunities || []);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to fetch data');
    } finally {
      setLoading(false);
    }
  };

  const getSentimentColor = (score: number) => {
    if (score > 0.3) return 'text-green-400';
    if (score < -0.3) return 'text-red-400';
    return 'text-gray-400';
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.7) return 'bg-green-600 text-white';
    if (confidence >= 0.5) return 'bg-yellow-600 text-white';
    return 'bg-gray-600 text-white';
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">Social Signals & Sentiment Analysis</h1>
        <p className="text-gray-600">
          AI-powered betting suggestions based on social media sentiment and arbitrage opportunities
        </p>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 mb-6">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab('suggestions')}
            className={`py-4 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'suggestions'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Betting Suggestions
            {suggestions.length > 0 && (
              <span className="ml-2 bg-blue-100 text-blue-600 py-0.5 px-2 rounded-full text-xs">
                {suggestions.length}
              </span>
            )}
          </button>
          <button
            onClick={() => setActiveTab('arbitrage')}
            className={`py-4 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'arbitrage'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Arbitrage Opportunities
            {arbitrage.length > 0 && (
              <span className="ml-2 bg-green-100 text-green-600 py-0.5 px-2 rounded-full text-xs">
                {arbitrage.length}
              </span>
            )}
          </button>
        </nav>
      </div>

      {/* Controls */}
      {activeTab === 'suggestions' && (
        <div className="mb-6 flex items-center space-x-4">
          <label className="text-sm font-medium text-gray-700">
            Min Confidence:
          </label>
          <input
            type="range"
            min="0"
            max="1"
            step="0.1"
            value={minConfidence}
            onChange={(e) => setMinConfidence(parseFloat(e.target.value))}
            className="w-48"
          />
          <span className="text-sm text-gray-600">{(minConfidence * 100).toFixed(0)}%</span>
          <button
            onClick={fetchData}
            className="ml-auto px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          >
            Refresh
          </button>
        </div>
      )}

      {/* Loading State */}
      {loading && (
        <div className="text-center py-12">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
          <p className="mt-2 text-gray-600">Loading...</p>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
          <p className="text-red-800">
            <strong>Error:</strong> {error}
          </p>
          <p className="text-sm text-red-600 mt-2">
            Make sure the backend is running and ENABLE_SOCIAL_SIGNALS=True in your .env file
          </p>
        </div>
      )}

      {/* Suggestions Tab */}
      {!loading && activeTab === 'suggestions' && (
        <div className="space-y-4">
          {suggestions.length === 0 ? (
            <div className="text-center py-12 bg-gray-50 rounded-lg">
              <p className="text-gray-600">No suggestions available</p>
              <p className="text-sm text-gray-500 mt-2">
                Try lowering the confidence threshold or check if social signals are enabled
              </p>
            </div>
          ) : (
            suggestions.map((suggestion, idx) => (
              <div key={idx} className="bg-gray-800 border border-gray-600 rounded-lg p-6 hover:shadow-xl hover:border-gray-500 transition-all">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h3 className="text-lg font-semibold text-white">
                      {suggestion.home_team} vs {suggestion.away_team}
                    </h3>
                    <p className="text-sm text-gray-400">Match ID: {suggestion.match_id}</p>
                  </div>
                  <span className={`px-3 py-1 rounded-full text-sm font-medium ${getConfidenceColor(suggestion.confidence)}`}>
                    {(suggestion.confidence * 100).toFixed(0)}% confidence
                  </span>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                  <div>
                    <p className="text-sm text-gray-400">Suggested Bet</p>
                    <p className="text-lg font-semibold text-white capitalize">{suggestion.suggested_selection}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-400">Odds</p>
                    <p className="text-lg font-semibold text-white">{suggestion.suggested_odds.toFixed(2)}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-400">Sentiment</p>
                    <p className={`text-lg font-semibold ${getSentimentColor(suggestion.sentiment_score)}`}>
                      {suggestion.sentiment_score > 0 ? '+' : ''}{suggestion.sentiment_score.toFixed(2)}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-400">Sample Size</p>
                    <p className="text-lg font-semibold text-white">{suggestion.sample_count} posts</p>
                  </div>
                </div>

                <div className="bg-gray-900 rounded p-3 border border-gray-700">
                  <p className="text-sm text-gray-300">
                    <strong className="text-white">Reason:</strong> {suggestion.reason}
                  </p>
                </div>

                <div className="mt-4 flex space-x-2">
                  <button className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm font-medium">
                    View Details
                  </button>
                  <button className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 text-sm font-medium">
                    Place Bet
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Arbitrage Tab */}
      {!loading && activeTab === 'arbitrage' && (
        <div className="space-y-4">
          {arbitrage.length === 0 ? (
            <div className="text-center py-12 bg-gray-50 rounded-lg">
              <p className="text-gray-600">No arbitrage opportunities found</p>
              <p className="text-sm text-gray-500 mt-2">
                Arbitrage opportunities are rare and time-sensitive
              </p>
            </div>
          ) : (
            arbitrage.map((opp, idx) => (
              <div key={idx} className="bg-gray-800 border-2 border-green-600 rounded-lg p-6 hover:shadow-xl hover:border-green-500 transition-all">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h3 className="text-lg font-semibold text-white">
                      {opp.home_team} vs {opp.away_team}
                    </h3>
                    <p className="text-sm text-gray-400">Match ID: {opp.match_id}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-2xl font-bold text-green-400">
                      +{opp.profit_margin.toFixed(2)}%
                    </p>
                    <p className="text-xs text-gray-400">
                      ({opp.commission_adjusted_profit.toFixed(2)}% after fees)
                    </p>
                  </div>
                </div>

                <div className="mb-4">
                  <p className="text-sm text-gray-400 mb-2">Required Stakes (Total: ${opp.total_stake.toFixed(2)})</p>
                  <div className="space-y-2">
                    {opp.legs.map((leg, legIdx) => (
                      <div key={legIdx} className="flex items-center justify-between bg-gray-900 border border-gray-700 rounded p-3">
                        <div>
                          <p className="font-medium text-white">{leg.bookmaker}</p>
                          <p className="text-sm text-gray-400 capitalize">{leg.selection} @ {leg.odds.toFixed(2)}</p>
                        </div>
                        <p className="text-lg font-semibold text-white">${leg.stake.toFixed(2)}</p>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="bg-green-900 bg-opacity-30 border border-green-600 rounded p-3 mb-4">
                  <p className="text-sm text-green-300">
                    <strong className="text-green-200">Guaranteed Profit:</strong> ${(opp.total_stake * opp.commission_adjusted_profit / 100).toFixed(2)}
                  </p>
                </div>

                <button className="w-full px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 font-medium transition-colors">
                  Execute Arbitrage
                </button>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
