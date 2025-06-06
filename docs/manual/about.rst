About
=====

The code ``pyflowDS``, Flow Diagnostics Toolkit, provides a Python-based tool
for flow diagnostics in reservoir simulation. To our knowledge, it is the first
open-source, lightweight Python-based flow diagnostics tool coupled with
commercial reservoir simulators.

Features
--------

- Read reservoir simulator outputs (fluxes, pore volume, cell connections, well
  info, etc.)

  - SLB reservoir simulators: we developed ``ecl_reader.py`` that reads
    ECLIPSE/IX style binary simulation outputs. This script alone may be useful
    for other applications that require parsing and processing ECLIPSE style
    binary output files.
  - CMG reservoir simulators: we utilize
    `sr3_reader
    <https://github.com/nikolai-andrianov/sr3_reader/blob/main/README.md>`_
    (slightly modified to support LGR).

- Solves the time-of-flight (TOF) and tracer concentrations equations (finite
  volume).

- Compute other diagnostics, if applicable:

  - Allocation factors
  - Lorentz curves and sweep efficiencies
