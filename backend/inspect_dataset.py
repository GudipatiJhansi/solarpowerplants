from __future__ import annotations

import argparse
from pathlib import Path

from app.services.data_service import inspect_csv_file


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Inspect a solar plant CSV dataset.')
    parser.add_argument('file_path', nargs='?', default=str(Path(__file__).resolve().parent / 'data' / 'sample' / 'demo_solar_data.csv'))
    args = parser.parse_args()

    summary = inspect_csv_file(args.file_path)
    print(f"Filename: {summary['filename']}")
    print(f"Rows: {summary['row_count']}")
    print(f"Columns: {summary['column_count']}")
    print(f"Columns list: {summary['columns']}")
    print(f"Timestamp min: {summary['timestamp_min']}")
    print(f"Timestamp max: {summary['timestamp_max']}")
    print(f"Duplicate rows: {summary['duplicate_rows']}")
    print(f"Supported features: {summary['supported_features']}")
