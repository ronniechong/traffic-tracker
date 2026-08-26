// The API's own `freeway_name` labels are inconsistent with common usage
// for at least one freeway -- EastLink appears as "E'link". Everything not
// listed here is shown as-is.
const DISPLAY_NAME_OVERRIDES: Record<string, string> = {
  "E'link": 'EastLink',
}

export function freewayDisplayName(freewayName: string): string {
  return DISPLAY_NAME_OVERRIDES[freewayName] ?? freewayName
}
