#!/usr/bin/env python3
"""Automated model retraining orchestrator."""
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

from src.model_version import ModelVersionManager
from src.data_collector import DataCollector
from src.model_ensemble import EnsembleModel
from src.feature import build_features
from src.logging_config import get_logger
from src.alerts import send_alert

logger = get_logger(__name__)


def main():
    """Run automated retraining."""
    print("=" * 70)
    print("  AUTOMATED MODEL RETRAINING")
    print("=" * 70)
    print()
    
    try:
        # Initialize components
        version_manager = ModelVersionManager()
        data_collector = DataCollector()
        
        # Send start notification
        send_alert("🤖 Automated retraining started...", level="info")
        
        # Step 1: Collect new data
        print("📊 Step 1: Collecting recent match results...")
        new_results = data_collector.collect_recent_results(days=7)
        
        if len(new_results) < 50:
            msg = f"⚠️ Insufficient new data ({len(new_results)} samples). Skipping retraining."
            logger.warning(msg)
            send_alert(msg, level="warning")
            return
        
        # Step 2: Validate data
        print("✅ Step 2: Validating data quality...")
        if not data_collector.validate_results(new_results):
            msg = "❌ Data validation failed. Aborting retraining."
            logger.error(msg)
            send_alert(msg, level="error")
            return
        
        # Step 3: Prepare features
        print("🔧 Step 3: Preparing features...")
        
        # Create fixtures DataFrame from results
        fixtures = new_results[['market_id', 'home', 'away']].copy()
        
        # Create odds DataFrame
        odds_data = []
        for _, row in new_results.iterrows():
            for selection, odds_col in [('home', 'home_odds'), ('away', 'away_odds'), ('draw', 'draw_odds')]:
                odds_data.append({
                    'market_id': row['market_id'],
                    'selection': selection,
                    'odds': row[odds_col]
                })
        odds = pd.DataFrame(odds_data)
        
        # Build features
        features_df = build_features(fixtures, odds)
        
        # Add outcomes
        features_df = features_df.merge(
            new_results[['market_id', 'outcome']],
            on='market_id',
            how='left'
        )
        
        # Remove rows with missing outcomes
        features_df = features_df.dropna(subset=['outcome'])
        
        print(f"   Generated features for {len(features_df)} matches")
        
        # Step 4: Prepare training data
        print("📚 Step 4: Preparing training data...")
        
        feature_cols = [col for col in features_df.columns if col not in ['market_id', 'outcome', 'home', 'away', 'start', 'sport', 'league']]
        X = features_df[feature_cols].select_dtypes(include=[np.number]).fillna(0).values
        
        # Encode labels
        label_encoder = LabelEncoder()
        y = label_encoder.fit_transform(features_df['outcome'])
        
        print(f"   Training data shape: X={X.shape}, y={y.shape}")
        
        # Step 5: Backup current model
        print("💾 Step 5: Backing up current model...")
        version_manager.backup_current_model("ensemble")
        
        # Step 6: Train new model
        print("🤖 Step 6: Training new ensemble model...")
        
        new_model = EnsembleModel()
        new_model.train(X, y, verbose=False)
        
        # Step 7: Evaluate performance
        print("📈 Step 7: Evaluating model performance...")
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        y_pred = new_model.predict(X_test)
        
        accuracy = accuracy_score(y_test, y_pred)
        precision = precision_score(y_test, y_pred, average='weighted', zero_division=0)
        recall = recall_score(y_test, y_pred, average='weighted', zero_division=0)
        f1 = f1_score(y_test, y_pred, average='weighted', zero_division=0)
        
        print(f"   Accuracy:  {accuracy:.4f}")
        print(f"   Precision: {precision:.4f}")
        print(f"   Recall:    {recall:.4f}")
        print(f"   F1 Score:  {f1:.4f}")
        
        # Step 8: Compare with current model (if criterias met)
        print("⚖️  Step 8: Performance comparison...")
        
        # Get previous model metrics if available
        latest_version = version_manager.get_latest_version()
        if latest_version and 'metrics' in latest_version:
            prev_accuracy = latest_version['metrics'].get('accuracy', 0)
            improvement = accuracy - prev_accuracy
            
            print(f"   Previous accuracy: {prev_accuracy:.4f}")
            print(f"   Improvement: {improvement:+.4f}")
            
            # Deploy only if improvement >= 1%
            if improvement < 0.01:
                msg = f"⚠️ New model accuracy ({accuracy:.4f}) not significantly better. Keeping current model."
                logger.info(msg)
                send_alert(msg, level="info")
                return
        
        # Step 9: Deploy new model
        print("🚀 Step 9: Deploying new model...")
        
        new_model.save()
        
        # Save metrics in version history
        current_version_id = version_manager.get_latest_version()['version_id']
        for version in version_manager.versions:
            if version['version_id'] == current_version_id:
                version['metrics'] = {
                    'accuracy': float(accuracy),
                    'precision': float(precision),
                    'recall': float(recall),
                    'f1': float(f1)
                }
                break
        version_manager._save_versions()
        
        # Step 10: Cleanup old backups
        print("🧹 Step 10: Cleaning up old backups...")
        version_manager.cleanup_old_versions(retention_days=30)
        
        # Success notification
        print()
        print("=" * 70)
        print("✅ RETRAINING COMPLETED SUCCESSFULLY")
        print("=" * 70)
        
        msg = (
            f"✅ Model retraining complete!\n\n"
            f"📊 Performance:\n"
            f"   Accuracy:  {accuracy:.4f}\n"
            f"   Precision: {precision:.4f}\n"
            f"   Recall:    {recall:.4f}\n"
            f"   F1 Score:  {f1:.4f}\n\n"
            f"📦 Training data: {len(features_df)} matches\n"
            f"🚀 New model deployed"
        )
        send_alert(msg, level="info")
        
    except Exception as e:
        logger.error(f"Retraining failed: {e}", exc_info=True)
        send_alert(f"❌ Model retraining failed: {str(e)}", level="error")
        raise


if __name__ == "__main__":
    main()
