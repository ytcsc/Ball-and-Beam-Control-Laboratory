import csv
import numpy as np

# Experiment CSV parameters
EXPERIMENT_HEADER = ['time_ms', 'spx_cm']           # Expected experiment CSV header
EXPERIMENT_MIN_DTIME = 20                           # Minimum time difference in ms between successive data points
EXPERIMENT_MAX_TIME = 30*60*1000                    # Maximum experiment time in ms
EXPERIMENT_MAX_BEAM_LENGTH = 50                     # Maximum beam length in cm
EXPERIMENT_MAX_DATAPOINTS = 65536                   # Maximum number of experiment datapoints
EXPERIMENT_DATA_LENGTH = len(EXPERIMENT_HEADER)     # Expected data length for each csv row

# Error and warning codes
LOADER_NO_ERROR = 0                                 # No error occurred during file loading
LOADER_ERROR_EMPTY_FILE = 101                       # Empty CSV file
LOADER_ERROR_INCORRECT_HEADER = 102                 # CSV file has incorrect header
LOADER_ERROR_NO_DATA = 103                          # CSV file has no data
LOADER_ERROR_MAX_DATAPOINTS = 104                   # CSV file exceeds maximum number of datapoints
LOADER_ERROR_MIN_DATAPOINTS = 105                   # CSV file has fewer than the minimum required datapoints
LOADER_ERROR_INSUFFICIENT_DT = 106                  # CSV datapoints violate the minimum sampling time interval

LOADER_WARNING_BEAM_EXCEEDED = 151                  # Experiment contains a position setpoint exceeding beam length
LOADER_WARNING_TIME_TOO_LARGE = 152                 # Total duration of the experiment exceeds the limit

def load_and_validate_experiment(experiment_filepath : str, csv_delimiter: str = ',') -> tuple[np.ndarray | None, int, list[int]]:
    """Loads and validates an experiment CSV file.

    Parses time and position data into a memory-efficient NumPy structured array and checks against physical and operational rules.

    Args:
        experiment_filepath: Path to the CSV file to be loaded.
        csv_delimiter: Delimiter character used in the CSV file (default is ',').

    Returns:
        tuple containing:
            - data (np.ndarray | None): Structured array with fields (np.int64 'time_ms', np.float64 'spx_cm'), or None if a fatal error occurs.
            - error_code (int): LOADER_NO_ERROR (0) on success, or a specific LOADER_ERROR_* code on fatal failure.
            - warning_codes (list[int]): List of non-fatal LOADER_WARNING_* codes triggered during validation.
    """

    warnings = []
    with open(experiment_filepath, mode = 'r', encoding = 'utf-8') as experiment_file:
        reader = csv.reader(experiment_file, delimiter = csv_delimiter)
        experiment_header = next(reader, None)
        print(experiment_header)
        if not experiment_header:
            return None, LOADER_ERROR_EMPTY_FILE, warnings
        if experiment_header != EXPERIMENT_HEADER:
            return None, LOADER_ERROR_INCORRECT_HEADER, warnings
        experiment_table = [(int(row[0]), float(row[1])) for row in reader if len(row) == EXPERIMENT_DATA_LENGTH]
        if not experiment_table:
            return None, LOADER_ERROR_NO_DATA, warnings
        if len(experiment_table) > EXPERIMENT_MAX_DATAPOINTS:
            return None, LOADER_ERROR_MAX_DATAPOINTS, warnings
        if len(experiment_table) < 2:
            return None, LOADER_ERROR_MIN_DATAPOINTS, warnings
        data_type = np.dtype([('time_ms', np.int64), ('spx_cm', np.float64)])
        experiment_data = np.array(experiment_table, dtype = data_type)
        times = experiment_data['time_ms']
        references = experiment_data['spx_cm']
        time_diffs = np.diff(times)
        if np.any(time_diffs < EXPERIMENT_MIN_DTIME):
            return None, LOADER_ERROR_INSUFFICIENT_DT, warnings
        if np.any(np.abs(references) > EXPERIMENT_MAX_BEAM_LENGTH):
            warnings.append(LOADER_WARNING_BEAM_EXCEEDED)
        if times[-1] > EXPERIMENT_MAX_TIME:
            warnings.append(LOADER_WARNING_TIME_TOO_LARGE)
        return experiment_data, LOADER_NO_ERROR, warnings