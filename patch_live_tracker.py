# Read the file
with open("scripts/live_tracker.py", "r") as f:
    content = f.read()

# Replace the problematic section
old_code = """            # Make predictions
            if self.model is None:
                print("  ⚠️  No model - using default probabilities")
                features['p_win'] = 0.50
            else:
                # Use proper feature selection to match training
                X = features.drop(columns=['market_id', 'result'], errors='ignore')
                X_selected = select_features(X)
                predictions = self.model.predict_proba(X_selected.values)[:, 1]
                features['p_win'] = predictions
            
            # Prepare for value detection
            features['odds'] = features.get('home', 2.0)
            features['selection'] = 'home'
            
            # Find value bets
            value_bets = find_value_bets(
                features,
                proba_col='p_win',
                odds_col='odds',"""

new_code = """            # Make predictions
            if self.model is None:
                print("  ⚠️  No model - using normalized implied probabilities")
                if 'home_prob' not in features.columns:
                    if 'home_odds' in features.columns:
                        features['home_prob'] = 1.0 / features['home_odds']
                    else:
                        print("  ❌ Cannot calculate probabilities")
                        return []
            else:
                print("  🤖 Using ML model predictions...")
                X = features.drop(columns=['market_id', 'result'], errors='ignore')
                X_selected = select_features(X)
                try:
                    predictions = self.model.predict_proba(X_selected)
                    if len(predictions.shape) > 1 and predictions.shape[1] > 1:
                        features['home_prob'] = predictions[:, 1]
                    else:
                        features['home_prob'] = predictions
                    print(f"  ✅ Predictions: mean={features['home_prob'].mean():.3f}")
                except Exception as e:
                    print(f"  ⚠️  Model failed: {e}, using implied probs")
                    if 'home_odds' in features.columns:
                        features['home_prob'] = 1.0 / features['home_odds']
            
            # Verify columns
            if 'home_odds' not in features.columns or 'home_prob' not in features.columns:
                print(f"  ❌ Missing required columns")
                print(f"  Available: {list(features.columns)}")
                return []
            
            # Find value bets
            print(f"  🔍 Searching for value bets...")
            value_bets = find_value_bets(
                features,
                proba_col='home_prob',
                odds_col='home_odds',"""

content = content.replace(old_code, new_code)

# Write back
with open("scripts/live_tracker.py", "w") as f:
    f.write(content)

print("✅ Patched live_tracker.py")
