/**
 * components/SectorTag.tsx — colour-coded sector pill chip.
 * Colors from PRD §8.2 sector map. PRD §8.6 chip spec.
 */

import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { sectorColors } from '../theme/colors';
import { FontFamily, FontSize } from '../theme/typography';
import { Radius, Spacing } from '../theme/spacing';

const SECTOR_EMOJI: Record<string, string> = {
  'Technology':            '💻',
  'Finance':               '💰',
  'Policy & Regulation':   '⚖️',
  'Labour & Employment':   '👷',
  'Healthcare':            '🏥',
  'Energy':                '⚡',
  'Defence & Security':    '🛡️',
  'Education':             '📚',
  'Media & Entertainment': '📺',
  'Retail & E-commerce':   '🛍️',
  'Real Estate':           '🏠',
  'Manufacturing':         '🏭',
  'Agriculture':           '🌾',
};

interface Props {
  name: string;
}

export default function SectorTag({ name }: Props) {
  const { bg, text } = sectorColors(name);
  const emoji = SECTOR_EMOJI[name] ?? '📌';

  return (
    <View
      style={[
        styles.chip,
        {
          backgroundColor: bg,
          borderColor: `${text}4D`,   // text at ~30% opacity
        },
      ]}
      accessibilityLabel={`Sector: ${name}`}
    >
      <Text style={styles.emoji}>{emoji}</Text>
      <Text style={[styles.label, { color: text }]}>{name}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: Spacing.sm + 2,   // 10px
    paddingVertical: Spacing.xs,          // 4px
    borderRadius: Radius.tag,
    borderWidth: 1,
  },
  emoji: {
    fontSize: 11,
  },
  label: {
    fontFamily: FontFamily.bodyMedium,
    fontSize: FontSize.sm,
    lineHeight: 18,
  },
});
