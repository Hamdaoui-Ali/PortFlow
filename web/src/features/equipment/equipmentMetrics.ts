export function formatPercentage(value: number | null | undefined): string {
  if (value === null || value === undefined) return "Unavailable";
  return `${(value * 100).toFixed(1)}%`;
}

export function formatMetric(value: number | null | undefined, unit: "min" | "hr"): string {
  if (value === null || value === undefined) return "Unavailable";
  const displayValue = Number.isInteger(value) ? value : value.toFixed(1);
  return `${displayValue} ${unit}`;
}

export function formatMinutes(value: number | null | undefined): string {
  return formatMetric(value, "min");
}
