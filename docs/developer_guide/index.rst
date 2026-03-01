Developer Guide
===============

This section targets users extending Omni-Cache internals.

.. toctree::
   :maxdepth: 2
   :caption: Developer Guide:

   architecture
   custom_adapters
   ../adapter_creation
   testing
   internals

Quick Start for Implementers
----------------------------

.. code-block:: bash

   git clone <repository-url>
   cd omni-cache
   python -m venv .venv
   source .venv/bin/activate
   pip install -e .[dev]
   pytest

Recommended Reading Order
-------------------------

1. :doc:`architecture`
2. :doc:`custom_adapters`
3. :doc:`../adapter_creation`
4. :doc:`testing`
