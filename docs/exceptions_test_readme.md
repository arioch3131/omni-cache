# Omni-Cache Exception System Tests

This directory contains comprehensive unit tests for the omni-cache exception system. The test suite covers all exception classes, utility functions, and edge cases to ensure robust error handling throughout the system.

## Test Structure

### Core Test Files

- **`test_omni_cache_error.py`** - Tests for the base `OmniCacheError` class
- **`test_adapter_exceptions.py`** - Tests for adapter-related exceptions
- **`test_cache_exceptions.py`** - Tests for cache-specific exceptions
- **`test_config_exceptions.py`** - Tests for configuration-related exceptions
- **`test_connection_exceptions.py`** - Tests for connection-related exceptions
- **`test_factory_exceptions.py`** - Tests for factory-related exceptions
- **`test_operation_pool_serialization_exceptions.py`** - Tests for operation, pool, and serialization exceptions
- **`test_other_and_utility_exceptions.py`** - Tests for other exceptions and utility functions

### Advanced Test Files

- **`test_exceptions_integration.py`** - Integration tests for exception system interactions
- **`test_exceptions_edge_cases.py`** - Edge cases and stress tests
- **`test_exceptions_compatibility.py`** - Compatibility and regression tests

### Configuration

- **`conftest.py`** - Pytest configuration with fixtures and test utilities

## Running the Tests

### Run All Exception Tests
```bash
# Run all exception tests
pytest tests/unit/test_exceptions/

# Run with verbose output
pytest -v tests/unit/test_exceptions/

# Run with coverage
pytest --cov=omni_cache.core.exceptions tests/unit/test_exceptions/
```

### Run Specific Test Categories
```bash
# Run only basic unit tests
pytest tests/unit/test_exceptions/test_*_exceptions.py

# Run only integration tests
pytest -m integration tests/unit/test_exceptions/

# Run only edge case tests
pytest -m edge_case tests/unit/test_exceptions/

# Run only performance tests
pytest -m performance tests/unit/test_exceptions/

# Run only unicode/i18n tests
pytest -m unicode tests/unit/test_exceptions/
```

### Run Specific Test Files
```bash
# Test base exception class
pytest tests/unit/test_exceptions/test_omni_cache_error.py

# Test adapter exceptions
pytest tests/unit/test_exceptions/test_adapter_exceptions.py

# Test utility functions
pytest tests/unit/test_exceptions/test_other_and_utility_exceptions.py

# Test integration scenarios
pytest tests/unit/test_exceptions/test_exceptions_integration.py
```

## Test Categories and Markers

### Pytest Markers

- **`@pytest.mark.integration`** - Integration tests that test interactions between components
- **`@pytest.mark.performance`** - Performance and stress tests
- **`@pytest.mark.slow`** - Tests that take longer to run
- **`@pytest.mark.unicode`** - Tests for unicode/internationalization support
- **`@pytest.mark.edge_case`** - Edge case and boundary condition tests
- **`@pytest.mark.compatibility`** - Cross-platform and backward compatibility tests

### Skip Markers for Conditional Tests

Some tests may be skipped based on environment conditions:
- Python version requirements
- Available system resources
- Platform-specific features

## Test Coverage

The test suite aims for comprehensive coverage of:

### Exception Classes (100% coverage target)
- All exception constructors and parameter combinations
- Inheritance hierarchy and MRO
- String representations (`__str__` and `__repr__`)
- Property access and modification
- Edge cases and boundary conditions

### Utility Functions (100% coverage target)
- `handle_and_wrap_exception()` - Exception wrapping logic
- `exception_context()` - Context manager for exception handling
- `is_retriable_error()` - Error categorization
- `get_exception_summary()` - Exception summarization

### Integration Scenarios
- Exception chaining and cause preservation
- Cross-exception-type interactions
- Real-world failure scenarios
- Concurrent exception handling

### Edge Cases and Stress Tests
- Memory pressure and resource exhaustion
- Unicode and internationalization
- Platform-specific behavior
- Performance under load
- Thread safety and concurrency

## Key Test Patterns

### 1. Exception Structure Validation
```python
def test_exception_structure(self):
    error = SomeException("test")
    assert isinstance(error, OmniCacheError)
    assert hasattr(error, 'message')
    assert hasattr(error, 'details')
    assert hasattr(error, 'timestamp')
    assert hasattr(error, 'cause')
```

### 2. Parameter Validation Testing
```python
def test_all_parameter_combinations(self):
    # Test with all parameters
    error = ExceptionClass(param1, param2, param3)
    
    # Test with minimal parameters
    error = ExceptionClass(param1)
    
    # Test with None values
    error = ExceptionClass(param1, None)
```

### 3. Inheritance Testing
```python
def test_inheritance_chain(self):
    error = SpecificException("test")
    assert isinstance(error, BaseException)
    assert isinstance(error, OmniCacheError)
    
    # Test MRO
    mro = type(error).__mro__
    assert SpecificException in mro
    assert BaseException in mro
    assert OmniCacheError in mro
```

### 4. Utility Function Testing
```python
def test_utility_function_with_all_exception_types(self):
    for exception_class, args in all_exception_classes.items():
        exception = exception_class(*args)
        result = utility_function(exception)
        assert expected_condition(result)
```

## Common Test Fixtures

### Available Fixtures (from conftest.py)

- **`sample_details`** - Standard details dictionary for testing
- **`sample_cause`** - Standard exception cause for testing
- **`mock_time`** - Mocked time for consistent timestamps
- **`all_exception_classes`** - Dictionary of all exception classes with constructor args
- **`base_exception_classes`** - Mapping of base classes to derived classes
- **`retriable_exceptions`** - List of exceptions that should be retriable
- **`non_retriable_exceptions`** - List of exceptions that should not be retriable
- **`unicode_test_data`** - Unicode strings for i18n testing
- **`performance_test_data`** - Large data sets for performance testing

### Using Fixtures
```python
def test_with_fixture(self, all_exception_classes, sample_details):
    for name, (exc_class, args) in all_exception_classes.items():
        error = exc_class(*args)
        error.details.update(sample_details)
        # Test logic here
```

## Writing New Tests

### Guidelines for Adding Tests

1. **Follow the existing pattern** - Look at similar test files for structure
2. **Use appropriate markers** - Mark tests with relevant pytest markers
3. **Test all parameter combinations** - Include tests for edge cases
4. **Use fixtures** - Leverage existing fixtures from conftest.py
5. **Add docstrings** - Document what each test validates
6. **Test both success and failure paths** - Don't just test happy paths

### Test Naming Convention
```python
class TestExceptionClassName:
    def test_basic_initialization(self):
        """Test basic exception creation."""
        
    def test_initialization_with_all_parameters(self):
        """Test exception creation with all possible parameters."""
        
    def test_edge_case_description(self):
        """Test specific edge case scenario."""
        
    def test_inheritance_behavior(self):
        """Test inheritance and MRO behavior."""
```

### Adding New Exception Classes

When adding a new exception class to the system:

1. **Create unit tests** in the appropriate test file
2. **Add to fixtures** - Update `all_exception_classes` in conftest.py
3. **Test inheritance** - Ensure proper base class inheritance
4. **Test utility functions** - Verify compatibility with utility functions
5. **Add integration tests** - Test interactions with other exceptions

## Debugging Failed Tests

### Common Test Failures

1. **Missing attributes** - Exception class doesn't have expected attributes
2. **Wrong inheritance** - Exception doesn't inherit from expected base class
3. **Parameter handling** - Constructor doesn't handle parameters correctly
4. **String representation** - `__str__` or `__repr__` methods have issues
5. **Unicode issues** - Problems with non-ASCII characters

### Debugging Commands
```bash
# Run with verbose output to see detailed failure information
pytest -v -s tests/unit/test_exceptions/test_specific_file.py::TestClass::test_method

# Run with pdb debugger on failure
pytest --pdb tests/unit/test_exceptions/test_specific_file.py

# Run with traceback on failure
pytest --tb=long tests/unit/test_exceptions/test_specific_file.py

# Run with coverage to see which lines are not tested
pytest --cov=omni_cache.core.exceptions --cov-report=html tests/unit/test_exceptions/
```

## Performance Considerations

### Test Performance Guidelines

- **Mark slow tests** - Use `@pytest.mark.slow` for tests taking >1 second
- **Use appropriate data sizes** - Don't create unnecessarily large test data
- **Mock expensive operations** - Use mocks for I/O or network operations
- **Parallel execution** - Tests should be safe for parallel execution with pytest-xdist

### Running Performance Tests
```bash
# Skip slow tests for faster feedback
pytest -m "not slow" tests/unit/test_exceptions/

# Run only performance tests
pytest -m performance tests/unit/test_exceptions/

# Run with timing information
pytest --durations=10 tests/unit/test_exceptions/
```

## Maintenance Notes

When adding new tests:

1. **Run the full test suite** before submitting
2. **Add appropriate documentation** for complex test scenarios
3. **Follow the established patterns** in existing tests
4. **Ensure cross-platform compatibility** 
5. **Update this README** if adding new test categories or patterns

## Troubleshooting

### Common Issues

**Import Errors**: Ensure `omni_cache` package is installed or PYTHONPATH is set correctly
```bash
pip install -e .  # Install in development mode
# OR
export PYTHONPATH=$PWD/src:$PYTHONPATH
```

**Missing Dependencies**: Install test dependencies
```bash
pip install -e ".[dev]"  # Install with development dependencies
```

**Platform Issues**: Some tests may behave differently on different platforms
```bash
pytest --platform-specific tests/unit/test_exceptions/test_exceptions_compatibility.py
```

**Memory Issues**: For large-scale stress tests
```bash
pytest -m "not slow and not performance" tests/unit/test_exceptions/
```

For more information, see the main omni-cache documentation.
