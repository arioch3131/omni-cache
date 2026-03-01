from omni_cache.adapters.smartpool import (
    __description__,
    __version__,
    get_adapter_info,
    is_available,
)


def test_is_available():
    """Test that is_available returns a boolean."""
    assert isinstance(is_available(), bool)


def test_get_adapter_info():
    """Test that get_adapter_info returns correct information."""
    info = get_adapter_info()
    assert isinstance(info, dict)
    assert info["name"] == "SmartPool"
    assert info["version"] == __version__
    assert info["description"] == __description__
    assert isinstance(info["available"], bool)
    assert "interfaces" in info
    assert "backend" in info
    assert "features" in info
