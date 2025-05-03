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

import numpy as np
import struct
import os
import logging


class EclReader:
    """Reads SLB ECLIPSE style binary output files (.INIT, .EGRID, .UNRST, .X00xx).

    This class provides methods to read various ECLIPSE output files, including
    initial conditions (.INIT), grid data (.EGRID), and restart files (.UNRST, .X00xx).
    It handles endianness detection and data type conversion.

    Attributes:
        input_file_path (str): Path to the main ECLIPSE input file (.DATA or .IXF).
        input_file_path_base (str): Base path of the input file (without extension).
        init_file_path (str): Path to the initial conditions file (.INIT).
        egrid_file_path (str): Path to the grid data file (.EGRID).
        unrst_file_path (str): Path to the unified restart file (.UNRST).  Currently not used.
    """


    def __init__(self, input_file_path: str) -> None:
        """Initializes the EclReader object.

        Args:
            input_file_path (str): Path to the main ECLIPSE input file (.DATA or .IXF).

        Raises:
            FileNotFoundError: If the input file or any required related file is not found.
            RuntimeError: If the input file has an unsupported extension.
        """
        self.input_file_path = input_file_path
        self._validate_input_file()
        self._initialize_file_names()


    def read_init(self, keys: list = None) -> dict:
        """Reads data from the initial conditions file (.INIT).

        Args:
            keys (list, optional): List of keys to read. If None, all keys are read. Defaults to None.

        Returns:
            dict: Dictionary containing the requested data, keyed by the provided keys.
                Returns an empty dictionary if no keys are provided.
        """
        return self._read_bin(self.init_file_path, keys)


    def read_egrid(self, keys: list = None) -> dict:
        """Reads data from the grid data file (.EGRID).

        Args:
            keys (list, optional): List of keys to read. If None, all keys are read. Defaults to None.

        Returns:
            dict: Dictionary containing the requested data, keyed by the provided keys.
                Returns an empty dictionary if no keys are provided.
        """
        return self._read_bin(self.egrid_file_path, keys)


    def read_rst(self, keys: list = None, tstep_id: int = None, unified: bool = False) -> dict:
        """Reads data from a restart file (.X00xx).

        Args:
            keys (list, optional): List of keys to read. If None, all keys are read. Defaults to None.
            tstep_id (int, optional): Time step ID. Required for reading restart files. Defaults to None.
            unified (bool, optional): Whether to read a unified restart file (.UNRST).  Not yet implemented. Defaults to False.

        Returns:
            dict: Dictionary containing the requested data, keyed by the provided keys.
                Returns an empty dictionary if no keys are provided.

        Raises:
            NotImplementedError: If `unified` is True (UNRST support not implemented).
            ValueError: If `tstep_id` is None.
            FileNotFoundError: If the specified restart file is not found.
        """

        if unified:
            raise NotImplementedError("Unified restart file (.UNRST) support is not yet implemented.")
        if tstep_id is None:
            raise ValueError("Missing required argument: tstep_id.")

        file_path = f"{self.input_file_path_base}.X{self._int2ext(tstep_id)}"
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Restart file not found: {file_path}")

        return self._read_bin(file_path, keys)


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
        if ext.upper() not in [".DATA", ".IXF"]:
            if ext.upper() == ".AFI":
                logging.warning("Intersect input file detected. Limited support available.")
            else:
                raise RuntimeError(f"Unsupported input file: {self.input_file_path}")

        self.input_file_path_base = base


    def _initialize_file_names(self) -> None:
        """Initializes file paths for related binary files (.INIT, .EGRID, .UNRST).

        Raises:
            FileNotFoundError: If any of the required files (.INIT, .EGRID) are not found.
        """
        self.init_file_path = f"{self.input_file_path_base}.INIT"
        self.egrid_file_path = f"{self.input_file_path_base}.EGRID"
        self.unrst_file_path = f"{self.input_file_path_base}.UNRST"

        required_files = [self.init_file_path, self.egrid_file_path]
        for file in required_files:
            if not os.path.exists(file):
                raise FileNotFoundError(f"Required file not found: {file}")
        # TODO: Support both UNRST and X00xx files


    def _read_bin(self, file_path: str, keys: list) -> dict:
        """Reads ECLIPSE style binary data from the given file.

        Args:
            file_path (str): Path to the binary file.
            keys (list): List of keys to read.

        Returns:
            dict: Dictionary containing the requested data. Returns an empty dictionary if keys is None.
        """

        if keys is None:
            logging.warning("No keys provided.")
            return {}

        logging.debug(f"Reading keys: {keys} in file: {file_path}")

        variables = {}
        with open(file_path, 'rb') as fid:
            endian = self._detect_endian(fid)
            found_keys = {key: False for key in keys}

            while keys and not all(found_keys.values()):
                data, _, key = self._load_vector(fid, endian)
                key = key.strip()
                if key in found_keys:
                    # Dynamically determine dtype
                    if isinstance(data, np.ndarray):
                        variables[key] = data  # Keep original dtype
                    elif isinstance(data, (bytes, str)):
                        variables[key] = data.decode(errors="ignore").strip()  # Convert bytes to string
                    elif isinstance(data, (int, float)):
                        variables[key] = np.array([data], dtype=np.float32)  # Convert scalars to array
                    else:
                        logging.warning(f"Unknown data type for key: {key}")
                        variables[key] = data  # Store as-is

                    found_keys[key] = True

                if fid.tell() >= os.fstat(fid.fileno()).st_size:
                    break

            # Log missing keys (Debug level)
            missing_keys = [k for k, v in found_keys.items() if not v]
            if missing_keys:
                logging.debug(f"The following keys were not found: {missing_keys}")
                for key in missing_keys:
                    variables[key] = np.array([])

        return variables


    def _load_vector(self, fid, endian):
        """Reads a data block (vector) from the binary file.

        Args:
            fid: File object.
            endian (str): Endianness ('<' for little-endian, '>' for big-endian).

        Returns:
            tuple: A tuple containing the data (NumPy array or string), the data count, and the key.
                Returns (None, None, key) if an error occurs during reading.
        """
        try:
            # Read and verify the header
            header_size = struct.unpack(endian + 'i', fid.read(4))[0]
            key = fid.read(8).decode(errors='ignore').strip()
            data_count = struct.unpack(endian + 'i', fid.read(4))[0]
            data_type_raw = fid.read(4)
            data_type = data_type_raw.decode(errors='ignore').strip().upper()
            end_size = struct.unpack(endian + 'i', fid.read(4))[0]

            if header_size != end_size:
                logging.warning(f"Mismatch Detected for {key}: Header={header_size}, End={end_size}")
                return None, None, key  # Skip this entry

            # Define data type mapping
            dtype_map = {'CHAR': 'S1', 'INTE': 'i4', 'REAL': 'f4', 'DOUB': 'f8', 'LOGI': 'i4'}
            dtype = dtype_map.get(data_type)

            if dtype:
                raw_data = bytearray()
                read_count = 0

                while read_count < data_count:
                    # Read the header size of this chunk
                    chunk_size = struct.unpack(endian + 'i', fid.read(4))[0]
                    chunk_data = fid.read(chunk_size)
                    chunk_end = struct.unpack(endian + 'i', fid.read(4))[0]

                    if chunk_size != chunk_end:
                        logging.warning(f"Chunk mismatch in {key}: Expected {chunk_size}, got {chunk_end}")
                        return None, None, key

                    raw_data.extend(chunk_data)
                    read_count += chunk_size // np.dtype(dtype).itemsize

                if data_type == "CHAR":
                    char_array = np.frombuffer(raw_data, dtype="S1").reshape((-1, 8))  # 8-char wide strings
                    char_array = np.char.decode(char_array, encoding='utf-8').astype(str)
                    return char_array, data_count, key
                else:
                    data = np.frombuffer(raw_data, dtype=endian + dtype)
                    return data, data_count, key
            else:
                fid.seek(data_count * 4, os.SEEK_CUR)  # Skip unknown type
                return None, None, key
        except struct.error:
            return None, None, ""


    def _detect_endian(self, fid):
        """Detects file endianness.

        Args:
            fid: File object.

        Returns:
            str: Endianness ('<' for little-endian, '>' for big-endian).
        """
        fid.seek(0)
        test_int = fid.read(4)
        little_endian = struct.unpack('<i', test_int)[0]
        big_endian = struct.unpack('>i', test_int)[0]
        fid.seek(0)
        return '<' if abs(little_endian) < abs(big_endian) else '>'


    def _int2ext(self, i):
        """Converts an integer to a formatted string with leading zeros (e.g., 1 to "0001").

        Args:
            i (int): Integer to convert.

        Returns:
            str: Formatted string with leading zeros.
        """
        return f"{i:04d}"
