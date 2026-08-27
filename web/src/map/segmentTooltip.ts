import type { Segment } from '../api-types'
import { freewayDisplayName } from '../lib/freewayDisplayName'

export const SEGMENT_TOOLTIP_CLASS = 'segment-tooltip'

const ESTIMATED_TIERS = new Set(['partially_interpolated', 'majority_interpolated'])

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

const CONDITION_COLORS: Record<string, string> = {
  Light: '#22c55e',
  Medium: '#f97316',
  Heavy: '#dc2626',
  Blank: '#9ca3af',
}

function conditionLabel(segment: Segment): string {
  if (segment.condition !== 'Blank') return segment.condition
  return segment.persistent_blank ? 'No data (2+ hours)' : 'No data'
}

function dataQualityNote(segment: Segment): string | null {
  if (segment.condition === 'Blank') {
    return segment.persistent_blank
      ? 'This segment has reported no data continuously for at least 2 hours.'
      : 'No current reading for this segment.'
  }
  if (ESTIMATED_TIERS.has(segment.data_substitution_tier)) {
    return 'This reading is estimated (interpolated), not measured directly.'
  }
  if (segment.is_stale) {
    return 'This reading may be delayed.'
  }
  return null
}

export function renderSegmentTooltipHtml(segment: Segment): string {
  const dotColor = segment.persistent_blank ? '#4b5563' : (CONDITION_COLORS[segment.condition] ?? CONDITION_COLORS.Blank)
  const note = dataQualityNote(segment)

  return `
    <div class="${SEGMENT_TOOLTIP_CLASS}__body">
      <p class="${SEGMENT_TOOLTIP_CLASS}__freeway">${escapeHtml(freewayDisplayName(segment.freeway_name))}</p>
      <p class="${SEGMENT_TOOLTIP_CLASS}__segment">${escapeHtml(segment.segment_name)}</p>
      <p class="${SEGMENT_TOOLTIP_CLASS}__direction">${escapeHtml(segment.direction)}</p>
      <p class="${SEGMENT_TOOLTIP_CLASS}__condition">
        <span class="${SEGMENT_TOOLTIP_CLASS}__dot" style="background-color:${dotColor}"></span>
        ${escapeHtml(conditionLabel(segment))}
      </p>
      ${note ? `<p class="${SEGMENT_TOOLTIP_CLASS}__note">${escapeHtml(note)}</p>` : ''}
    </div>
  `
}
