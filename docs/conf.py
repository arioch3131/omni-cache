# Configuration file for the Sphinx documentation builder.

import os
import sys

sys.path.insert(0, os.path.abspath("../src"))

project = "Omni-Cache"
copyright = "2024, Omni-Cache"
author = "Omni-Cache"
release = "2.1.0"
version = "2.1.0"

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.todo",
    "sphinx.ext.coverage",
    "sphinx.ext.mathjax",
    "sphinx.ext.ifconfig",
    "sphinx.ext.githubpages",
]

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

# Napoleon settings
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = False
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_param = True
napoleon_use_rtype = True

# Autodoc settings
autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
    "special-members": "__init__",
}
autodoc_member_order = "bysource"
# Keep API pages readable and avoid noisy cross-reference warnings from
# unresolved/ambiguous typing aliases and TypeVars.
autodoc_typehints = "none"

# Autosummary settings
autosummary_generate = True
autosummary_generate_overwrite = True

templates_path = ["_templates"]
exclude_patterns = [
    "_build",
    "Thumbs.db",
    ".DS_Store",
    "api/generated/**",
    "exceptions_test_readme.md",
]

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]

html_theme_options = {
    "prev_next_buttons_location": "bottom",
    "style_nav_header_background": "#2980B9",
    "collapse_navigation": False,
    "sticky_navigation": True,
    "navigation_depth": 4,
    "includehidden": True,
    "titles_only": False,
}

html_sidebars = {
    "**": [
        "relations.html",
        "searchbox.html",
    ]
}

intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
    "redis": ("https://redis-py.readthedocs.io/en/stable/", None),
}

# Ignore unresolved internal TypeVars in nitpicky mode (-n)
nitpick_ignore = [
    ("py:obj", "omni_cache.adapters.memory.memory.K"),
    ("py:obj", "omni_cache.adapters.memory.memory.V"),
    ("py:obj", "omni_cache.adapters.redis.redis.K"),
    ("py:obj", "omni_cache.adapters.redis.redis.V"),
    ("py:obj", "omni_cache.adapters.smartpool.smartpool.T"),
    ("py:class", "omni_cache.adapters.memory.memory.K"),
    ("py:class", "omni_cache.adapters.memory.memory.V"),
    ("py:class", "omni_cache.adapters.redis.redis.K"),
    ("py:class", "omni_cache.adapters.redis.redis.V"),
    ("py:class", "omni_cache.adapters.smartpool.smartpool.T"),
    ("py:obj", "omni_cache.utils.decorators.T"),
    ("py:obj", "omni_cache.utils.decorators.F"),
    ("py:class", "omni_cache.utils.decorators.T"),
    ("py:class", "omni_cache.utils.decorators.F"),
    ("py:obj", "omni_cache.core.interfaces.key_value_interface.K"),
    ("py:obj", "omni_cache.core.interfaces.key_value_interface.V"),
    ("py:class", "omni_cache.core.interfaces.key_value_interface.K"),
    ("py:class", "omni_cache.core.interfaces.key_value_interface.V"),
    ("py:obj", "omni_cache.core.interfaces.pool_interface.T"),
    ("py:class", "omni_cache.core.interfaces.pool_interface.T"),
    ("py:class", "smartpool.ObjectFactory"),
    ("py:class", "omni_cache.adapters.smartpool.factory_smartpool._T"),
    ("py:obj", "omni_cache.adapters.smartpool.factory_smartpool._T"),
    # Ambiguous references produced by autodoc in core API pages
    ("ref.python", "ManagerConfig"),
    ("ref.python", "AdapterRegistry"),
    ("ref.python", "FactoryCreationError"),
    ("ref.python", "FactoryRegistrationError"),
    ("ref.python", "FactoryNotFoundError"),
    ("ref.python", "CacheBackend"),
    ("ref.python", "FactoryInterface"),
    ("ref.python", "K"),
    ("py:class", "K"),
]

# Generic ignore for internal TypeVar symbols exposed by autodoc signatures.
nitpick_ignore_regex = [
    ("py:class", r".*\.(K|V|T|F)$"),
    ("py:obj", r".*\.(K|V|T|F)$"),
]

todo_include_todos = True

# Some API objects are intentionally re-exported under multiple paths,
# which triggers noisy "more than one target found" cross-reference warnings.
suppress_warnings = ["ref.python"]

autodoc_mock_imports = [
    "redis",
    "pymemcache",
    "smartpool",
    "adaptive_memory_pool",
]

master_doc = "index"
htmlhelp_basename = "omni-cachedoc"

epub_title = project
epub_author = author
epub_publisher = author
epub_copyright = copyright
epub_exclude_files = ["search.html"]
