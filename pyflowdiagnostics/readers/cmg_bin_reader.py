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

import os.path

from pyflowdiagnostics.readers.sr3_reader import  *

__all__ = ["CmgReader", ]


def __dir__():
    return __all__


class CmgReader:
    """Reads CMG style binary output file (.sr3).

    This class provides methods to read various CMG output files, including

    Attributes:
        input_file_path (str): Path to the main CMG input file (.DAT).
        input_file_path_base (str): Base path of the input file (without extension).
        sr3_file_path (str): Path to the output binary file (.sr3).
    """


    def __init__(self, input_file_path: str) -> None:
        """Initializes the EclReader object.

        Args:
            input_file_path (str): Path to the main ECLIPSE input file (.DATA or .IXF).

        Raises:
            FileNotFoundError: If the input file or any required file is not found.
            RuntimeError: If the input file has an unsupported extension.
        """
        self.input_file_path = input_file_path
        self._validate_input_file()
        self._initialize_file_names()
        self._initialize_sr3()


    def get_grid_properties(self, keys: list = None) -> tuple[list, dict]:
        """Reads grid properties from the sr3 file.

        Args:
            keys (list): List of keys to read.

        Returns:
            list: time step indices at which spatial properties are available
            dict: Dictionary containing the requested data, keyed by the provided keys.
                Returns an empty dictionary if no keys are provided.
        """
        if self._sr3.grid.LGR:
            sp_ind, sp = get_spatial_properties(self._sr3, keys, original_grid_only=True)
        else:
            sp_ind, sp = get_spatial_properties(self._sr3, keys)

        return sp_ind, sp


    def get_time_series(self) -> dict:
        """Reads time series from the sr3 file.

        Returns:
            dict: Dictionary containing time series data for each well
        """
        return get_wells_timeseries(self._sr3)


    def get_layer_time_series(self) -> dict:
        """Reads layer time series from the sr3 file.

        Returns:
            dict: Dictionary containing layer time series data for each well
        """
        return get_layers_timeseries(self._sr3)


    def get_sr3(self) -> object:
        """Returns the sr3 object.

        Returns:
            object: sr3 object
        """
        return self._sr3


    # ---- Private Methods ---------------------------------------------------------------------------------------------


    def _validate_input_file(self) -> None:
        """Validates the input file and its extension.

        Raises:
            FileNotFoundError: If the input file is not found.
            RuntimeError: If the input file has an unsupported extension.
        """
        if not os.path.exists(self.input_file_path):
            raise FileNotFoundError(f"Input file not found: {self.input_file_path}")

        base, ext = os.path.splitext(self.input_file_path)
        if ext.upper() not in [".DAT"]:
            raise RuntimeError(f"Unsupported input file: {self.input_file_path}")

        self.input_file_path_base = base


    def _initialize_file_names(self) -> None:
        """Initializes file path of the output binary file (.sr3).

        Raises:
            FileNotFoundError: If any of the required files (.INIT, .EGRID) are not found.
        """
        self.sr3_file_path = f"{self.input_file_path_base}.sr3"
        if not os.path.exists(self.sr3_file_path):
            raise FileNotFoundError(f"Required file not found: {self.sr3_file_path}")


    def _initialize_sr3(self) -> None:
        """Initializes the sr3 file."""
        logging.info(f"Reading sr3 file: {self.sr3_file_path}. It may take a while...")
        self._sr3 = read_SR3(self.sr3_file_path)
