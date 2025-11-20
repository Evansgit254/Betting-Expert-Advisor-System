'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { 
  TrendingUp, TrendingDown, Target, DollarSign, 
  BarChart3, Activity, RefreshCw, Bell 
} from 'lucide-react';

interface Opportunity {
  fixture_id: string;
  league: string;
  home_team: string;
  away_team: string;
  commence_time: string;
  prediction: string;
  confidence: number;
  odds: number;
  expected_value: number;
  tier: number;
  reason: string;
}

interface Stats {
  total_opportunities: number;
  tier1_count: number;
  tier2_count: number;
  tier3_count: number;
  avg_confidence: number;
  avg_ev: number;
  win_rate: number;
  roi: number;
  profit_loss: number;
  total_bets: number;
  best_opportunities: Array<{
    match: string;
    prediction: string;
    odds: number;
    confidence: number;
  }>;
  daily_profit_trend: Array<{
    date: string;
    profit: number;
  }>;
}

export default function AnalyticsDashboard() {
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());
  const [autoRefresh, setAutoRefresh] = useState(true);

  const fetchData = async () => {
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';
      const response = await fetch(`${apiBase}/api/analytics/dashboard`);
      const result = await response.json();
      
      if (result.success) {
        setOpportunities(result.data.current_opportunities || []);
        setStats(result.data.stats);
        setLastUpdate(new Date());
      }
    } catch (error) {
      console.error('Error fetching analytics:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    
    if (autoRefresh) {
      const interval = setInterval(fetchData, 30000); // Refresh every 30 seconds
      return () => clearInterval(interval);
    }
  }, [autoRefresh]);

  const getTierColor = (tier: number) => {
    switch (tier) {
      case 1: return 'bg-yellow-500';
      case 2: return 'bg-blue-500';
      case 3: return 'bg-green-500';
      default: return 'bg-gray-500';
    }
  };

  const getTierLabel = (tier: number) => {
    switch (tier) {
      case 1: return 'Premium';
      case 2: return 'High';
      case 3: return 'Good';
      default: return 'Standard';
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-950">
        <div className="text-center">
          <RefreshCw className="w-12 h-12 animate-spin text-blue-500 mx-auto mb-4" />
          <p className="text-gray-400">Loading analytics...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white p-6">
      {/* Header */}
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-4xl font-bold mb-2">📊 Analytics Dashboard</h1>
          <p className="text-gray-400">
            Last updated: {lastUpdate.toLocaleTimeString()}
          </p>
        </div>
        <div className="flex gap-4">
          <Button
            onClick={() => setAutoRefresh(!autoRefresh)}
            variant={autoRefresh ? 'default' : 'outline'}
            className="flex items-center gap-2"
          >
            <Bell className="w-4 h-4" />
            {autoRefresh ? 'Auto-Refresh ON' : 'Auto-Refresh OFF'}
          </Button>
          <Button onClick={fetchData} className="flex items-center gap-2">
            <RefreshCw className="w-4 h-4" />
            Refresh Now
          </Button>
        </div>
      </div>

      {/* Stats Overview */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <Card className="bg-gray-900 border-gray-800">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-gray-400">
              Total Opportunities
            </CardTitle>
            <Target className="w-4 h-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{stats?.total_opportunities || 0}</div>
            <p className="text-xs text-gray-500 mt-1">
              Tier 1: {stats?.tier1_count || 0} | Tier 2: {stats?.tier2_count || 0} | Tier 3: {stats?.tier3_count || 0}
            </p>
          </CardContent>
        </Card>

        <Card className="bg-gray-900 border-gray-800">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-gray-400">
              Avg Confidence
            </CardTitle>
            <Activity className="w-4 h-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {((stats?.avg_confidence || 0) * 100).toFixed(1)}%
            </div>
            <p className="text-xs text-gray-500 mt-1">
              Avg EV: {((stats?.avg_ev || 0) * 100).toFixed(1)}%
            </p>
          </CardContent>
        </Card>

        <Card className="bg-gray-900 border-gray-800">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-gray-400">
              Win Rate
            </CardTitle>
            <TrendingUp className="w-4 h-4 text-yellow-500" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {((stats?.win_rate || 0) * 100).toFixed(1)}%
            </div>
            <p className="text-xs text-gray-500 mt-1">
              {stats?.total_bets || 0} total bets
            </p>
          </CardContent>
        </Card>

        <Card className="bg-gray-900 border-gray-800">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-gray-400">
              Profit/Loss
            </CardTitle>
            <DollarSign className={`w-4 h-4 ${(stats?.profit_loss || 0) >= 0 ? 'text-green-500' : 'text-red-500'}`} />
          </CardHeader>
          <CardContent>
            <div className={`text-3xl font-bold ${(stats?.profit_loss || 0) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
              ${(stats?.profit_loss || 0).toFixed(2)}
            </div>
            <p className="text-xs text-gray-500 mt-1">
              ROI: {((stats?.roi || 0) * 100).toFixed(1)}%
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Main Content */}
      <Tabs defaultValue="opportunities" className="space-y-6">
        <TabsList className="bg-gray-900">
          <TabsTrigger value="opportunities">Current Opportunities</TabsTrigger>
          <TabsTrigger value="performance">Performance</TabsTrigger>
          <TabsTrigger value="trends">Trends</TabsTrigger>
        </TabsList>

        <TabsContent value="opportunities" className="space-y-4">
          {opportunities.length === 0 ? (
            <Card className="bg-gray-900 border-gray-800">
              <CardContent className="py-12 text-center">
                <p className="text-gray-400">No opportunities available at the moment.</p>
                <p className="text-sm text-gray-500 mt-2">Check back soon or refresh the page.</p>
              </CardContent>
            </Card>
          ) : (
            opportunities.map((opp, index) => (
              <Card key={index} className="bg-gray-900 border-gray-800 hover:border-gray-700 transition-colors">
                <CardHeader>
                  <div className="flex justify-between items-start">
                    <div>
                      <CardTitle className="text-xl mb-2">
                        {opp.home_team} vs {opp.away_team}
                      </CardTitle>
                      <CardDescription className="text-gray-400">
                        {opp.league} • {new Date(opp.commence_time).toLocaleString()}
                      </CardDescription>
                    </div>
                    <Badge className={getTierColor(opp.tier)}>
                      Tier {opp.tier} - {getTierLabel(opp.tier)}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                    <div>
                      <p className="text-sm text-gray-400">Prediction</p>
                      <p className="text-lg font-bold uppercase">{opp.prediction}</p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-400">Odds</p>
                      <p className="text-lg font-bold">{opp.odds.toFixed(2)}</p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-400">Confidence</p>
                      <p className="text-lg font-bold text-green-500">
                        {(opp.confidence * 100).toFixed(0)}%
                      </p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-400">Expected Value</p>
                      <p className={`text-lg font-bold ${opp.expected_value >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                        {(opp.expected_value * 100).toFixed(1)}%
                      </p>
                    </div>
                  </div>
                  <div className="bg-gray-800 p-3 rounded">
                    <p className="text-sm text-gray-300">{opp.reason}</p>
                  </div>
                </CardContent>
              </Card>
            ))
          )}
        </TabsContent>

        <TabsContent value="performance">
          <Card className="bg-gray-900 border-gray-800">
            <CardHeader>
              <CardTitle>Performance Metrics</CardTitle>
              <CardDescription>Historical betting performance</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                <div className="grid grid-cols-2 md:grid-cols-3 gap-6">
                  <div>
                    <p className="text-sm text-gray-400 mb-1">Total Bets</p>
                    <p className="text-2xl font-bold">{stats?.total_bets || 0}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-400 mb-1">Win Rate</p>
                    <p className="text-2xl font-bold text-green-500">
                      {((stats?.win_rate || 0) * 100).toFixed(1)}%
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-400 mb-1">ROI</p>
                    <p className={`text-2xl font-bold ${(stats?.roi || 0) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                      {((stats?.roi || 0) * 100).toFixed(1)}%
                    </p>
                  </div>
                </div>

                {stats?.best_opportunities && stats.best_opportunities.length > 0 && (
                  <div>
                    <h3 className="text-lg font-semibold mb-4">Top Opportunities Today</h3>
                    <div className="space-y-3">
                      {stats.best_opportunities.map((opp, index) => (
                        <div key={index} className="bg-gray-800 p-4 rounded flex justify-between items-center">
                          <div>
                            <p className="font-medium">{opp.match}</p>
                            <p className="text-sm text-gray-400">
                              {opp.prediction.toUpperCase()} @ {opp.odds.toFixed(2)}
                            </p>
                          </div>
                          <Badge className="bg-green-500">
                            {(opp.confidence * 100).toFixed(0)}%
                          </Badge>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="trends">
          <Card className="bg-gray-900 border-gray-800">
            <CardHeader>
              <CardTitle>Profit Trend</CardTitle>
              <CardDescription>Daily profit/loss over time</CardDescription>
            </CardHeader>
            <CardContent>
              {stats?.daily_profit_trend && stats.daily_profit_trend.length > 0 ? (
                <div className="space-y-2">
                  {stats.daily_profit_trend.slice(-10).map((day, index) => (
                    <div key={index} className="flex justify-between items-center py-2 border-b border-gray-800">
                      <span className="text-gray-400">{day.date}</span>
                      <span className={`font-bold ${day.profit >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                        ${day.profit.toFixed(2)}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-gray-400 text-center py-8">No trend data available yet</p>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
