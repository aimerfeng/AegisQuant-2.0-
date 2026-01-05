"""
Pytest configuration and fixtures for Titan-Quant tests.
"""
import pytest
from pathlib import Path


@pytest.fixture
def project_root() -> Path:
    """Return the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def test_data_dir(project_root: Path) -> Path:
    """Return the test data directory."""
    test_data = project_root / "tests" / "data"
    test_data.mkdir(parents=True, exist_ok=True)
    return test_data


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Return a temporary directory for test artifacts."""
    return tmp_path
