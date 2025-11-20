"use client";

import React, { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import clsx from 'clsx';

interface OpportunityCardProps {
    home: string;
    away: string;
    selection: string;
    odds: number;
    stake: number;
    ev: number;
    probability: number;
}

export function OpportunityCard({ home, away, selection, odds, stake, ev, probability }: OpportunityCardProps) {
    const [expanded, setExpanded] = useState(false);

    return (
        <div className={clsx(
            'rounded-lg border border-yellow-700/50 bg-gradient-to-r from-yellow-900/20 to-orange-900/20 p-4',
            'hover:from-yellow-900/30 hover:to-orange-900/30 transition-all cursor-pointer'
        )}
            onClick={() => setExpanded(!expanded)}
        >
            <div className="flex justify-between items-start">
                <div className="flex-1">
                    <div className="font-semibold text-white text-lg">{home} vs {away}</div>
                    <div className="text-sm text-yellow-400 mt-1">👉 BET: {selection.toUpperCase()}</div>
                </div>
                <div className="text-right">
                    <div className="text-lg font-bold text-green-400">${stake.toFixed(2)}</div>
                    <div className="text-sm text-neutral-400">@ {odds.toFixed(2)}</div>
                </div>
            </div>

            <div className="mt-3 flex gap-4 text-sm">
                <span className="text-neutral-300">Prob: {(probability * 100).toFixed(1)}%</span>
                <span className="text-green-400">EV: +{ev.toFixed(2)}</span>
            </div>

            {expanded && (
                <div className="mt-4 pt-4 border-t border-yellow-700/30">
                    <div className="grid grid-cols-2 gap-3 text-sm">
                        <div>
                            <div className="text-neutral-400">Implied Probability</div>
                            <div className="text-white font-medium">{(1 / odds * 100).toFixed(1)}%</div>
                        </div>
                        <div>
                            <div className="text-neutral-400">Edge</div>
                            <div className="text-green-400 font-medium">{((probability - 1 / odds) * 100).toFixed(1)}%</div>
                        </div>
                        <div>
                            <div className="text-neutral-400">Expected Return</div>
                            <div className="text-white font-medium">${(stake * odds).toFixed(2)}</div>
                        </div>
                        <div>
                            <div className="text-neutral-400">Confidence</div>
                            <div className="text-blue-400 font-medium">{probability > 0.6 ? 'High' : probability > 0.4 ? 'Medium' : 'Low'}</div>
                        </div>
                    </div>
                </div>
            )}

            <div className="mt-2 flex justify-center">
                {expanded ? <ChevronUp className="h-4 w-4 text-neutral-500" /> : <ChevronDown className="h-4 w-4 text-neutral-500" />}
            </div>
        </div>
    );
}
