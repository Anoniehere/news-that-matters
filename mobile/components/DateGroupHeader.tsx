/**
 * components/DateGroupHeader.tsx — sticky section header for article date groups.
 *
 * Displays:  ──── Today ─────  (or Yesterday / Apr 8)
 *
 * Used as the `renderSectionHeader` in ArticleListScreen's SectionList.
 * Sticky behaviour is controlled by the parent SectionList prop.
 */

import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { Colors } from '../theme/colors';
import { Spacing } from '../theme/spacing';
import { FontFamily, FontSize, LetterSpacing } from '../theme/typography';

interface Props {
  label: string;  // "Today" | "Yesterday" | "Apr 8"
}

export default function DateGroupHeader({ label }: Props) {
  return (
    <View style={styles.container}>
      <View style={styles.line} />
      <Text style={styles.label}>{label}</Text>
      <View style={styles.line} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.sm,
    backgroundColor: Colors.bgBase,   // opaque so sticky doesn't bleed through
  },
  line: {
    flex: 1,
    height: 1,
    backgroundColor: Colors.borderSubtle,
  },
  label: {
    fontFamily: FontFamily.body,
    fontSize: FontSize.xs,
    color: Colors.textMuted,
    letterSpacing: LetterSpacing.wide,
    textTransform: 'uppercase',
  },
});
