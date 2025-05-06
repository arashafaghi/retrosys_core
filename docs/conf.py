import os
import sys
from datetime import datetime

# Add the project root directory to the path so that Sphinx can find the modules
sys.path.insert(0, os.path.abspath('../..'))

# Project information
project = 'RetroSys Core'
author = 'RetroSys'
copyright = f'{datetime.now().year}, {author}'
release = '0.1.0'  # Update as needed

# General configuration
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx.ext.intersphinx',
    'sphinx_autodoc_typehints',
    'myst_parser',
]

# Add mappings for intersphinx to link to external documentation
intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
}

# Napoleon settings for docstring parsing
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True

# The suffix of source filenames
source_suffix = {
    '.rst': 'restructuredtext',
    '.md': 'markdown',
}

# The master toctree document
master_doc = 'index'

# The language for content
language = 'en'

# List of patterns to exclude from source
exclude_patterns = []

# The theme to use for HTML and HTML Help pages
html_theme = 'sphinx_rtd_theme'

# Theme options
html_theme_options = {
    'navigation_depth': 4,
    'titles_only': False,
}

# Add any paths that contain custom static files
html_static_path = ['_static']

# Enable autodoc to load modules
autodoc_member_order = 'bysource'
autodoc_typehints = 'description'
autodoc_typehints_format = 'short'
autoclass_content = 'both'

# Default role for text marked up with ``
default_role = 'code'