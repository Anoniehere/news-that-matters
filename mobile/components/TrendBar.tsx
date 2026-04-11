/**
 * components/TrendBar.tsx — animated trend score bar.
 * Animates 0 → score% on mount (600ms ease-out). PRD §8.5, §8.6.
 */

import React, { useEffect, useRef } from 'react';
import { Animated, StyleSheet, Text, View } from 'react-native';

import { Colors, trendColor } from '../theme/colors';
import { FontFamily, FontSize, LetterSpacing } from '../theme/typography';
import { Spacing } from '../theme/spacing';

interface Props {
  score: number;   // 0.0–1.0
  rank: number;
}

export default function TrendBar({ score, rank }: Props) {
  const widthAnim = useRef(new Animated.Value(0)).current;
  const pct = Math.round(score * 100);
  const fill = trendColor(score);

  useEffect(() => {
    Animated.timing(widthAnim, {
      toValue: score,
      duration: 600,
      useNativeDriver: false,   // width animation requires JS driver
    }).start();
  }, [score]);

  const animatedWidth = widthAnim.interpolate({
    inputRange:  [0, 1],
    outputRange: ['0%', '100%'],
    extrapolate: 'clamp',
  });

  return (
    <View style={styles.container}>
      {/* Rank + label row */}
      <View style={styles.labelRow}>
        <Text style={styles.rank}>#{rank}</Text>
        <Text style={styles.label}>TRENDING</Text>
        <Text style={[styles.pct, { color: fill }]}>{pct}%</Text>
      </View>

      {/* Bar track + fill */}
      <View style={styles.track}>
        <Animated.View style={[styles.fill, { width: animatedWidth, backgroundColor: fill }]} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: Spacing.xs,
  },
  labelRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  rank: {
    fontFamily: FontFamily.mono,
    fontSize: FontSize.sm,
    color: Colors.textSecondary,
    letterSpacing: LetterSpacing.wide,
    minWidth: 24,
  },
  label: {
    fontFamily: FontFamily.mono,
    fontSize: FontSize.xs,
    color: Colors.textMuted,
    letterSpacing: LetterSpacing.wide,
    flex: 1,
  },
  pct: {
    fontFamily: FontFamily.mono,
    fontSize: FontSize.sm,
    letterSpacing: LetterSpacing.tight,
  },
  track: {
    height: 4,
    backgroundColor: Colors.borderSubtle,
    borderRadius: 2,
    overflow: 'hidden',
  },
  fill: {
    height: 4,
    borderRadius: 2,
  },
});
