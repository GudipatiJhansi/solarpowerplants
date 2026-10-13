from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import polars as pl


def resolve_data_path(file_path: str | Path) -> Path:
    candidate = Path(file_path)
    if candidate.exists():
        return candidate

    project_root = Path(__file__).resolve().parents[2]
    repo_candidate = project_root / candidate
    if repo_candidate.exists():
        return repo_candidate

    backend_root = project_root / 'backend'
    backend_candidate = backend_root / candidate
    if backend_candidate.exists():
        return backend_candidate

    return candidate


def read_csv_safely(path: str | Path) -> pl.DataFrame:
    csv_path = Path(path)
    try:
        return pl.read_csv(csv_path, ignore_errors=True, infer_schema_length=1000000)
    except Exception:
        return pl.read_csv(csv_path, ignore_errors=True, infer_schema_length=10000)


def parse_timestamp_series(series: pl.Series) -> pl.Series:
    if series.dtype == pl.Datetime or series.dtype == pl.Date:
        return series

    formats = [
        '%d-%m-%Y %H:%M:%S',
        '%d-%m-%Y %H:%M',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d %H:%M',
        '%d/%m/%Y %H:%M:%S',
        '%Y/%m/%d %H:%M:%S',
    ]

    values = series.cast(pl.String).to_list()
    parsed = []
    for value in values:
        if value is None or value == '':
            parsed.append(None)
            continue
        text = str(value).strip()
        result = None
        for fmt in formats:
            try:
                result = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
        parsed.append(result)

    return pl.Series(name=series.name, values=parsed, dtype=pl.Datetime)


def normalize_column_name(name: str) -> str:
    cleaned = re.sub(r'[^0-9a-zA-Z]+', '_', str(name).strip())
    cleaned = cleaned.lower().strip('_')
    return cleaned or 'column'


def find_matching_column(columns: List[str], aliases: List[str]) -> str | None:
    normalized_columns = {normalize_column_name(column): column for column in columns}
    for alias in aliases:
        match = normalized_columns.get(normalize_column_name(alias))
        if match is not None:
            return match
    return None


def find_timestamp_column(columns: List[str]) -> str | None:
    candidates = ['timestamp', 'datetime', 'date_time', 'time', 'date', 'event_time', 'reading_time']
    lower_map = {normalize_column_name(col): col for col in columns}
    for key in candidates:
        if key in lower_map:
            return lower_map[key]
    for col in columns:
        lower = normalize_column_name(col)
        if 'time' in lower or 'date' in lower:
            return col
    return None


def validate_csv_file(file_path: str) -> Dict[str, Any]:
    path = resolve_data_path(file_path)
    if not path.exists():
        return {'valid': False, 'errors': [f'CSV file not found: {file_path}'], 'warnings': []}
    if path.suffix.lower() != '.csv':
        return {'valid': False, 'errors': ['Only CSV files are supported.'], 'warnings': []}
    if path.stat().st_size > 50 * 1024 * 1024:
        return {'valid': False, 'errors': ['CSV file exceeds 50 MB limit.'], 'warnings': []}
    try:
        df = read_csv_safely(path)
        if df.height == 0:
            return {'valid': False, 'errors': ['CSV file is empty.'], 'warnings': []}
        return {'valid': True, 'errors': [], 'warnings': ['CSV structure looks valid.'], 'row_count': df.height, 'column_count': df.width}
    except Exception as exc:
        return {'valid': False, 'errors': [f'CSV validation failed: {exc}'], 'warnings': []}


def inspect_csv_file(file_path: str) -> Dict[str, Any]:
    path = resolve_data_path(file_path)
    df = read_csv_safely(path)
    timestamp_column = find_timestamp_column(df.columns)
    timestamp_min = None
    timestamp_max = None

    if timestamp_column:
        try:
            parsed = parse_timestamp_series(df[timestamp_column])
            valid = parsed.drop_nulls()
            if len(valid) > 0:
                timestamp_min = valid.min().strftime('%Y-%m-%dT%H:%M:%S')
                timestamp_max = valid.max().strftime('%Y-%m-%dT%H:%M:%S')
        except Exception:
            timestamp_min = None
            timestamp_max = None

    numeric_candidates = [
        'power', 'voltage', 'current', 'temperature', 'irradiance', 'irradiation', 'humidity', 'wind', 'energy', 'generation'
    ]
    supported_features = []
    for col in df.columns:
        low = normalize_column_name(col)
        if any(token in low for token in numeric_candidates):
            supported_features.append(col)

    plants = []
    equipment_ids = []
    for col in df.columns:
        low = normalize_column_name(col)
        if 'plant' in low:
            plants = sorted(df[col].drop_nulls().unique().to_list())
        if 'inverter' in low or 'equipment' in low or 'asset' in low or 'device' in low or 'source_key' in low:
            equipment_ids = sorted(df[col].drop_nulls().unique().to_list())

    missing_values = {col: int(df[col].null_count()) for col in df.columns}
    measurement_category_columns = {
        'power': [col for col in df.columns if 'power' in normalize_column_name(col)],
        'voltage': [col for col in df.columns if 'voltage' in normalize_column_name(col)],
        'current': [col for col in df.columns if 'current' in normalize_column_name(col)],
        'temperature': [col for col in df.columns if 'temp' in normalize_column_name(col)],
        'irradiance': [col for col in df.columns if any(token in normalize_column_name(col) for token in ['irradiance', 'irradiation'])],
        'weather': [col for col in df.columns if any(token in normalize_column_name(col) for token in ['humidity', 'wind', 'irradi', 'ambient', 'module_temperature'])],
        'fault_labels': [col for col in df.columns if any(token in normalize_column_name(col) for token in ['fault', 'failure', 'anomaly', 'label'])],
    }
    invalid_measurements: Dict[str, int] = {}
    statistical_outliers: Dict[str, int] = {}
    measurement_columns = {
        'irradiance': ['irradiance', 'irradiation'],
        'temperature': ['temperature', 'temp'],
        'humidity': ['humidity'],
        'wind': ['wind_speed'],
        'power': ['ac_power', 'dc_power', 'power'],
    }
    for column in df.columns:
        normalized = normalize_column_name(column)
        values = pl.col(column).cast(pl.Float64, strict=False)
        category = next((name for name, tokens in measurement_columns.items() if any(token in normalized for token in tokens)), None)
        if category:
            if category in {'irradiance', 'power', 'wind'}:
                invalid = int(df.select((values < 0).fill_null(False).sum()).item())
            elif category == 'temperature':
                invalid = int(df.select(((values < -80) | (values > 100)).fill_null(False).sum()).item())
            else:
                invalid = int(df.select(((values < 0) | (values > 100)).fill_null(False).sum()).item())
            invalid_measurements[column] = invalid
            numeric = df.select(values.drop_nulls()).to_series()
            if len(numeric) >= 4:
                first_quartile = numeric.quantile(0.25)
                third_quartile = numeric.quantile(0.75)
                spread = third_quartile - first_quartile
                lower = first_quartile - 1.5 * spread
                upper = third_quartile + 1.5 * spread
                statistical_outliers[column] = int(df.select(((values < lower) | (values > upper)).fill_null(False).sum()).item())
    warnings = [
        f'{count} measurements outside basic physical bounds in {column}; records were retained.'
        for column, count in invalid_measurements.items() if count > 0
    ]
    warnings.extend([
        f'{count} statistical IQR outliers found in {column}; records were retained for investigation.'
        for column, count in statistical_outliers.items() if count > 0
    ])

    return {
        'filename': path.name,
        'path': str(path),
        'row_count': int(df.height),
        'column_count': int(df.width),
        'columns': df.columns,
        'data_types': {col: str(dtype) for col, dtype in df.schema.items()},
        'missing_values': missing_values,
        'measurement_units': {col: 'not declared in source file' for col in df.columns if any(token in normalize_column_name(col) for token in ['power', 'voltage', 'current', 'temp', 'irradi', 'wind', 'humidity'])},
        'invalid_measurements': invalid_measurements,
        'statistical_outliers': statistical_outliers,
        'duplicate_rows': int(df.is_duplicated().sum()),
        'timestamp_column': timestamp_column,
        'timestamp_timezone': 'not declared in source file',
        'measurement_columns': measurement_category_columns,
        'timestamp_min': timestamp_min,
        'timestamp_max': timestamp_max,
        'plants': plants,
        'equipment_ids': equipment_ids,
        'power_and_voltage_columns': [col for col in df.columns if 'power' in normalize_column_name(col) or 'voltage' in normalize_column_name(col)],
        'temperature_columns': [col for col in df.columns if 'temp' in normalize_column_name(col)],
        'irradiance_columns': [col for col in df.columns if 'irradiance' in normalize_column_name(col)],
        'fault_label_columns': [col for col in df.columns if 'fault' in normalize_column_name(col) or 'failure' in normalize_column_name(col) or 'anomaly' in normalize_column_name(col)],
        'verified_failure_label_columns': [col for col in df.columns if 'fault' in normalize_column_name(col) or 'failure' in normalize_column_name(col)],
        'supported_features': supported_features,
        'suitable_for_anomaly_detection': bool(supported_features),
        'verified_failure_labels_exist': bool([col for col in df.columns if 'fault' in normalize_column_name(col) or 'failure' in normalize_column_name(col)]),
        'suitable_for_supervised_classification': bool([col for col in df.columns if 'fault' in normalize_column_name(col) or 'failure' in normalize_column_name(col)]),
        'status': 'ready' if df.height > 0 else 'empty',
        'warnings': warnings,
        'errors': [],
    }


def preprocess_dataset(file_path: str, output_path: str) -> pl.DataFrame:
    source = resolve_data_path(file_path)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    df = read_csv_safely(source)

    renamed = df.clone()
    old_to_new = {col: normalize_column_name(col) for col in renamed.columns}
    renamed = renamed.rename(old_to_new)

    timestamp_column = find_timestamp_column(renamed.columns)
    if timestamp_column:
        try:
            parsed = parse_timestamp_series(renamed[timestamp_column])
            renamed = renamed.with_columns(parsed.alias('timestamp'))
        except Exception:
            pass

    numeric_targets = {
        'power_kw': ['power', 'power_kw', 'p_ac', 'ac_power', 'dc_power', 'active_power'],
        'voltage_v': ['voltage', 'voltage_v', 'v_dc', 'v_ac', 'dc_voltage', 'ac_voltage'],
        'current_a': ['current', 'current_a', 'i_ac', 'ac_current', 'dc_current', 'current_ma'],
        'temperature_c': ['module_temp', 'module_temperature', 'module_temp_c', 'temperature_c', 'temperature', 'temp'],
        'ambient_temperature_c': ['ambient_temp', 'ambient_temperature', 'ambient_temperature_c'],
        'irradiance_w_m2': ['irradiance', 'irradiance_w_m2', 'irradiation', 'solar_irradiance', 'ghi'],
        'humidity_pct': ['humidity', 'relative_humidity', 'humidity_pct', 'ambient_humidity'],
        'wind_speed_m_s': ['wind_speed', 'wind_speed_m_s'],
        'energy_kwh': ['energy', 'generation', 'energy_kwh', 'daily_yield', 'total_yield'],
    }

    for final_name, aliases in numeric_targets.items():
        match = find_matching_column(renamed.columns, aliases)
        if match is not None:
            renamed = renamed.with_columns(pl.col(match).cast(pl.Float64, strict=False).alias(final_name))

    if 'timestamp' not in renamed.columns:
        if 'date' in renamed.columns:
            renamed = renamed.with_columns(pl.col('date').str.to_datetime(strict=False).alias('timestamp'))

    if 'timestamp' in renamed.columns:
        renamed = renamed.with_columns(pl.col('timestamp').cast(pl.Datetime, strict=False))

    renamed = renamed.unique(maintain_order=True)

    if target.suffix.lower() == '.parquet':
        renamed.write_parquet(target)
    else:
        renamed.write_csv(target)

    return renamed


def resolve_primary_dataset_file() -> str:
    root = Path(__file__).resolve().parents[2] / 'data'
    raw_dir = root / 'raw'
    if raw_dir.exists():
        csv_files = sorted(raw_dir.glob('*.csv'))
        if csv_files:
            for candidate in csv_files:
                if 'generation' in candidate.name.lower() or 'plant_' in candidate.name.lower():
                    return str(candidate)
            return str(csv_files[0])
    sample_dir = root / 'sample'
    if sample_dir.exists():
        sample_files = sorted(sample_dir.glob('*.csv'))
        if sample_files:
            return str(sample_files[0])
    return str(root / 'sample' / 'demo_solar_data.csv')


def load_solar_dataset(primary_file: str | Path | None = None) -> pl.DataFrame:
    data_root = Path(__file__).resolve().parents[2] / 'data'
    raw_dir = data_root / 'raw'
    if primary_file:
        primary = resolve_data_path(primary_file)
        generation_files = sorted(raw_dir.glob('*Generation*.csv')) if primary.parent == raw_dir and 'generation' in primary.name.lower() else [primary]
    else:
        generation_files = sorted(raw_dir.glob('*Generation*.csv'))
        if not generation_files:
            fallback = Path(resolve_primary_dataset_file())
            generation_files = [fallback] if fallback.exists() else []

    generation_frames = []
    for source in generation_files:
        target = data_root / 'processed' / f'{source.stem}_normalized.parquet'
        frame = preprocess_dataset(str(source), str(target))
        frame = frame.with_columns(pl.lit(source.name).alias('source_file'))
        generation_frames.append(frame)
    if not generation_frames:
        return pl.DataFrame()
    generation = pl.concat(generation_frames, how='diagonal_relaxed')
    if 'source_key' in generation.columns and 'equipment_id' not in generation.columns:
        generation = generation.with_columns(pl.col('source_key').cast(pl.String).alias('equipment_id'))

    weather_files = sorted(raw_dir.glob('*Weather*.csv'))
    weather_frames = []
    for source in weather_files:
        target = data_root / 'processed' / f'{source.stem}_normalized.parquet'
        frame = preprocess_dataset(str(source), str(target))
        weather_frames.append(frame)
    if not weather_frames or not {'plant_id', 'timestamp'}.issubset(generation.columns):
        return generation

    weather = pl.concat(weather_frames, how='diagonal_relaxed')
    join_keys = ['plant_id', 'timestamp']
    if not set(join_keys).issubset(weather.columns):
        return generation
    if weather.select(pl.struct(join_keys).is_duplicated().sum()).item() > 0:
        raise ValueError('Weather records contain duplicate plant/timestamp keys; refusing a row-multiplying join.')

    weather_values = [
        column for column in ['temperature_c', 'ambient_temperature_c', 'irradiance_w_m2', 'humidity_pct', 'wind_speed_m_s']
        if column in weather.columns
    ]
    if not weather_values:
        return generation
    return generation.join(
        weather.select(join_keys + weather_values),
        on=join_keys,
        how='left',
        validate='m:1',
    )


def list_dataset_files(base_dir: str | None = None) -> List[Path]:
    root = Path(base_dir or Path(__file__).resolve().parents[2] / 'data')
    files: List[Path] = []
    for folder in [root / 'raw', root / 'processed', root / 'sample']:
        if folder.exists():
            files.extend([p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == '.csv'])
    return sorted(files, key=lambda p: p.name.lower())


def load_dataset_summary() -> List[Dict[str, Any]]:
    items = []
    for file_path in list_dataset_files():
        try:
            summary = inspect_csv_file(str(file_path))
            processed_output = Path(__file__).resolve().parents[2] / 'data' / 'processed' / f'{file_path.stem}_normalized.parquet'
            items.append({
                'dataset_id': file_path.stem,
                'filename': file_path.name,
                'source': 'local filesystem',
                'data_source': 'simulated demo' if 'sample' in str(file_path) else 'local historical CSV',
                'file_size_bytes': file_path.stat().st_size,
                'row_count': summary['row_count'],
                'column_count': summary['column_count'],
                'date_start': summary['timestamp_min'],
                'date_end': summary['timestamp_max'],
                'column_names': summary['columns'],
                'data_types': summary['data_types'],
                'timestamp_timezone': summary['timestamp_timezone'],
                'measurement_units': summary['measurement_units'],
                'measurement_columns': summary['measurement_columns'],
                'missing_values': summary['missing_values'],
                'duplicate_rows': summary['duplicate_rows'],
                'invalid_measurements': summary['invalid_measurements'],
                'statistical_outliers': summary['statistical_outliers'],
                'invalid_measurements': summary['invalid_measurements'],
                'statistical_outliers': summary['statistical_outliers'],
                'supported_features': summary['supported_features'],
                'verified_failure_labels_exist': summary['verified_failure_labels_exist'],
                'suitable_for_anomaly_detection': summary['suitable_for_anomaly_detection'],
                'suitable_for_supervised_classification': summary['suitable_for_supervised_classification'],
                'status': 'available',
                'quality': 'good' if summary['duplicate_rows'] == 0 else 'warning',
                'preprocessing_status': 'completed' if processed_output.exists() else 'not started',
                'warnings': summary['warnings'],
                'errors': summary['errors'],
            })
        except Exception as exc:
            items.append({
                'dataset_id': file_path.stem,
                'filename': file_path.name,
                'source': 'local filesystem',
                'data_source': 'demo',
                'file_size_bytes': file_path.stat().st_size,
                'row_count': 0,
                'column_count': 0,
                'date_start': None,
                'date_end': None,
                'status': 'error',
                'quality': 'poor',
                'preprocessing_status': 'failed',
                'warnings': [],
                'errors': [str(exc)],
            })
    return items
