from datetime import datetime, timedelta
from pathlib import Path

import csv


base = Path(__file__).resolve().parent
path = base / 'demo_solar_data.csv'

rows = []
start = datetime(2025, 1, 1, 6, 0)
for day in range(15):
    for slot in range(24):
        ts = start + timedelta(days=day, hours=slot)
        for plant_id, equipment_id, base_power, base_temp in [
            ('PLANT-01', 'INV-01', 70, 38),
            ('PLANT-01', 'INV-02', 62, 35),
            ('PLANT-02', 'INV-03', 78, 42),
            ('PLANT-02', 'INV-04', 68, 39),
            ('PLANT-03', 'INV-05', 74, 41),
        ]:
            irradiance = 0 if ts.hour < 7 or ts.hour > 17 else 350 + (ts.hour * 22) + (day * 5)
            power = max(0.0, base_power + (irradiance / 30) - 14 + ((slot % 3) * 1.5))
            temperature = base_temp + max(0, (irradiance / 18) - 10) + ((slot % 4) * 0.7)
            voltage = 420 + (irradiance / 30) * 0.25
            current = power / max(voltage / 1000, 0.1)
            humidity = 35 + (day % 5) * 4 + (slot % 2) * 3
            wind_speed = 3.5 + (slot % 5) * 0.8
            rows.append({
                'timestamp': ts.strftime('%Y-%m-%d %H:%M:%S'),
                'plant_id': plant_id,
                'equipment_id': equipment_id,
                'power_kw': round(power, 2),
                'voltage_v': round(voltage, 2),
                'current_a': round(current, 2),
                'temperature_c': round(temperature, 2),
                'irradiance_w_m2': round(irradiance, 2),
                'humidity_pct': round(humidity, 2),
                'wind_speed_m_s': round(wind_speed, 2),
                'ambient_temp_c': round(base_temp - 4.5, 2),
            })

with path.open('w', newline='') as csvfile:
    writer = csv.DictWriter(
        csvfile,
        fieldnames=['timestamp', 'plant_id', 'equipment_id', 'power_kw', 'voltage_v', 'current_a', 'temperature_c', 'irradiance_w_m2', 'humidity_pct', 'wind_speed_m_s', 'ambient_temp_c'],
    )
    writer.writeheader()
    writer.writerows(rows)

print(f'Wrote {len(rows)} rows to {path}')
