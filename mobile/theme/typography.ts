/**
 * theme/typography.ts — PRD §8.3 type scale.
 * Fonts loaded in App.tsx via expo-font / @expo-google-fonts.
 */
export const FontFamily = {
  displayBold:    'PlusJakartaSans_700Bold',
  displaySemiBold:'PlusJakartaSans_600SemiBold',
  body:           'Inter_400Regular',
  bodyMedium:     'Inter_500Medium',
  mono:           undefined,    // system monospace — platform default (Menlo/Courier)
} as const;

export const FontSize = {
  xs:   11,  // timestamps, source names
  sm:   13,  // sector tags, metadata
  base: 15,  // body text
  lg:   17,  // card heading
  xl:   20,  // screen title
  xl2:  24,  // article list heading
} as const;

export const LineHeight = {
  xs:   15,
  sm:   20,
  base: 24,
  lg:   24,
  xl:   26,
  xl2:  29,
} as const;

export const LetterSpacing = {
  tight:  -0.34,  // headings: -0.02em @ 17px
  normal:  0,
  wide:    0.88,  // labels: 0.08em @ 11px (tracking-widest)
} as const;
