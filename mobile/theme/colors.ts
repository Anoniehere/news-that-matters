/**
 * theme/colors.ts — PRD §8.2 design tokens.
 * Single source of truth. Never hardcode hex values in components.
 */

export const Colors = {
  // ── Backgrounds ─────────────────────────────────────
  bgBase:     '#09090B',   // Zinc 950  — screen background
  bgSurface:  '#18181B',   // Zinc 900  — card background
  bgElevated: '#27272A',   // Zinc 800  — pressed / hover state

  // ── Borders ──────────────────────────────────────────
  borderSubtle: '#3F3F46', // Zinc 700

  // ── Text ─────────────────────────────────────────────
  textPrimary:   '#FAFAFA', // headings, body
  textSecondary: '#A1A1AA', // labels, metadata
  textMuted:     '#71717A', // timestamps, fine print

  // ── Accent ───────────────────────────────────────────
  accent:    '#818CF8', // Indigo 400 — interactive
  accentDim: '#312E81', // Indigo 900 — tag backgrounds

  // ── Trend / Status ───────────────────────────────────
  positive: '#34D399', // Emerald 400 — trend ≥ 0.75
  warning:  '#FBBF24', // Amber 400   — trend ≥ 0.50
  alert:    '#F87171', // Red 400     — trend < 0.50
} as const;

/**
 * Sector tag color map — PRD §8.2 table.
 * Keys are the exact sector names returned by the API.
 */
export type SectorColors = { bg: string; text: string };

export const SECTOR_COLORS: Record<string, SectorColors> = {
  'Technology':          { bg: '#312E81', text: '#A5B4FC' },
  'Finance':             { bg: '#451A03', text: '#FCD34D' },
  'Policy & Regulation': { bg: '#431407', text: '#FB923C' },
  'Labour & Employment': { bg: '#022C22', text: '#34D399' },
  'Healthcare':          { bg: '#052E16', text: '#4ADE80' },
  'Energy':              { bg: '#2E1065', text: '#C4B5FD' },
  'Defence & Security':  { bg: '#450A0A', text: '#F87171' },
  'Education':           { bg: '#082F49', text: '#38BDF8' },
  'Media & Entertainment': { bg: '#500724', text: '#F472B6' },
  'Retail & E-commerce': { bg: '#18181B', text: '#94A3B8' },
  'Real Estate':         { bg: '#18181B', text: '#94A3B8' },
  'Manufacturing':       { bg: '#18181B', text: '#94A3B8' },
  'Agriculture':         { bg: '#022C22', text: '#4ADE80' },
  // Fallback for any unmapped sector
  default:               { bg: '#27272A', text: '#A1A1AA' },
};

export function sectorColors(name: string): SectorColors {
  return SECTOR_COLORS[name] ?? SECTOR_COLORS['default'];
}

/** Trend bar fill color — PRD §8.6 */
export function trendColor(score: number): string {
  if (score >= 0.75) return Colors.positive;
  if (score >= 0.50) return Colors.warning;
  return Colors.alert;
}
