import { describe, expect, it } from 'vitest';
import { buildAlertQuery } from './alerts';

describe('buildAlertQuery', () => {
  it('omits empty filters and applies the requested page window', () => {
    expect(buildAlertQuery({ plant_id: '4135001', equipment_id: '', status: 'Open' }, 2, 50)).toEqual({
      plant_id: '4135001',
      status: 'Open',
      limit: 50,
      offset: 100,
    });
  });

  it('keeps the first page offset at zero', () => {
    expect(buildAlertQuery({}, 0)).toEqual({ limit: 100, offset: 0 });
  });
});