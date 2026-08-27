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

function renderDirectionRow(segment: Segment): string {
  const dotColor = segment.persistent_blank ? '#4b5563' : (CONDITION_COLORS[segment.condition] ?? CONDITION_COLORS.Blank)
  const note = dataQualityNote(segment)

  return `
    <div class="${SEGMENT_TOOLTIP_CLASS}__direction-row">
      <p class="${SEGMENT_TOOLTIP_CLASS}__direction">${escapeHtml(segment.direction)}</p>
      <p class="${SEGMENT_TOOLTIP_CLASS}__condition">
        <span class="${SEGMENT_TOOLTIP_CLASS}__dot" style="background-color:${dotColor}"></span>
        ${escapeHtml(conditionLabel(segment))}
      </p>
      ${note ? `<p class="${SEGMENT_TOOLTIP_CLASS}__note">${escapeHtml(note)}</p>` : ''}
    </div>
  `
}

function renderNamedGroup(freewayName: string, segmentName: string, segments: Segment[]): string {
  return `
    <div class="${SEGMENT_TOOLTIP_CLASS}__named-group">
      <p class="${SEGMENT_TOOLTIP_CLASS}__freeway">${escapeHtml(freewayDisplayName(freewayName))}</p>
      <p class="${SEGMENT_TOOLTIP_CLASS}__segment">${escapeHtml(segmentName)}</p>
      ${segments.map(renderDirectionRow).join('')}
    </div>
  `
}

/** Segments passed in are whatever fell within the click hit-test buffer --
 * usually both directions of the same stretch, but proximity alone can't
 * guarantee that, so segments are grouped by their own freeway+name rather
 * than assumed to share one. */
export function renderSegmentTooltipHtml(segments: Segment[]): string {
  const groups = new Map<string, { freewayName: string; segmentName: string; segments: Segment[] }>()
  for (const segment of segments) {
    const key = `${segment.freeway_name}::${segment.segment_name}`
    const group = groups.get(key)
    if (group) {
      group.segments.push(segment)
    } else {
      groups.set(key, { freewayName: segment.freeway_name, segmentName: segment.segment_name, segments: [segment] })
    }
  }

  const body = [...groups.values()]
    .map((g) => renderNamedGroup(g.freewayName, g.segmentName, g.segments))
    .join(`<hr class="${SEGMENT_TOOLTIP_CLASS}__divider" />`)

  return `<div class="${SEGMENT_TOOLTIP_CLASS}__body">${body}</div>`
}
