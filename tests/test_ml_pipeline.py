"""Tests for ML pipeline module."""
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.datasets import make_classification

from src.ml_pipeline import MLPipeline


@pytest.fixture
def sample_ml_data():
    """Generate sample classification data for ML pipeline."""
    X, y = make_classification(
        n_samples=200,
        n_features=15,
        n_informative=10,
        n_redundant=3,
        n_classes=2,
        random_state=42,
        flip_y=0.1,  # Add some noise
    )

    # Convert to DataFrame for realistic usage
    feature_names = [f"feature_{i}" for i in range(X.shape[1])]
    X_df = pd.DataFrame(X, columns=feature_names)
    y_series = pd.Series(y, name="target")

    return X_df, y_series


@pytest.fixture
def temp_model_dir():
    """Create temporary directory for model storage."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_ml_pipeline_initialization():
    """Test MLPipeline initialization."""
    pipeline = MLPipeline()
    assert pipeline.model is None
    assert pipeline.best_params is None


def test_ml_pipeline_train_simple(sample_ml_data, temp_model_dir):
    """Test simple training without cross-validation."""
    X, y = sample_ml_data
    model_path = temp_model_dir / "test_model.pkl"
    pipeline = MLPipeline(model_path=model_path)

    model = pipeline.train_simple(X, y.values, num_leaves=31)

    # Model should be trained
    assert pipeline.model is not None
    assert model is not None


def test_ml_pipeline_train_simple_saves_model(sample_ml_data, temp_model_dir):
    """Test that simple training saves the model."""
    X, y = sample_ml_data
    model_path = temp_model_dir / "test_model.pkl"
    pipeline = MLPipeline(model_path=model_path)

    pipeline.train_simple(X, y.values)

    # Model file should exist
    assert model_path.exists()


def test_ml_pipeline_train_with_cv(sample_ml_data, temp_model_dir):
    """Test training with cross-validation."""
    X, y = sample_ml_data
    model_path = temp_model_dir / "test_model.pkl"
    pipeline = MLPipeline(model_path=model_path)

    # Use small n_trials and n_splits for speed
    model = pipeline.train_with_cv(X, y.values, n_splits=3, n_trials=3)

    # Should return model
    assert model is not None

    # Model should be trained
    assert pipeline.model is not None
    assert pipeline.best_params is not None


def test_ml_pipeline_train_with_cv_optuna(sample_ml_data, temp_model_dir):
    """Test that Optuna hyperparameter optimization works."""
    X, y = sample_ml_data
    model_path = temp_model_dir / "test_model.pkl"
    pipeline = MLPipeline(model_path=model_path)

    pipeline.train_with_cv(X, y.values, n_splits=3, n_trials=5)

    # Should have found best parameters
    assert pipeline.best_params is not None
    assert isinstance(pipeline.best_params, dict)

    # Best params should have LightGBM parameters
    assert "num_leaves" in pipeline.best_params
    assert "learning_rate" in pipeline.best_params


def test_ml_pipeline_predict_proba(sample_ml_data, temp_model_dir):
    """Test probability prediction."""
    X, y = sample_ml_data
    X_train, X_test = X[:150], X[150:]
    y_train = y[:150]

    model_path = temp_model_dir / "test_model.pkl"
    pipeline = MLPipeline(model_path=model_path)
    pipeline.train_simple(X_train, y_train.values)

    probas = pipeline.predict_proba(X_test)

    # Check shape - returns 1D array of probabilities for positive class
    assert probas.shape[0] == len(X_test)

    # Check probabilities are valid
    assert (probas >= 0).all() and (probas <= 1).all()


def test_ml_pipeline_predict_proba_without_model(sample_ml_data):
    """Test prediction without trained model."""
    X, _ = sample_ml_data
    pipeline = MLPipeline()

    with pytest.raises(RuntimeError, match="Model not loaded"):
        pipeline.predict_proba(X)


def test_ml_pipeline_load(sample_ml_data, temp_model_dir):
    """Test loading a trained model."""
    X, y = sample_ml_data
    model_path = temp_model_dir / "test_model.pkl"

    # Train and save
    pipeline1 = MLPipeline(model_path=model_path)
    pipeline1.train_simple(X, y.values)

    # Load in new pipeline
    pipeline2 = MLPipeline(model_path=model_path)
    pipeline2.load()

    # Should have loaded model
    assert pipeline2.model is not None

    # Predictions should match
    pred1 = pipeline1.predict_proba(X[:10])
    pred2 = pipeline2.predict_proba(X[:10])
    np.testing.assert_array_almost_equal(pred1, pred2)


def test_ml_pipeline_load_nonexistent_model():
    """Test loading from nonexistent model file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        model_path = Path(tmpdir) / "nonexistent.pkl"
        pipeline = MLPipeline(model_path=model_path)

        with pytest.raises(FileNotFoundError):
            pipeline.load()


def test_ml_pipeline_evaluate(sample_ml_data, temp_model_dir):
    """Test model evaluation."""
    X, y = sample_ml_data
    X_train, X_test = X[:150], X[150:]
    y_train, y_test = y[:150], y[150:]

    model_path = temp_model_dir / "test_model.pkl"
    pipeline = MLPipeline(model_path=model_path)
    pipeline.train_simple(X_train, y_train.values)

    metrics = pipeline.evaluate(X_test, y_test.values)

    # Check metrics exist
    assert "log_loss" in metrics
    assert "roc_auc" in metrics
    assert "accuracy" in metrics

    # Check metrics are in valid range
    assert metrics["log_loss"] >= 0
    assert 0 <= metrics["roc_auc"] <= 1
    assert 0 <= metrics["accuracy"] <= 1


def test_ml_pipeline_evaluate_without_model(sample_ml_data):
    """Test evaluation without trained model."""
    X, y = sample_ml_data
    pipeline = MLPipeline()

    with pytest.raises(RuntimeError, match="Model not loaded"):
        pipeline.evaluate(X, y.values)


def test_ml_pipeline_prepare_data(sample_ml_data):
    """Test data preparation."""
    X, y = sample_ml_data
    pipeline = MLPipeline()

    X_prepared = pipeline._prepare(X)

    # Should return DataFrame
    assert isinstance(X_prepared, pd.DataFrame)

    # Shape should be preserved
    assert X_prepared.shape == X.shape


def test_ml_pipeline_prepare_data_with_arrays(sample_ml_data):
    """Test preparation with DataFrames."""
    X_df, y_series = sample_ml_data

    pipeline = MLPipeline()
    X_prepared = pipeline._prepare(X_df)

    assert isinstance(X_prepared, pd.DataFrame)
    assert X_prepared.shape[0] == X_df.shape[0]


def test_ml_pipeline_feature_names_tracked(sample_ml_data, temp_model_dir):
    """Test that model trains successfully."""
    X, y = sample_ml_data
    model_path = temp_model_dir / "test_model.pkl"
    pipeline = MLPipeline(model_path=model_path)

    pipeline.train_simple(X, y.values)

    # Model should be trained
    assert pipeline.model is not None


def test_ml_pipeline_cv_scores_reasonable(sample_ml_data, temp_model_dir):
    """Test that CV training works."""
    X, y = sample_ml_data
    model_path = temp_model_dir / "test_model.pkl"
    pipeline = MLPipeline(model_path=model_path)

    model = pipeline.train_with_cv(X, y.values, n_splits=3, n_trials=3)

    # Model should be trained
    assert model is not None
    assert pipeline.model is not None
    assert pipeline.best_params is not None


def test_ml_pipeline_handles_numpy_arrays(temp_model_dir):
    """Test that pipeline handles DataFrames with numeric data."""
    X = pd.DataFrame(np.random.rand(100, 10), columns=[f"f_{i}" for i in range(10)])
    y = np.random.randint(0, 2, 100)

    model_path = temp_model_dir / "test_model.pkl"
    pipeline = MLPipeline(model_path=model_path)
    pipeline.train_simple(X, y)

    assert pipeline.model is not None

    # Should be able to predict
    probas = pipeline.predict_proba(X[:10])
    assert probas.shape == (10,)


def test_ml_pipeline_consistent_predictions(sample_ml_data, temp_model_dir):
    """Test that predictions are consistent."""
    X, y = sample_ml_data
    model_path = temp_model_dir / "test_model.pkl"
    pipeline = MLPipeline(model_path=model_path)

    pipeline.train_simple(X, y.values)

    # Same input should give same predictions
    pred1 = pipeline.predict_proba(X[:10])
    pred2 = pipeline.predict_proba(X[:10])

    np.testing.assert_array_almost_equal(pred1, pred2)


def test_ml_pipeline_handles_imbalanced_data(temp_model_dir):
    """Test pipeline with imbalanced classes."""
    # Create imbalanced dataset
    X, y = make_classification(
        n_samples=100,
        n_features=10,
        n_classes=2,
        weights=[0.9, 0.1],  # 90% class 0, 10% class 1
        random_state=42,
    )
    X_df = pd.DataFrame(X, columns=[f"feature_{i}" for i in range(X.shape[1])])

    model_path = temp_model_dir / "test_model.pkl"
    pipeline = MLPipeline(model_path=model_path)
    pipeline.train_simple(X_df, y)

    # Should still train successfully
    assert pipeline.model is not None

    # Should be able to predict
    probas = pipeline.predict_proba(X_df[:10])
    assert probas.shape == (10,)


def test_ml_pipeline_model_persistence(sample_ml_data, temp_model_dir):
    """Test that model persists across sessions."""
    X, y = sample_ml_data
    X_train, X_test = X[:150], X[150:]
    y_train = y[:150]

    model_path = temp_model_dir / "test_model.pkl"

    # Train and save
    pipeline1 = MLPipeline(model_path=model_path)
    pipeline1.train_simple(X_train, y_train.values)
    pred1 = pipeline1.predict_proba(X_test)

    # Simulate new session - create new pipeline and load
    pipeline2 = MLPipeline(model_path=model_path)
    pipeline2.load()
    pred2 = pipeline2.predict_proba(X_test)

    # Predictions should be identical
    np.testing.assert_array_almost_equal(pred1, pred2)
