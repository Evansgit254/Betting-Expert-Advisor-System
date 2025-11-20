"use client";

import React from 'react';
import { LineChart, Line, AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

interface ChartProps {
    data: any[];
    type: 'line' | 'area' | 'bar' | 'pie';
    dataKey?: string;
    xAxisKey?: string;
    height?: number;
    color?: string;
    colors?: string[];
}

const CHART_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4'];

export function Chart({ data, type, dataKey = 'value', xAxisKey = 'name', height = 300, color = '#3b82f6', colors = CHART_COLORS }: ChartProps) {
    if (!data || data.length === 0) {
        return (
            <div className="flex items-center justify-center h-64 text-neutral-500">
                No data available
            </div>
        );
    }

    const renderChart = () => {
        switch (type) {
            case 'line':
                return (
                    <LineChart data={data}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                        <XAxis dataKey={xAxisKey} stroke="#9ca3af" />
                        <YAxis stroke="#9ca3af" />
                        <Tooltip
                            contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: '8px' }}
                            labelStyle={{ color: '#f3f4f6' }}
                        />
                        <Legend />
                        <Line type="monotone" dataKey={dataKey} stroke={color} strokeWidth={2} dot={{ fill: color }} />
                    </LineChart>
                );

            case 'area':
                return (
                    <AreaChart data={data}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                        <XAxis dataKey={xAxisKey} stroke="#9ca3af" />
                        <YAxis stroke="#9ca3af" />
                        <Tooltip
                            contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: '8px' }}
                            labelStyle={{ color: '#f3f4f6' }}
                        />
                        <Legend />
                        <Area type="monotone" dataKey={dataKey} stroke={color} fill={color} fillOpacity={0.6} />
                    </AreaChart>
                );

            case 'bar':
                return (
                    <BarChart data={data}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                        <XAxis dataKey={xAxisKey} stroke="#9ca3af" />
                        <YAxis stroke="#9ca3af" />
                        <Tooltip
                            contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: '8px' }}
                            labelStyle={{ color: '#f3f4f6' }}
                        />
                        <Legend />
                        <Bar dataKey={dataKey} fill={color} />
                    </BarChart>
                );

            case 'pie':
                return (
                    <PieChart>
                        <Pie
                            data={data}
                            cx="50%"
                            cy="50%"
                            labelLine={false}
                            label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                            outerRadius={80}
                            fill="#8884d8"
                            dataKey={dataKey}
                        >
                            {data.map((entry, index) => (
                                <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />
                            ))}
                        </Pie>
                        <Tooltip
                            contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: '8px' }}
                        />
                    </PieChart>
                );

            default:
                return null;
        }
    };

    return (
        <ResponsiveContainer width="100%" height={height}>
            {renderChart()}
        </ResponsiveContainer>
    );
}
