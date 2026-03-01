Installation
============

This guide covers installing Omni-Cache and its optional dependencies.

Requirements
------------

**Python Version**
  - Python 3.8 or higher
  - Tested on Python 3.8, 3.9, 3.10, 3.11, and 3.12

**Operating Systems**
  - Linux (recommended)
  - macOS
  - Windows

Basic Installation
------------------

Install Omni-Cache using pip:

.. code-block:: bash

   pip install omni_cache

This installs the core functionality with the built-in memory adapter. No external dependencies required.

Optional Dependencies
---------------------

Install additional backends as needed:

Redis Support
~~~~~~~~~~~~~

For Redis-based distributed caching:

.. code-block:: bash

   pip install omni_cache[redis]

This installs:
  - ``redis`` - Redis Python client

SmartPool Support
~~~~~~~~~~~~~~~~~

For advanced object pooling:

.. code-block:: bash

   pip install omni_cache[smartpool]

This installs:
  - ``smartpool`` - Advanced object pooling library

All Optional Dependencies
~~~~~~~~~~~~~~~~~~~~~~~~~

To install all optional dependencies:

.. code-block:: bash

   pip install omni_cache[all]

Development Installation
------------------------

For development and testing:

.. code-block:: bash

   # Clone repository (if working from source)
   git clone <repository-url>
   cd omni-cache

   # Create virtual environment
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # or
   venv\\Scripts\\activate     # Windows

   # Install in development mode with all dependencies
   pip install -e .[dev]

This installs all optional dependencies plus development tools:
  - Testing: ``pytest``, ``pytest-cov``, ``pytest-mock``
  - Code quality: ``black``, ``isort``, ``flake8``, ``mypy``
  - Documentation: ``sphinx``, ``sphinx-rtd-theme``

Verification
------------

Verify your installation:

.. code-block:: python

   import omni_cache
   print(f"Omni-Cache version: {omni_cache.__version__}")
   
   # Check available backends
   from omni_cache import discover_backends
   backends = discover_backends()
   print(f"Available backends: {list(backends.keys())}")

You should see output like:

.. code-block:: text

   Omni-Cache version: 1.0.0
   Available backends: ['memory', 'redis', 'smartpool']

Docker Installation
-------------------

Using Docker for testing with external services:

.. code-block:: dockerfile

   FROM python:3.11-slim

   # Install Omni-Cache with all dependencies
   RUN pip install omni_cache[all]

   # Copy your application
   COPY . /app
   WORKDIR /app

   CMD ["python", "your_app.py"]

Docker Compose Example
~~~~~~~~~~~~~~~~~~~~~~

For testing with Redis:

.. code-block:: yaml

   version: '3.8'
   services:
     app:
       build: .
       depends_on:
         - redis
       environment:
         - OMNI_CACHE_ADAPTERS_REDIS_EXTRA_CONFIG_HOST=redis
     
     redis:
       image: redis:7-alpine
       ports:
         - "6379:6379"

Conda Installation
------------------

If you prefer Conda:

.. code-block:: bash

   # Create environment
   conda create -n omni-cache python=3.11
   conda activate omni-cache
   
   # Install via pip (not available on conda-forge yet)
   pip install omni_cache[all]

Troubleshooting
---------------

Common Issues
~~~~~~~~~~~~~

**ImportError for optional dependencies**

If you see import errors for Redis or SmartPool:

.. code-block:: bash

   # Install the missing dependency
   pip install redis  # for Redis support
   pip install smartpool  # for SmartPool support

**Permission denied on installation**

Use user installation:

.. code-block:: bash

   pip install --user omni_cache[all]

**Old version installed**

Force upgrade:

.. code-block:: bash

   pip install --upgrade omni_cache[all]

Platform-Specific Notes
~~~~~~~~~~~~~~~~~~~~~~~

**Windows**

On Windows, you may need to install Visual C++ build tools for some dependencies.

**Alpine Linux**

For Alpine Linux, you may need additional packages:

.. code-block:: bash

   apk add --no-cache gcc musl-dev libffi-dev

**macOS**

On macOS with Apple Silicon (M1/M2), ensure you're using a compatible Python version:

.. code-block:: bash

   # Use Python from Homebrew for best compatibility
   brew install python@3.11
   /opt/homebrew/bin/python3.11 -m pip install omni_cache[all]

Next Steps
----------

After installation:

1. Try the :doc:`../quickstart` guide
2. Read about :doc:`basic_usage`
3. Learn about :doc:`configuration`
4. Explore the :doc:`../examples/index`