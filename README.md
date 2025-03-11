# Flow Diagnostics Toolkit

This repository provides a Python-based tool for flow diagnostics in reservoir simulation. To our knowledge, it is the first open-source, lightweight Python-based finite volume-based flow diagnostics tool coupled with commercial reservoir simulators.

## Features
- Read reservoir simulator outputs (fluxes, pore volume, cell connections, well info, etc.)
  - For SLB reservoir simulators, we developed `ecl_reader.py` that reads ECLIPSE/IX style binary simulation outputs. This script alone may be useful for other applications that require parsing and processing ECLIPSE style binary output files.
  - For CMG reservoir simulators, we utilize [sr3_reader](https://github.com/nikolai-andrianov/sr3_reader/blob/main/README.md) (slightly modified to support LGR).
- Solves the time-of-flight (TOF) and tracer concentrations equations (finite volume).
- Computes allocation factors, if both injector(s) and producer(s) exist.
- Computes Lorentz curves and sweep efficiencies, if both injector(s) and producer(s) exist (total TOF is required).

## Installation

Ensure you have [Anaconda](https://www.anaconda.com/products/distribution) installed, then create a conda environment using the provided `environment.yml` file:

```
conda env create -f environment.yml
conda activate pyfd
```

## Usage

Run the tool via the command line:

```
python pyfd_cli.py -f <PATH_TO_DATA/AFI_FILE> -t <TSTEP_OF_INTEREST>
```

### Arguments:
- `-f <PATH_TO_DATA/AFI_FILE>`: Path to the reservoir simulation primary input file (.DATA, .AFI, or .DAT).
- `-t <TSTEP_OF_INTEREST>`: Reservoir simulation output (grid dynamic simulation results) time step of interest for the analysis.
- `-d`: An optional argument to enable debug mode.

### Example:

```
python pyfd_cli.py -f /path/to/simulation.DATA -t 1
```

Or, in your Python script for a single time step of interest:

```python
from flow_diagnostics import FlowDiagnostics

tstep = 1
fd = FlowDiagnostics("examples/ecl/e100/SPE10_TOPLAYER/SPE10.DATA")
fd.execute(tstep)
```

For multiple time steps:

```python
from flow_diagnostics import FlowDiagnostics

tsteps = [1,5,10]
fd = FlowDiagnostics("examples/ecl/e100/SPE10_TOPLAYER/SPE10.DATA")
for tstep in tsteps:
    fd.execute(tstep)
```
## Output

The script generates a folder named `CASENAME.fdout` in the same directory as the provided `DATA/AFI/DAT` file. This folder contains:
- Grid flow diagnostics results (time-of-flight, flow partitioning) in `.GRDECL` (Petrel readable) format.
- If applicable:
  - Allocation factors.
  - Lorentz curve data.
  - Sweep efficiencies.

## Documentation

The full documentation is available `docs/build/html/pyfd_doc.html`.

## Project Status
This project is actively maintained and under development. 
- ✅ Core functionality implemented for SLB reservoir simulators.
- ✅ Prototype support for CMG reservoir simulators.
- ✅ Tested with various types of grid systems:
  - Single-porosity
  - Dual-porosity dual/single-permeability
  - Faulted reservoirs (NNCs)
  - Embedded discrete fracture model (EDFM)
  - Combinations of the above
- 🛠️ Planned improvements:
  - More testing with IX, OPM, and CMG (not yet fully tested)
  - Multidimensional upstream (MDU) weighting - currently uses single-point upstream (SPU) weighting.
  
- 🚀 Looking for contributors! Feel free to open an issue or submit a PR.

## Dependencies

Required core dependencies are installed via `environment.yml`.
Additionally, we utilize [sr3_reader](https://github.com/nikolai-andrianov/sr3_reader/blob/main/README.md) (slightly modified to support LGR) for processing CMG binary outputs.

## References

- Datta-Gupta, A., & King, M. J. (2007). Streamline simulation: theory and practice (Vol. 11). Society of Petroleum Engineers.
- Møyner, O., Krogstad, S., & Lie, K. A. (2015). The application of flow diagnostics for reservoir management. SPE Journal, 20(02), 306-323.
- [MRST Flow Diagnostics module by SINTEF](https://www.sintef.no/projectweb/mrst/modules/diagnostics/).
- Shahvali, M., Mallison, B., Wei, K., & Gross, H. (2012). An alternative to streamlines for flow diagnostics on structured and unstructured grids. SPE Journal, 17(03), 768-778.
- Shook, G. M., & Mitchell, K. M. (2009, October). A robust measure of heterogeneity for ranking earth models: The F-Phi curve and dynamic Lorenz coefficient. In SPE Annual Technical Conference and Exhibition (pp. SPE-124625). SPE.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contact

For any questions or contributions, feel free to open an issue or reach out.

