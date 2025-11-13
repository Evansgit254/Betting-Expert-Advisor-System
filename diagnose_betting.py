#!/usr/bin/env python3
"""Diagnostic script to find out why no bets are being placed"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd

from src.feature import build_features
from src.risk import calculate_expected_value, stake_from_bankroll
from src.strategy import find_value_bets
from src.tools.synthetic_data import generate_synthetic_fixtures, generate_synthetic_odds

print("=" * 70)
print("  🔍 BETTING DIAGNOSTICS")
print("=" * 70)

# Generate test data
print("\n1️⃣ Generating test data...")
fixtures = generate_synthetic_fixtures(n_days=1, games_per_day=5)
odds = generate_synthetic_odds(fixtures)
print(f"   ✅ Generated {len(fixtures)} fixtures, {len(odds)} odds")

# Build features
print("\n2️⃣ Building features...")
features = build_features(fixtures, odds)
print(f"   ✅ Features shape: {features.shape}")
print(f"   Columns: {list(features.columns)}")

# Check for required columns
print("\n3️⃣ Checking required columns...")
required = ["home", "away", "odds", "p_win", "market_id"]
for col in required:
    if col in features.columns:
        print(f"   ✅ {col}: Present")
    else:
        # Check for similar columns
        similar = [c for c in features.columns if col.lower() in c.lower()]
        if similar:
            print(f"   ⚠️  {col}: Missing, but found similar: {similar}")
        else:
            print(f"   ❌ {col}: MISSING")

# Manually calculate what we SHOULD see
print("\n4️⃣ Manual EV calculation on first 5 matches...")
for i in range(min(5, len(features))):
    row = features.iloc[i]

    # Try to find probability column
    p_col = None
    for col in ["p_win", "implied_prob_home", "home_y", "home"]:
        if col in features.columns and pd.notna(row.get(col)):
            p_col = col
            break

    # Try to find odds column
    o_col = None
    for col in ["odds", "home_y", "home"]:
        if col in features.columns and pd.notna(row.get(col)) and row.get(col, 0) > 1:
            o_col = col
            break

    if p_col and o_col:
        p = row[p_col]
        odds = row[o_col]
        ev = calculate_expected_value(p, odds)
        stake = stake_from_bankroll(p, odds, 1000.0)

        print(f"\n   Match {i+1}:")
        print(f"   - Probability ({p_col}): {p:.3f}")
        print(f"   - Odds ({o_col}): {odds:.2f}")
        print(f"   - Expected Value: {ev:.4f} ({ev*100:.2f}%)")
        print(f"   - Suggested stake: ${stake:.2f}")
        print(f"   - Would qualify: {'✅ YES' if ev >= 0.001 and p >= 0.48 else '❌ NO'}")

# Try to find value bets with very low thresholds
print("\n5️⃣ Attempting to find value bets...")
print("   Using ultra-low thresholds:")
print("   - min_ev: -0.05 (allow negative!)")
print("   - min_odds: 1.01")
print("   - max_odds: 10.0")

bets = find_value_bets(
    features,
    proba_col="p_win"
    if "p_win" in features.columns
    else list(features.select_dtypes(include=[np.number]).columns)[0],
    odds_col="odds"
    if "odds" in features.columns
    else list(features.select_dtypes(include=[np.number]).columns)[1],
    bank=1000.0,
    min_ev=-0.05,  # Accept even negative EV
    min_odds=1.01,
    max_odds=10.0,
    dynamic_tuning=False,
)

print(f"\n   Result: Found {len(bets)} bets")

if len(bets) > 0:
    print("\n   ✅ SUCCESS! Bets were found:")
    for bet in bets[:3]:
        print(f"   - {bet['home']} vs {bet['away']}")
        print(f"     Odds: {bet['odds']:.2f}, EV: {bet['ev']:.4f}, Stake: ${bet['stake']:.2f}")
else:
    print("\n   ❌ STILL NO BETS - Issue is deeper")
    print("\n   Let's check what's in the DataFrame:")
    print(features.head())
    print("\n   Data types:")
    print(features.dtypes)

print("\n" + "=" * 70)
print("  DIAGNOSIS COMPLETE")
print("=" * 70)
