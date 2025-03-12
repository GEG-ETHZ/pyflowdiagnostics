import argparse
import logging
import time
import os
from datetime import datetime
from flow_diagnostics import FlowDiagnostics


def config_logging(debug_mode):

    log_dir = os.path.join(os.getcwd(), "pyfd_logs")
    os.makedirs(log_dir, exist_ok=True)

    log_filename = os.path.join(log_dir, f"pyfd_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
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
    parser.add_argument("-f", "--file", type=str, required=True,
                        help="Path to the reservoir simulation file", dest="file_path")
    parser.add_argument("-t", "--time_steps", nargs='+', type=int, required=True, default=[],
                        help="List of time step indices to run the diagnostics on (e.g., -t 1 5 10)", dest="time_step_indices")
    parser.add_argument("-d", "--debug", help="Enable debugging (optional)", required=False, default=False,
                        action=argparse.BooleanOptionalAction, dest="debug")
    return parser


def main():

    parser = config_parser()
    args = parser.parse_args()
    config_logging(args.debug)

    try:
        logging.info(f"Running Flow Diagnostics using: {args.file_path}")
        t0 = time.time()

        fd = FlowDiagnostics(args.file_path)
        for time_step in args.time_step_indices:
            fd.execute(time_step)

    except Exception as e:
        raise RuntimeError(f"{e}")

    logging.info("Run finished normally. Elapsed time: {:.2f} seconds.".format(time.time() - t0))


if __name__ == "__main__":
    main()
