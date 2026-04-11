/**
 * components/EventCard.tsx — full event card per PRD §8.6.
 *
 * Layout (top → bottom):
 *   3px gradient accent bar
 *   TrendBar (rank + score)
 *   Heading
 *   Dashed separator
 *   Summary
 *   WHY IT MATTERS label + body
 *   Sector tags
 *   Footer: source count + most-recent timestamp + chevron
 *
 * Press: scale(0.98) + opacity(0.85) over 80ms.
 */

import { LinearGradient } from 'expo-linear-gradient';
import React, { useRef } from 'react';
import {
  Animated,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import { Colors } from '../theme/colors';
import { Radius, Spacing } from '../theme/spacing';
import { FontFamily, FontSize, LetterSpacing, LineHeight } from '../theme/typography';
import { EnrichedEvent } from '../types/brief';
import { formatRelativeDate } from '../services/api';
import SectorTag from './SectorTag';
import TrendBar from './TrendBar';

interface Props {
  event: EnrichedEvent;
  onPress: () => void;
}

export default function EventCard({ event, onPress }: Props) {
  const scaleAnim   = useRef(new Animated.Value(1)).current;
  const opacityAnim = useRef(new Animated.Value(1)).current;

  const handlePressIn = () => {
    Animated.parallel([
      Animated.timing(scaleAnim,   { toValue: 0.98, duration: 80, useNativeDriver: true }),
      Animated.timing(opacityAnim, { toValue: 0.85, duration: 80, useNativeDriver: true }),
    ]).start();
  };

  const handlePressOut = () => {
    Animated.parallel([
      Animated.timing(scaleAnim,   { toValue: 1, duration: 80, useNativeDriver: true }),
      Animated.timing(opacityAnim, { toValue: 1, duration: 80, useNativeDriver: true }),
    ]).start();
  };

  const latestArticle  = event.source_articles[0];
  const lastUpdated    = latestArticle ? formatRelativeDate(latestArticle.published_at) : '';
  const sourceCount    = event.source_articles.length;

  return (
    <Animated.View style={[styles.wrapper, { transform: [{ scale: scaleAnim }], opacity: opacityAnim }]}>
      <Pressable
        onPress={onPress}
        onPressIn={handlePressIn}
        onPressOut={handlePressOut}
        accessibilityRole="button"
        accessibilityLabel={`News event: ${event.event_heading}`}
        style={styles.card}
      >
        {/* ── Top accent bar ───────────────────────────────── */}
        <LinearGradient
          colors={[Colors.accent, Colors.positive]}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 0 }}
          style={styles.accentBar}
        />

        <View style={styles.body}>
          {/* ── Trend bar + rank ─────────────────────────── */}
          <TrendBar score={event.trend_score} rank={event.rank} />

          {/* ── Heading ──────────────────────────────────── */}
          <Text style={styles.heading} numberOfLines={3}>
            {event.event_heading}
          </Text>

          {/* ── Dashed divider ───────────────────────────── */}
          <View style={styles.dashedLine} />

          {/* ── Summary ──────────────────────────────────── */}
          <Text style={styles.summary}>{event.summary}</Text>

          {/* ── Why it matters ───────────────────────────── */}
          <Text style={styles.whyLabel}>WHY IT MATTERS</Text>
          <View style={styles.whyUnderline} />
          <Text style={styles.why}>{event.why_it_matters}</Text>

          {/* ── Sector tags ──────────────────────────────── */}
          <View style={styles.tagsRow}>
            {event.sectors_impacted.slice(0, 4).map((s) => (
              <SectorTag key={s.name} name={s.name} />
            ))}
          </View>

          {/* ── Footer ───────────────────────────────────── */}
          <View style={styles.footer}>
            <Text style={styles.footerText}>
              {sourceCount} {sourceCount === 1 ? 'source' : 'sources'}
              {'  ·  '}
              Last: {lastUpdated}
            </Text>
            <Text style={[styles.footerText, { color: Colors.accent }]}>→</Text>
          </View>
        </View>
      </Pressable>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    marginBottom: Spacing.md,
  },
  card: {
    backgroundColor: Colors.bgSurface,
    borderRadius: Radius.card,
    borderWidth: 1,
    borderColor: Colors.borderSubtle,
    overflow: 'hidden',
  },
  accentBar: {
    height: 3,
    width: '100%',
  },
  body: {
    padding: Spacing.lg,
    gap: Spacing.md,
  },
  heading: {
    fontFamily: FontFamily.displayBold,
    fontSize: FontSize.lg,
    lineHeight: LineHeight.lg,
    letterSpacing: LetterSpacing.tight,
    color: Colors.textPrimary,
  },
  dashedLine: {
    borderBottomWidth: 1,
    borderBottomColor: Colors.borderSubtle,
    borderStyle: 'dashed',
    marginVertical: -Spacing.xs,
  },
  summary: {
    fontFamily: FontFamily.body,
    fontSize: FontSize.base,
    lineHeight: LineHeight.base,
    color: Colors.textPrimary,
  },
  whyLabel: {
    fontFamily: FontFamily.mono,
    fontSize: FontSize.xs,
    color: Colors.accent,
    letterSpacing: LetterSpacing.wide,
    marginBottom: -Spacing.xs,
  },
  whyUnderline: {
    height: 1,
    backgroundColor: Colors.accent,
    width: 80,
    marginBottom: -Spacing.xs,
  },
  why: {
    fontFamily: FontFamily.body,
    fontSize: FontSize.base,
    lineHeight: LineHeight.base,
    color: Colors.textSecondary,
  },
  tagsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.sm,
  },
  footer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingTop: Spacing.xs,
    borderTopWidth: 1,
    borderTopColor: Colors.borderSubtle,
  },
  footerText: {
    fontFamily: FontFamily.body,
    fontSize: FontSize.xs,
    color: Colors.textMuted,
  },
});
