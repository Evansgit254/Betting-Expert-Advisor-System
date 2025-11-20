"use client";

import React from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import clsx from 'clsx';

interface MetricCardProps {
    title: string;
    value: string | number;
    change?: number;
    trend?: 'up' | 'down' | 'neutral';
    suffix?: string;
    className?: string;
}

export function MetricCard({ title, value, change, trend, suffix, className }: MetricCardProps) {
    const getTrendIcon = () => {
        if (trend === 'up') return <TrendingUp className="h-4 w-4" />;
        if (trend === 'down') return <TrendingDown className="h-4 w-4" />;
        return <Minus className="h-4 w-4" />;
    };

    const getTrendColor = () => {
        if (trend === 'up') return 'text-green-400';
        if (trend === 'down') return 'text-red-400';
        return 'text-neutral-400';
    };

    return (
        <div className={clsx(
            'rounded-lg border border-neutral-800 bg-gradient-to-br from-neutral-900/50 to-neutral-900/30 p-6 backdrop-blur-sm',
            className
        )}>
            <div className="text-sm text-neutral-400 mb-2">{title}</div>
            <div className="flex items-end justify-between">
                <div className="text-3xl font-bold text-white">
                    {value}
                    {suffix && <span className="text-lg text-neutral-400 ml-1">{suffix}</span>}
                </div>
                {change !== undefined && (
                    <div className={clsx('flex items-center gap-1 text-sm', getTrendColor())}>
                        {getTrendIcon()}
                        <span>{change > 0 ? '+' : ''}{change.toFixed(1)}%</span>
                    </div>
                )}
            </div>
        </div>
    );
}
