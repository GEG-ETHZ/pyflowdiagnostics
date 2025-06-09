# Copyright 2025 Tsubasa Onishi
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import logging
from datetime import datetime
from pymatsolver.solvers import Base
from scooby import Report as ScoobyReport
from pymatsolver import AvailableSolvers, Mumps, Pardiso, SolverLU

# scooby is a soft dependency for pyflowdiagnostics
try:
    from scooby import Report as ScoobyReport
except ImportError:
    class ScoobyReport:
        def __init__(self, additional, core, optional, ncol, text_width, sort):
            print("\n* WARNING :: `pyflowdiagnostics.Report` requires `scooby`."
                  "\n             Install it via `pip install scooby`.\n")

try:
    # - Released versions just tags:       0.8.0
    # - GitHub commits add .dev#+hash:     0.8.1.dev4+g2785721
    # - Uncommitted changes add timestamp: 0.8.1.dev4+g2785721.d20191022
    from pyflowdiagnostics.version import version as __version__
except ImportError:
    # If it was not installed, then we don't know the version. We could throw a
    # warning here, but this case *should* be rare. pyflowdiagnostics should be
    # installed properly!
    __version__ = 'unknown-'+datetime.today().strftime('%Y%m%d')


__all__ = [
    "__version__", "Report", "set_default_solver", "get_default_solver",
]


def __dir__():
    return __all__


# The default direct solver priority is:
# 1. Pardiso (optional, but available on intel systems)
# 2. Mumps (optional, but available for all systems)
# 3. Scipy's SuperLU (available for all scipy systems)
if AvailableSolvers["Pardiso"]:
    _DEFAULT_SOLVER = Pardiso
elif AvailableSolvers["Mumps"]:
    _DEFAULT_SOLVER = Mumps
else:
    _DEFAULT_SOLVER = SolverLU

_SOLVER_INFO = 0

# Create a specific warning allowing users to silence this if they so choose.
class DefaultSolverWarning(UserWarning):
    pass


def get_default_solver():
    """Return the default solver used by pyflowdiagnostics"""
    global _SOLVER_INFO
    if not _SOLVER_INFO:
        logging.info(f"Using the default solver: {_DEFAULT_SOLVER.__name__}.")
        _SOLVER_INFO = 1
    return _DEFAULT_SOLVER


def set_default_solver(solver_class):
    """Set the default solver used by pyflowdiagnostics.

    Parameters
    ----------
    solver_class
        A ``pymatsolver.solvers.Base`` subclass used to construct an object
        that acts os the inverse of a sparse matrix.
    """
    global _DEFAULT_SOLVER
    if not issubclass(solver_class, Base):
        raise TypeError(
            "Default solver must be a subclass of pymatsolver.solvers.Base."
        )
    _DEFAULT_SOLVER = solver_class


class Report(ScoobyReport):
    r"""Print date, time, and version information.

    Use `scooby` to print date, time, and package version information in any
    environment (Jupyter notebook, IPython console, Python console, QT
    console), either as html-table (notebook) or as plain text (anywhere).

    Always shown are the OS, number of CPU(s), `numpy`, `scipy`, `pandas`,
    `h5py`, `pymatsolver`, `pyflowdiagnostics`, `sys.version`, and time/date.

    Additionally shown are, if they can be imported, `IPython`, and
    `matplotlib`, `pardiso`, `python-mumps`. It also shows MKL information, if
    available.

    All modules provided in `add_pckg` are also shown.

    .. note::

        The package `scooby` has to be installed in order to use `Report`:
        ``pip install scooby``.


    Parameters
    ----------
    add_pckg : packages, optional
        Package or list of packages to add to output information (must be
        imported beforehand).

    ncol : int, optional
        Number of package-columns in html table (no effect in text-version);
        Defaults to 3.

    text_width : int, optional
        The text width for non-HTML display modes

    sort : bool, optional
        Sort the packages when the report is shown


    Examples
    --------
    >>> import pytest
    >>> import dateutil
    >>> from pyflowdiagnostics import Report
    >>> Report()                            # Default values
    >>> Report(pytest)                      # Provide additional package
    >>> Report([pytest, dateutil], ncol=5)  # Set nr of columns

    """

    def __init__(self, add_pckg=None, ncol=3, text_width=80, sort=False):
        """Initiate a scooby.Report instance."""

        # Mandatory packages.
        core = [
            "numpy", "scipy", "pandas", "xlsxwriter", "h5py", "pymatsolver",
            "pyflowdiagnostics",
        ]

        # Optional packages.
        optional = ['IPython', 'matplotlib', 'pardiso', 'python-mumps']

        super().__init__(additional=add_pckg, core=core, optional=optional,
                         ncol=ncol, text_width=text_width, sort=sort)
