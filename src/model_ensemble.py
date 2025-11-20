"""Ensemble model combining multiple ML algorithms."""
import pickle
from pathlib import Path
from typing import Optional, Dict

import numpy as np
import lightgbm as lgb
import xgboost as xgb
from tensorflow import keras
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

from src.logging_config import get_logger

logger = get_logger(__name__)

MODEL_DIR = Path("./models")
ENSEMBLE_PATH = MODEL_DIR / "ensemble"


class EnsembleModel:
    """Ensemble of LightGBM, XGBoost, and Neural Network models."""
    
    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        lgb_params: Optional[Dict] = None,
        xgb_params: Optional[Dict] = None,
        nn_params: Optional[Dict] = None
    ):
        """Initialize ensemble model.
        
        Args:
            weights: Dict of model weights {'lgb': 0.33, 'xgb': 0.33, 'nn': 0.34}
            lgb_params: LightGBM hyperparameters
            xgb_params: XGBoost hyperparameters
            nn_params: Neural network architecture params
        """
        self.weights = weights or {'lgb': 0.33, 'xgb': 0.33, 'nn': 0.34}
        
        # LightGBM defaults
        self.lgb_params = lgb_params or {
            'objective': 'multiclass',
            'num_class': 3,
            'metric': 'multi_logloss',
            'num_leaves': 31,
            'learning_rate': 0.05,
            'feature_fraction': 0.9,
            'bagging_fraction': 0.8,
            'bagging_freq': 5,
            'verbose': -1
        }
        
        # XGBoost defaults
        self.xgb_params = xgb_params or {
            'objective': 'multi:softprob',
            'num_class': 3,
            'max_depth': 6,
            'learning_rate': 0.05,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'eval_metric': 'mlogloss',
            'verbosity': 0
        }
        
        # Neural network defaults
        self.nn_params = nn_params or {
            'hidden_layers': [64, 32, 16],
            'dropout': 0.3,
            'activation': 'relu',
            'epochs': 50,
            'batch_size': 32
        }
        
        self.lgb_model = None
        self.xgb_model = None
        self.nn_model = None
        self.n_features = None
        
        # Ensure model directory exists
        ENSEMBLE_PATH.mkdir(parents=True, exist_ok=True)
    
    def _build_nn(self, input_dim: int):
        """Build neural network architecture."""
        model = keras.Sequential()
        model.add(keras.layers.Input(shape=(input_dim,)))
        
        # Hidden layers
        for hidden_units in self.nn_params['hidden_layers']:
            model.add(keras.layers.Dense(hidden_units, activation=self.nn_params['activation']))
            model.add(keras.layers.Dropout(self.nn_params['dropout']))
        
        # Output layer (3 classes: home/draw/away)
        model.add(keras.layers.Dense(3, activation='softmax'))
        
        model.compile(
            optimizer='adam',
            loss='sparse_categorical_crossentropy',
            metrics=['accuracy']
        )
        
        return model
    
    def train(self, X: np.ndarray, y: np.ndarray, verbose: bool = True):
        """Train all three models.
        
        Args:
            X: Feature matrix (n_samples, n_features)
            y: Target vector (n_samples,) - must be 0/1/2 for home/draw/away
            verbose: Print training progress
        """
        self.n_features = X.shape[1]
        
        if verbose:
            logger.info(f"Training ensemble on {X.shape[0]} samples with {X.shape[1]} features")
        
        # Split data for validation
        X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # Train LightGBM
        if verbose:
            logger.info("Training LightGBM...")
        lgb_train = lgb.Dataset(X_train, y_train)
        lgb_val = lgb.Dataset(X_val, y_val, reference=lgb_train)
        self.lgb_model = lgb.train(
            self.lgb_params,
            lgb_train,
            num_boost_round=100,
            valid_sets=[lgb_val],
            callbacks=[lgb.early_stopping(stopping_rounds=10)] if verbose else None
        )
        
        # Train XGBoost
        if verbose:
            logger.info("Training XGBoost...")
        dtrain = xgb.DMatrix(X_train, label=y_train)
        dval = xgb.DMatrix(X_val, label=y_val)
        self.xgb_model = xgb.train(
            self.xgb_params,
            dtrain,
            num_boost_round=100,
            evals=[(dval, 'validation')],
            early_stopping_rounds=10,
            verbose_eval=verbose
        )
        
        # Train Neural Network
        if verbose:
            logger.info("Training Neural Network...")
        self.nn_model = self._build_nn(X.shape[1])
        self.nn_model.fit(
            X_train, y_train,
            epochs=self.nn_params['epochs'],
            batch_size=self.nn_params['batch_size'],
            validation_data=(X_val, y_val),
            verbose=1 if verbose else 0,
            callbacks=[keras.callbacks.EarlyStopping(patience=5, restore_best_weights=True)]
        )
        
        # Evaluate on validation set
        if verbose:
            self._evaluate(X_val, y_val)
        
        # Save models
        self.save()
        logger.info("Ensemble models trained and saved")
    
    def _evaluate(self, X: np.ndarray, y: np.ndarray):
        """Evaluate individual and ensemble performance."""
        # Get predictions from each model
        lgb_pred = self.lgb_model.predict(X).argmax(axis=1)
        dtest = xgb.DMatrix(X)
        xgb_pred = self.xgb_model.predict(dtest).argmax(axis=1)
        nn_pred = self.nn_model.predict(X, verbose=0).argmax(axis=1)
        ensemble_pred = self.predict(X)
        
        logger.info("\nModel Performance:")
        logger.info(f"LightGBM Accuracy: {accuracy_score(y, lgb_pred):.4f}")
        logger.info(f"XGBoost Accuracy:  {accuracy_score(y, xgb_pred):.4f}")
        logger.info(f"NeuralNet Accuracy: {accuracy_score(y, nn_pred):.4f}")
        logger.info(f"Ensemble Accuracy:  {accuracy_score(y, ensemble_pred):.4f}")
    
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Generate probability predictions from ensemble.
        
        Args:
            X: Feature matrix (n_samples, n_features)
            
        Returns:
            Probabilities for each class (n_samples, 3) for home/draw/away
        """
        if self.lgb_model is None or self.xgb_model is None or self.nn_model is None:
            raise RuntimeError("Models not trained. Call train() first.")
        
        # Get predictions from each model
        lgb_proba = self.lgb_model.predict(X)
        dtest = xgb.DMatrix(X)
        xgb_proba = self.xgb_model.predict(dtest)
        nn_proba = self.nn_model.predict(X, verbose=0)
        
        # Weighted average
        ensemble_proba = (
            self.weights['lgb'] * lgb_proba +
            self.weights['xgb'] * xgb_proba +
            self.weights['nn'] * nn_proba
        )
        
        return ensemble_proba
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Generate class predictions from ensemble.
        
        Args:
            X: Feature matrix (n_samples, n_features)
            
        Returns:
            Predicted classes (n_samples,) - 0/1/2 for home/draw/away
        """
        proba = self.predict_proba(X)
        return proba.argmax(axis=1)
    
    def save(self, path: Optional[Path] = None):
        """Save ensemble models to disk."""
        save_path = path or ENSEMBLE_PATH
        save_path.mkdir(parents=True, exist_ok=True)
        
        # Save individual models
        self.lgb_model.save_model(str(save_path / "lgb_model.txt"))
        self.xgb_model.save_model(str(save_path / "xgb_model.json"))
        self.nn_model.save(str(save_path / "nn_model.keras"))
        
        # Save metadata
        metadata = {
            'weights': self.weights,
            'n_features': self.n_features,
            'lgb_params': self.lgb_params,
            'xgb_params': self.xgb_params,
            'nn_params': self.nn_params
        }
        with open(save_path / "metadata.pkl", "wb") as f:
            pickle.dump(metadata, f)
        
        logger.info(f"Ensemble saved to {save_path}")
    
    def load(self, path: Optional[Path] = None):
        """Load ensemble models from disk."""
        load_path = path or ENSEMBLE_PATH
        
        # Load individual models
        self.lgb_model = lgb.Booster(model_file=str(load_path / "lgb_model.txt"))
        self.xgb_model = xgb.Booster()
        self.xgb_model.load_model(str(load_path / "xgb_model.json"))
        self.nn_model = keras.models.load_model(str(load_path / "nn_model.keras"))
        
        # Load metadata
        with open(load_path / "metadata.pkl", "rb") as f:
            metadata = pickle.load(f)
        
        self.weights = metadata['weights']
        self.n_features = metadata['n_features']
        self.lgb_params = metadata.get('lgb_params', {})
        self.xgb_params = metadata.get('xgb_params', {})
        self.nn_params = metadata.get('nn_params', {})
        
        logger.info(f"Ensemble loaded from {load_path}")
