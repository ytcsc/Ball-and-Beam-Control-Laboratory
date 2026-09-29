import csv
import numpy as np

EXPERIMENT_HEADER = ['time_ms', 'spx_cm']           # Expected experiment csv header
EXPERIMENT_MIN_DTIME = 20                           # Minimum time difference in ms between successive data points
EXPERIMENT_MAX_TIME = 30*60*1000                    # Maximum experiment time in ms
EXPERIMENT_MAX_BEAM_LENGTH = 50                     # Maximum beam length in cm
EXPERIMENT_MAX_DATAPOINTS = 65536                   # Maximum number of experiment datapoints
EXPERIMENT_DATA_LENGTH = len(EXPERIMENT_HEADER)     # Expected data length for each csv row

def load_and_validate_experiment(experiment_filepath : str, csv_delimiter: str = ',') -> tuple[np.ndarray, str]:
    with open(experiment_filepath, mode = 'r', encoding = 'utf-8') as experiment_file:
        error_and_warning_msgs = ""
        reader = csv.reader(experiment_file, delimiter = csv_delimiter)
        experiment_header = next(reader, None)
        if experiment_header is None:
            error_and_warning_msgs += "Error: Empty CSV file.\n"
            return None, error_and_warning_msgs
        if experiment_header != EXPERIMENT_HEADER:
            error_and_warning_msgs += "Error: CSV has incorret header.\n"
            return None, error_and_warning_msgs
        experiment_table = [(int(row[0]), float(row[1])) for row in reader if len(row) == EXPERIMENT_DATA_LENGTH]
        if not experiment_table:
            error_and_warning_msgs += "Error: CSV has no data rows.\n"
            return None, error_and_warning_msgs
        if len(experiment_table) > EXPERIMENT_MAX_DATAPOINTS:
            error_and_warning_msgs += "Error: Data exceeds maximum allowed limit of 65536 rows.\n"
            return None, error_and_warning_msgs
        if len(experiment_table) < 2:
            error_and_warning_msgs += "Error: Experiment must have at least 2 data points.\n"
            return None, error_and_warning_msgs
        data_type = np.dtype([('time_ms', np.int64), ('spx_cm', np.float64)])
        experiment_data = np.array(experiment_table, dtype = data_type)
        times = experiment_data['time_ms']
        references = experiment_data['spx_cm']
        time_diffs = np.diff(times)
        if np.any(time_diffs < EXPERIMENT_MIN_DTIME):
            error_and_warning_msgs += "Error: Insufficient time difference between data points. Minimal dt = 20 ms.\n"
            return None, error_and_warning_msgs
        if np.any(np.abs(references) > EXPERIMENT_MAX_BEAM_LENGTH):
            error_and_warning_msgs += "Warning: Position setpoint exceeds beam maximum length.\n"
        if times[-1] > EXPERIMENT_MAX_TIME:
            error_and_warning_msgs += "Warning: Experiment time length is too large.\n"
        return experiment_data, error_and_warning_msgs