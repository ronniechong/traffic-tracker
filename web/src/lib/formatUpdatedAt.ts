const timeFormatter = new Intl.DateTimeFormat(undefined, {
  hour: 'numeric',
  minute: '2-digit',
  hour12: true,
})

export function formatUpdatedAt(updatedAtUtc: string | undefined): string | null {
  if (!updatedAtUtc) return null
  const date = new Date(updatedAtUtc)
  if (Number.isNaN(date.getTime())) return null
  return timeFormatter.format(date)
}
