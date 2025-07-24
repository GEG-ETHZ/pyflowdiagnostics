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

import argparse
import logging
import time
import os
import sys
from datetime import datetime

from pyflowdiagnostics import flow_diagnostics, utils


def config_logging(debug_mode):

    log_dir = os.path.join(os.getcwd(), "pyflowdiagnostics_logs")
    os.makedirs(log_dir, exist_ok=True)

    log_filename = os.path.join(log_dir, f"pyflowdiagnostics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    logging.basicConfig(
        level=logging.DEBUG if debug_mode else logging.INFO,
        format='%(asctime)s, %(levelname)s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(log_filename, mode='w'),
            logging.StreamHandler()
        ]
    )

def config_parser():
    parser = argparse.ArgumentParser(description="Run Flow Diagnostics on a reservoir simulation file.")
    parser.add_argument("-f", "--file", type=str, default=False,
                        help="Path to the reservoir simulation file", dest="file_path")
    parser.add_argument("-t", "--time_steps", nargs='+', type=int, default=False,
                        help="List of time step indices to run the diagnostics on (e.g., -t 1 5 10)", dest="time_step_indices")
    parser.add_argument("-d", "--debug", help="Enable debugging (optional)", default=False,
                        action=argparse.BooleanOptionalAction, dest="debug")
    parser.add_argument("--report", action="store_true", default=False,
                        help="Show pyflowdiagnostics report and exit")
    parser.add_argument("--version", action="store_true", default=False,
                        help="Show pyflowdiagnostics version info and exit")
    return parser


def main():

    parser = config_parser()
    args = parser.parse_args()
    if vars(args).pop('report'):
        print(utils.Report())
    elif vars(args).pop('version'):
        print(f"pyflowdiagnostics v{utils.__version__}")
    elif not vars(args).get('file_path') or not vars(args).get('time_step_indices'):
        print(f"{parser.description}\n=> Type `pyflowdiagnostics --help` for "
              f"more info (pyflowdiagnostics v{utils.__version__}).")
    else:
        config_logging(args.debug)

        try:
            logging.info(f"Running Flow Diagnostics using: {args.file_path}")
            t0 = time.time()

            fd = flow_diagnostics.FlowDiagnostics(args.file_path)
            for time_step in args.time_step_indices:
                fd.execute(time_step)

        except Exception as e:
            raise RuntimeError(f"{e}")

        logging.info("Run finished normally. Elapsed time: {:.2f} seconds.".format(time.time() - t0))


if __name__ == "__main__":
    sys.exit(main())
