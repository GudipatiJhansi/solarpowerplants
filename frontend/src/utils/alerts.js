export function buildAlertQuery(filters, page, pageSize = 100) {
  return Object.fromEntries(
    Object.entries({ ...filters, limit: pageSize, offset: page * pageSize })
      .filter(([, value]) => value !== '' && value != null),
  );
}