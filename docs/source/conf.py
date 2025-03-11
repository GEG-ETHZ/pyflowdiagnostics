import os
import sys

# Correct sys.path: Go UP TWO levels to get to the root of your project
sys.path.insert(0, os.path.abspath('../../'))  # <--- Corrected Path

print("Current sys.path:", sys.path)  # <--- Add this line

project = 'pyfd'
copyright = '2025, Tsubasa Onishi'
author = 'Tsubasa Onishi'
html_title = "PyFD Documentation"
html_short_title = "PyFD"

master_doc = "pyfd_doc"

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx_rtd_theme'  # Use readthedocs theme
]

autodoc_default_options = {
    'members': True,
    'undoc-members': False,
    'private-members': True,  # Exclude private members (starting with _)
    'special-members': False,  # Exclude special members like __init__, __module__, etc.
}

html_theme = 'sphinx_rtd_theme' # Consistent theme

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

napoleon_google_docstring = True  # Or napoleon_numpy_docstring = True, but not both

# html_static_path = ['_static']  # Only needed if you have custom static files