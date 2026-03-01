"""Unit tests for base_pool.py helper functions."""

from unittest.mock import AsyncMock, Mock

import pytest

from omni_cache.core.interfaces.base_pool import _async_borrow_logic, _sync_borrow_logic


class TestSyncBorrowLogic:
    """Test cases for _sync_borrow_logic function."""

    def test_successful_borrow_and_return(self):
        """Test successful object borrowing and returning."""
        # Arrange
        test_obj = "test_object"
        get_func = Mock(return_value=test_obj)
        put_func = Mock(return_value=True)
        timeout = 10.0

        # Act
        with _sync_borrow_logic(get_func, put_func, timeout) as borrowed_obj:
            assert borrowed_obj == test_obj

        # Assert
        get_func.assert_called_once_with(timeout)
        put_func.assert_called_once_with(test_obj, None)

    def test_no_object_available_raises_runtime_error(self):
        """Test that RuntimeError is raised when no object is available."""
        # Arrange
        get_func = Mock(return_value=None)
        put_func = Mock()
        timeout = 5.0

        # Act & Assert
        with pytest.raises(RuntimeError, match="No object available from pool"):
            with _sync_borrow_logic(get_func, put_func, timeout):
                pass

        # Assert
        get_func.assert_called_once_with(timeout)
        put_func.assert_not_called()

    def test_exception_in_context_still_returns_object(self):
        """Test that object is returned to pool even if exception occurs in context."""
        # Arrange
        test_obj = "test_object"
        get_func = Mock(return_value=test_obj)
        put_func = Mock(return_value=True)
        timeout = None

        # Act & Assert
        with pytest.raises(ValueError, match="test exception"):
            with _sync_borrow_logic(get_func, put_func, timeout) as borrowed_obj:
                assert borrowed_obj == test_obj
                raise ValueError("test exception")

        # Assert
        get_func.assert_called_once_with(timeout)
        put_func.assert_called_once_with(test_obj, None)

    def test_with_none_timeout(self):
        """Test borrowing with None timeout."""
        # Arrange
        test_obj = 42
        get_func = Mock(return_value=test_obj)
        put_func = Mock(return_value=True)

        # Act
        with _sync_borrow_logic(get_func, put_func, None) as borrowed_obj:
            assert borrowed_obj == test_obj

        # Assert
        get_func.assert_called_once_with(None)
        put_func.assert_called_once_with(test_obj, None)

    def test_with_zero_timeout(self):
        """Test borrowing with zero timeout."""
        # Arrange
        test_obj = {"key": "value"}
        get_func = Mock(return_value=test_obj)
        put_func = Mock(return_value=True)

        # Act
        with _sync_borrow_logic(get_func, put_func, 0.0) as borrowed_obj:
            assert borrowed_obj == test_obj

        # Assert
        get_func.assert_called_once_with(0.0)
        put_func.assert_called_once_with(test_obj, None)

    def test_put_function_failure_does_not_affect_context(self):
        """Test that put function failure doesn't affect the context manager."""
        # Arrange
        test_obj = "test_object"
        get_func = Mock(return_value=test_obj)
        put_func = Mock(return_value=False)  # Simulating failure to put back
        timeout = 1.0

        # Act
        with _sync_borrow_logic(get_func, put_func, timeout) as borrowed_obj:
            assert borrowed_obj == test_obj

        # Assert
        get_func.assert_called_once_with(timeout)
        put_func.assert_called_once_with(test_obj, None)

    def test_get_function_called_with_exact_timeout(self):
        """Test that get function is called with the exact timeout value."""
        # Arrange
        test_obj = "test_object"
        get_func = Mock(return_value=test_obj)
        put_func = Mock(return_value=True)
        timeout = 3.14159

        # Act
        with _sync_borrow_logic(get_func, put_func, timeout):
            pass

        # Assert
        get_func.assert_called_once_with(timeout)


class TestAsyncBorrowLogic:
    """Test cases for _async_borrow_logic function."""

    @pytest.mark.asyncio
    async def test_successful_async_borrow_and_return(self):
        """Test successful async object borrowing and returning."""
        # Arrange
        test_obj = "async_test_object"
        get_func = AsyncMock(return_value=test_obj)
        put_func = AsyncMock(return_value=True)
        timeout = 10.0

        # Act
        async with _async_borrow_logic(get_func, put_func, timeout) as borrowed_obj:
            assert borrowed_obj == test_obj

        # Assert
        get_func.assert_called_once_with(timeout)
        put_func.assert_called_once_with(test_obj, None)

    @pytest.mark.asyncio
    async def test_async_no_object_available_raises_runtime_error(self):
        """Test that RuntimeError is raised when no async object is available."""
        # Arrange
        get_func = AsyncMock(return_value=None)
        put_func = AsyncMock()
        timeout = 5.0

        # Act & Assert
        with pytest.raises(RuntimeError, match="No object available from pool"):
            async with _async_borrow_logic(get_func, put_func, timeout):
                pass

        # Assert
        get_func.assert_called_once_with(timeout)
        put_func.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_exception_in_context_still_returns_object(self):
        """Test that async object is returned to pool even if exception occurs."""
        # Arrange
        test_obj = "async_test_object"
        get_func = AsyncMock(return_value=test_obj)
        put_func = AsyncMock(return_value=True)
        timeout = None

        # Act & Assert
        with pytest.raises(ValueError, match="async test exception"):
            async with _async_borrow_logic(get_func, put_func, timeout) as borrowed_obj:
                assert borrowed_obj == test_obj
                raise ValueError("async test exception")

        # Assert
        get_func.assert_called_once_with(timeout)
        put_func.assert_called_once_with(test_obj, None)

    @pytest.mark.asyncio
    async def test_async_with_none_timeout(self):
        """Test async borrowing with None timeout."""
        # Arrange
        test_obj = [1, 2, 3]
        get_func = AsyncMock(return_value=test_obj)
        put_func = AsyncMock(return_value=True)

        # Act
        async with _async_borrow_logic(get_func, put_func, None) as borrowed_obj:
            assert borrowed_obj == test_obj

        # Assert
        get_func.assert_called_once_with(None)
        put_func.assert_called_once_with(test_obj, None)

    @pytest.mark.asyncio
    async def test_async_with_coroutine_functions(self):
        """Test async borrowing with actual coroutine functions."""
        # Arrange
        test_obj = "coroutine_object"

        async def async_get_func(timeout: float | None):
            return test_obj

        async def async_put_func(obj, timeout: float | None):
            return True

        timeout = 2.0

        # Act
        async with _async_borrow_logic(async_get_func, async_put_func, timeout) as borrowed_obj:
            assert borrowed_obj == test_obj

    @pytest.mark.asyncio
    async def test_async_coroutine_get_returns_none(self):
        """Test async borrowing when coroutine get function returns None."""

        # Arrange
        async def async_get_func(timeout: float | None):
            return None

        async def async_put_func(obj, timeout: float | None):
            return True

        timeout = 1.0

        # Act & Assert
        with pytest.raises(RuntimeError, match="No object available from pool"):
            async with _async_borrow_logic(async_get_func, async_put_func, timeout):
                pass

    @pytest.mark.asyncio
    async def test_async_exception_in_coroutine_context(self):
        """Test exception handling in async context with coroutines."""
        # Arrange
        test_obj = "exception_test_object"

        async def async_get_func(timeout: float | None):
            return test_obj

        async def async_put_func(obj, timeout: float | None):
            assert obj == test_obj
            return True

        timeout = 3.0

        # Act & Assert
        with pytest.raises(RuntimeError, match="async context exception"):
            async with _async_borrow_logic(async_get_func, async_put_func, timeout) as borrowed_obj:
                assert borrowed_obj == test_obj
                raise RuntimeError("async context exception")


class TestBorrowLogicEdgeCases:
    """Test edge cases and unusual scenarios for both functions."""

    def test_sync_with_complex_object(self):
        """Test sync borrowing with complex object types."""

        # Arrange
        class ComplexObject:
            def __init__(self, value):
                self.value = value

            def __eq__(self, other):
                return isinstance(other, ComplexObject) and self.value == other.value

        test_obj = ComplexObject("complex_value")
        get_func = Mock(return_value=test_obj)
        put_func = Mock(return_value=True)

        # Act
        with _sync_borrow_logic(get_func, put_func, 1.0) as borrowed_obj:
            assert borrowed_obj.value == "complex_value"

        # Assert
        put_func.assert_called_once_with(test_obj, None)

    @pytest.mark.asyncio
    async def test_async_with_complex_object(self):
        """Test async borrowing with complex object types."""

        # Arrange
        class AsyncComplexObject:
            def __init__(self, value):
                self.value = value

        test_obj = AsyncComplexObject("async_complex_value")

        async def async_get_func(timeout: float | None):
            return test_obj

        async def async_put_func(obj, timeout: float | None):
            assert obj.value == "async_complex_value"
            return True

        # Act
        async with _async_borrow_logic(async_get_func, async_put_func, 2.0) as borrowed_obj:
            assert borrowed_obj.value == "async_complex_value"

    def test_sync_put_always_called_with_none_timeout(self):
        """Test that put function is always called with None timeout."""
        # Arrange
        test_obj = "timeout_test"
        get_func = Mock(return_value=test_obj)
        put_func = Mock(return_value=True)

        # Act
        with _sync_borrow_logic(get_func, put_func, 5.0):
            pass

        # Assert that put is called with None timeout regardless of get timeout
        put_func.assert_called_once_with(test_obj, None)

    @pytest.mark.asyncio
    async def test_async_put_always_called_with_none_timeout(self):
        """Test that async put function is always called with None timeout."""
        # Arrange
        test_obj = "async_timeout_test"

        async def async_get_func(timeout: float | None):
            return test_obj

        async def async_put_func(obj, timeout: float | None):
            assert timeout is None
            return True

        # Act
        async with _async_borrow_logic(async_get_func, async_put_func, 7.0):
            pass


@pytest.fixture
def mock_object():
    """Fixture providing a mock object for testing."""
    return "fixture_test_object"


@pytest.fixture
def mock_get_func(mock_object):
    """Fixture providing a mock get function."""
    return Mock(return_value=mock_object)


@pytest.fixture
def mock_put_func():
    """Fixture providing a mock put function."""
    return Mock(return_value=True)


class TestBorrowLogicWithFixtures:
    """Test borrow logic using pytest fixtures."""

    def test_sync_borrow_with_fixtures(self, mock_get_func, mock_put_func, mock_object):
        """Test sync borrowing using fixtures."""
        with _sync_borrow_logic(mock_get_func, mock_put_func, 1.0) as borrowed_obj:
            assert borrowed_obj == mock_object

        mock_get_func.assert_called_once_with(1.0)
        mock_put_func.assert_called_once_with(mock_object, None)

    @pytest.mark.asyncio
    async def test_async_borrow_with_fixtures(self, mock_object):
        """Test async borrowing using fixtures."""

        async def async_get_func(timeout: float | None):
            return mock_object

        async def async_put_func(obj, timeout: float | None):
            return True

        async with _async_borrow_logic(async_get_func, async_put_func, 2.0) as borrowed_obj:
            assert borrowed_obj == mock_object
