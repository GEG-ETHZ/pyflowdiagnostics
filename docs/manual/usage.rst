Usage
=====


Prerequisites
-------------

Before running, ensure that you have completed a reservoir simulation and that
the output includes all necessary data for flow diagnostics. This should
include pore volume, fluxes, cell connections, and well information, stored in
the binary output files.

- For SLB simulators (or OPM): ensure that you generate ``.INIT`` and
  ``.EGRID`` files. Additionally, specify ``FLORES`` under ``RPTPST`` keyword
  to output fluxes in reservoir conditions. Alternatively, the tool also works
  if both fluxes in surface conditions and formation volume factors are
  available.
- For CMG simulators: Use ``FLUXCON`` along with ``OUTSRF`` keyword to output
  fluxes in reservoir condition.


Running the tool
----------------

Via the command line:

.. code-block:: console

   pyflowdiagnostics -f <PATH_TO_DATA/AFI_FILE> -t <LIST_OF_TSTEPS_OF_INTEREST>

Arguments:

- ``-f <PATH_TO_SIMULATOR_PRIMARY_INPUT_FILE>``: Path to the reservoir
  simulation primary input file (.DATA, .AFI, or .DAT).
- ``-t <LIST_OF_TSTEPS_OF_INTEREST>``: List of reservoir simulation output
  (grid dynamic simulation results) time step indices to run the diagnostics
  on.
- ``-d``: An optional argument to enable debug mode.


Example
-------

Using command line interface (CLI):

.. code-block:: console

   pyflowdiagnostics -f /path/to/simulation.DATA -t 1 5 10

Or, in your Python script:

.. code-block:: python

   import pyflowdiagnostics.flow_diagnostics as pfd

   tsteps = [1, 5, 10]

   fd = pfd.FlowDiagnostics("/path/to/simulation.DATA")
   for tstep in tsteps:
       fd.execute(tstep)

The code will identify the simulator type based on the file path (extension) and then use appropriate binary reader. 


Output
------

The script generates a folder named ``CASENAME.fdout`` in the same directory as
the provided ``DATA/AFI/DAT`` file. This folder contains:

- Grid flow diagnostics results (time-of-flight, flow partitioning, well pair
  IDs) in Petrel readable (``.GRDECL``) format.
- If applicable:

  - Allocation factors.
  - Lorentz curve data.
  - Sweep efficiencies.

Sample results:

.. figure:: ../_static/imgs/spe10.png
   :width: 100 %
   :align: center
   :alt: Time of Flight Map
   :name: spe10top

   SPE10 top layer: TOF, flow partition, allocation factors, Lorentz curve.

.. figure:: ../_static/imgs/saigup.png
   :width: 100 %
   :align: center
   :alt: Permeability and TOF
   :name: saigup

   SAIGUP: permeability and TOF.


Example using sample data
-------------------------

First, we grab the example data from the repo
https://github.com/GEG-ETHZ/pyfd-data.

.. code-block:: python

   import os
   import pooch
   import zipfile
   import pyflowdiagnostics.flow_diagnostics as pfd

   fname = "pyfd-data"
   version = "2025-07-24"
   out = pooch.retrieve(
       f"https://github.com/GEG-ETHZ/pyfd-data/archive/refs/tags/{version}.zip",
       "61caf9b88b3f84227eabf2f1557c0d3f790caf6de3cb1559ebe3482b922c746a",
       fname=fname+".zip",
       path="data",
   )

   fdir = out.rsplit('.', 1)[0]
   with zipfile.ZipFile(out, 'r') as zip_ref:
       zip_ref.extractall(fdir)

Alternatively, you can grab the data manually from the repo
(https://github.com/GEG-ETHZ/pyfd-data) or use the usual tools,

.. code-block:: console

   wget https://github.com/GEG-ETHZ/pyfd-data/archive/refs/tags/2025-07-23.zip


Then we can run pyflowdiagnostics just as introduced above:

.. code-block:: python

   ecl_dir = os.path.join(fdir, f"pyfd-data-{version}", "examples", "ecl")
   spe10_dir = os.path.join(ecl_dir, "e100", "SPE10_TOPLAYER")

   fd = pfd.FlowDiagnostics(os.path.join(spe10_dir, "SPE10.DATA"))
   fd.execute(time_step_id=1)

This will create a directory ``SPE10.fdout`` within the data folder ``e100``,
with the four files ``Allocation_factor.xlsx``, ``F_Phi_1.csv``,
``GridFlowDiagnostics_1.GRDECL``, and ``Tracer_1.csv``.
