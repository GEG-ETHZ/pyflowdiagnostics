import time
from pyflowdiagnostics import __version__

# ==== 1. Extensions  ====

# Load extensions
extensions = [
    #'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx_design',
    'sphinx.ext.viewcode',
    'sphinx_automodapi.automodapi',
]
autosummary_generate = True
add_module_names = True
add_function_parentheses = False

#autodoc_default_options = {
#    'members': True,
#    'undoc-members': False,
#    'private-members': True,  # Exclude private members (starting with _)
#    'special-members': False,  # Exclude special members like __init__, __module__, etc.
#}

napoleon_google_docstring = True  # Or napoleon_numpy_docstring = True, but not both

# ==== 2. General Settings ====
description = 'Flow Diagnostics Toolkit.'


# The suffix(es) of source filenames.
source_suffix = ['.md', '.rst']

# The master toctree document.
master_doc = 'index'

# General information about the project.
project = 'pyflowdiagnostics'
author = 'Tsubasa Onishi'
copyright = f'2025-{time.strftime("%Y")}, {author}'

# |version| and |today| tags (|release|-tag is not used).
version = __version__
release = __version__
today_fmt = '%d %B %Y'

# List of patterns to ignore, relative to source directory.
exclude_patterns = ['_build', '../tests']

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'friendly'

# ==== 3. HTML settings ====
html_theme = 'pydata_sphinx_theme'
html_static_path = ['_static']
html_title = 'pyflowdiagnostics'

html_theme_options = {
    "github_url": "https://github.com/GEG-ETHZ/pyflowdiagnostics",
    "external_links": [
        {"name": "GEG", "url": "https://geg.ethz.ch/"},
    ],
    "navigation_with_keys": True,
}

html_context = {
    "github_user": "GEG-ETHZ",
    "github_repo": "pyflowdiagnostics",
    "github_version": "main",
    "doc_path": "docs",
}
