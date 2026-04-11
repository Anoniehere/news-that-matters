/**
 * theme/spacing.ts — PRD §8.4 spacing scale.
 * Base unit: 4px. Use these everywhere, never raw numbers.
 */
export const Spacing = {
  xs:  4,
  sm:  8,
  md:  12,
  lg:  16,
  xl:  24,
  xl2: 32,
  xl3: 48,
} as const;

export const Radius = {
  tag:  6,
  card: 16,
} as const;

export const Layout = {
  screenPadding: Spacing.lg,  // 16px horizontal gutter
  cardGap:       Spacing.md,  // 12px between cards
} as const;
