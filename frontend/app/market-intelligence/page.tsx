'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';

interface Suggestion {
    rank: number;
    market_id: string;
    home: string;
    away: string;
    league: string;
    kickoff: string;
    recommendation: {
        selection: string;
        odds: number;
        ml_probability: number;
        expected_value: number;
        kelly_stake: number;
        confidence: number;
    };
    sentiment: {
        score: number;
        label: string;
        post_count: number;
        sentiment_strength: string;
    };
    arbitrage: {
        profit_margin: number;
        guaranteed_profit: number;
        bookmakers: Record<string, string>;
    } | null;
    composite_score: number;
    tags: string[];
}

interface MarketIntelligenceResponse {
    headline: string;
    generated_at: string;
    suggestions: Suggestion[];
    filters_applied: {
        min_ev: number;
        min_sentiment: number;
        leagues: string | string[];
    };
}

export default function MarketIntelligencePage() {
    const [data, setData] = useState<MarketIntelligenceResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [filters, setFilters] = useState({
        max_results: 10,
        min_ev: 0.01,
        min_sentiment: -1.0,
        leagues: ''
    });

    const fetchIntelligence = async () => {
        setLoading(true);
        setError(null);

        try {
            const params = new URLSearchParams({
                max_results: filters.max_results.toString(),
                min_ev: filters.min_ev.toString(),
                min_sentiment: filters.min_sentiment.toString(),
                ...(filters.leagues && { leagues: filters.leagues })
            });

            // Use environment variable or default to localhost:8000 for Docker
            const apiBase = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';
            const response = await fetch(`${apiBase}/api/market-intelligence?${params}`);

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const json = await response.json();
            setData(json);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to fetch data');
            console.error('Error fetching market intelligence:', err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchIntelligence();

        // Auto-refresh every 30 seconds
        const interval = setInterval(fetchIntelligence, 30000);

        return () => clearInterval(interval);
    }, [filters]);

    const getSentimentEmoji = (label: string) => {
        switch (label) {
            case 'positive': return '😊';
            case 'negative': return '😔';
            default: return '😐';
        }
    };

    const formatPercentage = (value: number) => {
        return `${(value * 100).toFixed(1)}%`;
    };

    const formatCurrency = (value: number) => {
        return `$${value.toFixed(2)}`;
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 text-white p-6">
            <div className="max-w-7xl mx-auto">
                {/* Header */}
                <div className="mb-8">
                    <h1 className="text-4xl font-bold mb-2 bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent">
                        🔥 Market Intelligence Dashboard
                    </h1>
                    <p className="text-gray-400">Real-time AI-powered betting insights fusing ML, sentiment, and arbitrage</p>
                </div>

                {/* Filters */}
                <div className="bg-gray-800 rounded-lg p-6 mb-6 shadow-xl">
                    <h2 className="text-xl font-semibold mb-4">Filters</h2>
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                        <div>
                            <label className="block text-sm font-medium mb-2">Max Results</label>
                            <input
                                type="number"
                                value={filters.max_results}
                                onChange={(e) => setFilters({ ...filters, max_results: parseInt(e.target.value) })}
                                className="w-full px-3 py-2 bg-gray-700 rounded border border-gray-600 focus:border-blue-500 focus:outline-none"
                                min="1"
                                max="50"
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium mb-2">Min EV (%)</label>
                            <input
                                type="number"
                                value={filters.min_ev * 100}
                                onChange={(e) => setFilters({ ...filters, min_ev: parseFloat(e.target.value) / 100 })}
                                className="w-full px-3 py-2 bg-gray-700 rounded border border-gray-600 focus:border-blue-500 focus:outline-none"
                                step="0.1"
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium mb-2">Min Sentiment</label>
                            <input
                                type="number"
                                value={filters.min_sentiment}
                                onChange={(e) => setFilters({ ...filters, min_sentiment: parseFloat(e.target.value) })}
                                className="w-full px-3 py-2 bg-gray-700 rounded border border-gray-600 focus:border-blue-500 focus:outline-none"
                                min="-1"
                                max="1"
                                step="0.1"
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium mb-2">Leagues (csv)</label>
                            <input
                                type="text"
                                value={filters.leagues}
                                onChange={(e) => setFilters({ ...filters, leagues: e.target.value })}
                                placeholder="soccer_epl,soccer_spain_la_liga"
                                className="w-full px-3 py-2 bg-gray-700 rounded border border-gray-600 focus:border-blue-500 focus:outline-none"
                            />
                        </div>
                    </div>
                </div>

                {/* Loading State */}
                {loading && (
                    <div className="text-center py-12">
                        <div className="inline-block animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
                        <p className="mt-4 text-gray-400">Loading market intelligence...</p>
                    </div>
                )}

                {/* Error State */}
                {error && (
                    <div className="bg-red-900/50 border border-red-500 rounded-lg p-4 mb-6">
                        <p className="font-semibold">Error:</p>
                        <p className="text-sm mt-1">{error}</p>
                        <button
                            onClick={fetchIntelligence}
                            className="mt-4 px-4 py-2 bg-red-600 hover:bg-red-700 rounded transition"
                        >
                            Retry
                        </button>
                    </div>
                )}

                {/* Suggestions */}
                {!loading && data && (
                    <>
                        {/* Headline */}
                        <div className="mb-6">
                            <h2 className="text-2xl font-bold mb-2">{data.headline}</h2>
                            <p className="text-sm text-gray-400">
                                Generated at: {new Date(data.generated_at).toLocaleString()}
                            </p>
                        </div>

                        {/* Suggestions Grid */}
                        {data.suggestions.length === 0 ? (
                            <div className="bg-gray-800 rounded-lg p-12 text-center">
                                <p className="text-xl text-gray-400">No suggestions found with current filters</p>
                                <p className="text-sm text-gray-500 mt-2">Try adjusting your filter criteria</p>
                            </div>
                        ) : (
                            <div className="space-y-4">
                                {data.suggestions.map((suggestion) => (
                                    <div
                                        key={suggestion.market_id}
                                        className="bg-gradient-to-r from-gray-800 to-gray-750 rounded-lg p-6 shadow-xl border border-gray-700 hover:border-blue-500 transition"
                                    >
                                        {/* Rank and Tags */}
                                        <div className="flex items-start justify-between mb-4">
                                            <div className="flex items-center gap-3">
                                                <div className="bg-blue-600 text-white font-bold rounded-full w-10 h-10 flex items-center justify-center text-lg">
                                                    #{suggestion.rank}
                                                </div>
                                                <div>
                                                    <h3 className="text-xl font-bold">
                                                        {suggestion.home} vs {suggestion.away}
                                                    </h3>
                                                    <p className="text-sm text-gray-400">{suggestion.league}</p>
                                                </div>
                                            </div>
                                            <div className="flex gap-2">
                                                {suggestion.tags.includes('ARBITRAGE') && (
                                                    <span className="px-3 py-1 bg-green-600 text-xs font-bold rounded-full">
                                                        ⚡ ARBITRAGE
                                                    </span>
                                                )}
                                                {suggestion.tags.includes('HIGH_VALUE') && (
                                                    <span className="px-3 py-1 bg-purple-600 text-xs font-bold rounded-full">
                                                        🔥 HIGH VALUE
                                                    </span>
                                                )}
                                                {suggestion.tags.includes('POSITIVE_SENTIMENT') && (
                                                    <span className="px-3 py-1 bg-blue-600 text-xs font-bold rounded-full">
                                                        📈 TRENDING
                                                    </span>
                                                )}
                                            </div>
                                        </div>

                                        {/* Arbitrage Alert */}
                                        {suggestion.arbitrage && (
                                            <div className="mb-4 p-4 bg-green-900/30 border border-green-500 rounded-lg">
                                                <p className="font-bold text-green-400 mb-2">
                                                    ⚡ Guaranteed Profit Opportunity
                                                </p>
                                                <div className="grid grid-cols-2 gap-4 text-sm">
                                                    <div>
                                                        <p className="text-gray-400">Profit Margin</p>
                                                        <p className="text-xl font-bold text-green-400">
                                                            {formatPercentage(suggestion.arbitrage.profit_margin)}
                                                        </p>
                                                    </div>
                                                    <div>
                                                        <p className="text-gray-400">Guaranteed Profit</p>
                                                        <p className="text-xl font-bold text-green-400">
                                                            {formatCurrency(suggestion.arbitrage.guaranteed_profit)}
                                                        </p>
                                                    </div>
                                                </div>
                                            </div>
                                        )}

                                        {/* Main Info Grid */}
                                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                                            {/* Recommendation */}
                                            <div className="bg-gray-900/50 p-4 rounded">
                                                <p className="text-xs text-gray-400 mb-1">Recommendation</p>
                                                <p className="text-lg font-bold capitalize">{suggestion.recommendation.selection}</p>
                                                <p className="text-sm text-gray-400">@ {suggestion.recommendation.odds.toFixed(2)}</p>
                                            </div>

                                            {/* ML Probability */}
                                            <div className="bg-gray-900/50 p-4 rounded">
                                                <p className="text-xs text-gray-400 mb-1">ML Probability</p>
                                                <p className="text-lg font-bold">{formatPercentage(suggestion.recommendation.ml_probability)}</p>
                                                <p className="text-sm text-gray-400">Confidence: {formatPercentage(suggestion.recommendation.confidence)}</p>
                                            </div>

                                            {/* Expected Value */}
                                            <div className="bg-gray-900/50 p-4 rounded">
                                                <p className="text-xs text-gray-400 mb-1">Expected Value</p>
                                                <p className={`text-lg font-bold ${suggestion.recommendation.expected_value > 0 ? 'text-green-400' : 'text-red-400'}`}>
                                                    {suggestion.recommendation.expected_value > 0 ? '+' : ''}{formatPercentage(suggestion.recommendation.expected_value)}
                                                </p>
                                                <p className="text-sm text-gray-400">Kelly: {formatCurrency(suggestion.recommendation.kelly_stake)}</p>
                                            </div>

                                            {/* Sentiment */}
                                            <div className="bg-gray-900/50 p-4 rounded">
                                                <p className="text-xs text-gray-400 mb-1">Sentiment</p>
                                                <p className="text-lg font-bold">
                                                    {getSentimentEmoji(suggestion.sentiment.label)} {suggestion.sentiment.label}
                                                </p>
                                                <p className="text-sm text-gray-400">
                                                    {suggestion.sentiment.post_count} posts · {suggestion.sentiment.sentiment_strength}
                                                </p>
                                            </div>
                                        </div>

                                        {/* Composite Score */}
                                        <div className="flex items-center justify-between pt-4 border-t border-gray-700">
                                            <div>
                                                <p className="text-xs text-gray-400">Composite Score</p>
                                                <p className="text-2xl font-bold text-blue-400">{suggestion.composite_score.toFixed(3)}</p>
                                            </div>
                                            <div className="flex gap-3">
                                                <Link
                                                    href={`/fixtures/${suggestion.market_id}`}
                                                    className="px-6 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg font-semibold transition"
                                                >
                                                    View Details
                                                </Link>
                                                <Link
                                                    href={`/manual-betting?market_id=${suggestion.market_id}&selection=${suggestion.recommendation.selection}&odds=${suggestion.recommendation.odds}`}
                                                    className="px-6 py-2 bg-green-600 hover:bg-green-700 rounded-lg font-semibold transition"
                                                >
                                                    Place Bet
                                                </Link>
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </>
                )}

                {/* Footer */}
                <div className="mt-8 text-center text-sm text-gray-500">
                    <p>Auto-refreshing every 30 seconds · Last updated: {data ? new Date(data.generated_at).toLocaleTimeString() : 'N/A'}</p>
                    <div className="mt-4 flex justify-center gap-4">
                        <Link href="/" className="hover:text-blue-400 transition">← Back to Dashboard</Link>
                        <Link href="/fixtures/browse" className="hover:text-blue-400 transition">Browse All Fixtures</Link>
                        <Link href="/manual-betting" className="hover:text-blue-400 transition">Manual Betting</Link>
                    </div>
                </div>
            </div>
        </div>
    );
}
