"""Tests for ML model wrapper."""
import pytest
import numpy as np
import tempfile
from pathlib import Path
from sklearn.datasets import make_classification
from src.model import ModelWrapper


@pytest.fixture
def sample_data():
    """Generate sample classification data."""
    X, y = make_classification(
        n_samples=100, n_features=10, n_informative=5, n_redundant=2, random_state=42
    )
    return X, y


@pytest.fixture
def temp_model_path():
    """Create temporary path for model storage."""
    # Create path but don't create file yet
    temp_dir = tempfile.mkdtemp()
    path = Path(temp_dir) / "test_model.pkl"
    yield path
    # Cleanup
    if path.exists():
        path.unlink()
    Path(temp_dir).rmdir()


def test_model_wrapper_initialization(temp_model_path):
    """Test ModelWrapper initialization."""
    wrapper = ModelWrapper(model_path=temp_model_path)
    assert wrapper.model_path == temp_model_path
    assert wrapper.model is None


def test_model_wrapper_train(sample_data, temp_model_path):
    """Test model training."""
    X, y = sample_data
    wrapper = ModelWrapper(model_path=temp_model_path)

    wrapper.train(X, y)

    # Model should be trained
    assert wrapper.model is not None

    # Model file should exist
    assert temp_model_path.exists()


def test_model_wrapper_train_custom_params(sample_data, temp_model_path):
    """Test model training with custom parameters."""
    X, y = sample_data
    wrapper = ModelWrapper(model_path=temp_model_path)

    wrapper.train(X, y, n_estimators=50, max_depth=5)

    assert wrapper.model is not None
    assert wrapper.model.n_estimators == 50
    assert wrapper.model.max_depth == 5


def test_model_wrapper_save_without_model(temp_model_path):
    """Test saving when no model exists."""
    wrapper = ModelWrapper(model_path=temp_model_path)

    with pytest.raises(RuntimeError, match="No model to save"):
        wrapper.save()


def test_model_wrapper_save_custom_path(sample_data):
    """Test saving model to custom path."""
    X, y = sample_data
    wrapper = ModelWrapper()
    wrapper.train(X, y)

    with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
        custom_path = Path(f.name)

    try:
        wrapper.save(path=custom_path)
        assert custom_path.exists()
    finally:
        if custom_path.exists():
            custom_path.unlink()


def test_model_wrapper_load(sample_data, temp_model_path):
    """Test model loading."""
    X, y = sample_data

    # Train and save model
    wrapper1 = ModelWrapper(model_path=temp_model_path)
    wrapper1.train(X, y)

    # Load model in new wrapper
    wrapper2 = ModelWrapper(model_path=temp_model_path)
    wrapper2.load()

    assert wrapper2.model is not None

    # Predictions should match
    pred1 = wrapper1.predict(X[:5])
    pred2 = wrapper2.predict(X[:5])
    np.testing.assert_array_equal(pred1, pred2)


def test_model_wrapper_load_nonexistent_file(temp_model_path):
    """Test loading from nonexistent file."""
    wrapper = ModelWrapper(model_path=temp_model_path)

    with pytest.raises(FileNotFoundError, match="Model file not found"):
        wrapper.load()


def test_model_wrapper_predict(sample_data, temp_model_path):
    """Test model prediction."""
    X, y = sample_data
    wrapper = ModelWrapper(model_path=temp_model_path)
    wrapper.train(X, y)

    predictions = wrapper.predict(X[:10])

    assert isinstance(predictions, np.ndarray)
    assert len(predictions) == 10
    assert predictions.dtype in [np.int64, np.int32]


def test_model_wrapper_predict_without_model(temp_model_path):
    """Test prediction without trained model."""
    wrapper = ModelWrapper(model_path=temp_model_path)
    X = np.random.rand(10, 5)

    with pytest.raises(RuntimeError, match="Model not loaded"):
        wrapper.predict(X)


def test_model_wrapper_predict_proba(sample_data, temp_model_path):
    """Test probability prediction."""
    X, y = sample_data
    wrapper = ModelWrapper(model_path=temp_model_path)
    wrapper.train(X, y)

    probas = wrapper.predict_proba(X[:10])

    assert isinstance(probas, np.ndarray)
    assert probas.shape[0] == 10
    assert probas.shape[1] == 2  # Binary classification

    # Probabilities should sum to 1
    np.testing.assert_array_almost_equal(probas.sum(axis=1), np.ones(10))

    # Probabilities should be in [0, 1]
    assert (probas >= 0).all() and (probas <= 1).all()


def test_model_wrapper_predict_proba_without_model(temp_model_path):
    """Test probability prediction without trained model."""
    wrapper = ModelWrapper(model_path=temp_model_path)
    X = np.random.rand(10, 5)

    with pytest.raises(RuntimeError, match="Model not loaded"):
        wrapper.predict_proba(X)


def test_model_wrapper_feature_importance(sample_data, temp_model_path):
    """Test feature importance extraction."""
    X, y = sample_data
    wrapper = ModelWrapper(model_path=temp_model_path)
    wrapper.train(X, y)

    importances = wrapper.get_feature_importance()

    assert importances is not None
    assert isinstance(importances, np.ndarray)
    assert len(importances) == X.shape[1]

    # Importances should be non-negative and sum to ~1
    assert (importances >= 0).all()
    np.testing.assert_almost_equal(importances.sum(), 1.0, decimal=5)


def test_model_wrapper_feature_importance_without_model(temp_model_path):
    """Test feature importance without trained model."""
    wrapper = ModelWrapper(model_path=temp_model_path)
    importances = wrapper.get_feature_importance()
    assert importances is None


def test_model_wrapper_full_workflow(sample_data, temp_model_path):
    """Test complete train-save-load-predict workflow."""
    X, y = sample_data
    X_train, X_test = X[:80], X[80:]
    y_train, _ = y[:80], y[80:]  # y_test is not used in this test

    # Train and save
    wrapper1 = ModelWrapper(model_path=temp_model_path)
    wrapper1.train(X_train, y_train)

    # Load and predict
    wrapper2 = ModelWrapper(model_path=temp_model_path)
    wrapper2.load()

    predictions = wrapper2.predict(X_test)
    probas = wrapper2.predict_proba(X_test)

    assert len(predictions) == len(X_test)
    assert probas.shape[0] == len(X_test)

    # Predictions should match probability argmax
    np.testing.assert_array_equal(predictions, probas.argmax(axis=1))
