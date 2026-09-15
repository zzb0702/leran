// Backend stores naive UTC datetimes (datetime.utcnow) — anchor them to UTC
// so the local calendar day matches when the card was actually created.
export function parseCreated(v: string): Date {
  return new Date(/[zZ+]/.test(v) ? v : `${v}Z`);
}

/** Local "YYYY-MM-DD" key for a stored created_at value. */
export function localDayKey(v: string): string {
  const d = parseCreated(v);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
    d.getDate(),
  ).padStart(2, "0")}`;
}

export function dayLabel(d: Date): string {
  const now = new Date();
  const startOf = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const diffDays = Math.round((startOf(now) - startOf(d)) / 86400000);
  const week = ["日", "一", "二", "三", "四", "五", "六"][d.getDay()];
  if (diffDays <= 0) return `今天 · 周${week}`;
  if (diffDays === 1) return `昨天 · 周${week}`;
  if (diffDays < 7) return `${diffDays} 天前 · 周${week}`;
  const md = `${d.getMonth() + 1}月${d.getDate()}日 周${week}`;
  return d.getFullYear() === now.getFullYear() ? md : `${d.getFullYear()}年${md}`;
}

/** Label for a local "YYYY-MM-DD" key. */
export function dayKeyLabel(key: string): string {
  return dayLabel(new Date(`${key}T00:00:00`));
}
