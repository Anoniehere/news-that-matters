/**
 * screens/ArticleListScreen.tsx — M6: full article list for a trending event.
 *
 * Layout:
 *   ┌─ custom header ─────────────────────────────────────┐
 *   │  ← Back                               ⬆ Share      │
 *   │  Event heading (2 lines max)                        │
 *   │  N sources  ·  sector tags                          │
 *   └─────────────────────────────────────────────────────┘
 *   [DATE HEADER — sticky] ─── Today ───
 *   ArticleItem
 *   ArticleItem
 *   [DATE HEADER — sticky] ─── Yesterday ───
 *   ArticleItem
 *   ─────────────────────────────────────
 *   Disclaimer footer (always visible)
 *
 * Articles are grouped by calendar day, newest → oldest within each group.
 * Tap article → expo-web-browser in-app sheet.
 * Share → native Share API (heading + source count).
 */

import React, { useCallback, useMemo } from 'react';
import {
  Pressable,
  SafeAreaView,
  SectionList,
  Share,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import ArticleItem from '../components/ArticleItem';
import DateGroupHeader from '../components/DateGroupHeader';
import SectorTag from '../components/SectorTag';
import { Colors } from '../theme/colors';
import { Layout, Radius, Spacing } from '../theme/spacing';
import {
  FontFamily,
  FontSize,
  LetterSpacing,
  LineHeight,
} from '../theme/typography';
import { EnrichedEvent, SourceArticle } from '../types/brief';

// ── Types ─────────────────────────────────────────────────────────────────────

interface Props {
  navigation: any;
  route: any;
}

interface Section {
  title: string;           // "Today" | "Yesterday" | "Apr 8"
  data: SourceArticle[];   // sorted newest → oldest
}

// ── Date helpers ──────────────────────────────────────────────────────────────

function isSameCalendarDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth()    === b.getMonth()    &&
    a.getDate()     === b.getDate()
  );
}

function dayLabel(isoString: string): string {
  const date      = new Date(isoString);
  const today     = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);

  if (isSameCalendarDay(date, today))     return 'Today';
  if (isSameCalendarDay(date, yesterday)) return 'Yesterday';
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

/** Group articles by calendar day, preserving newest-first order. */
function groupByDay(articles: SourceArticle[]): Section[] {
  // API already returns articles newest → oldest — maintain that order
  const sorted = [...articles].sort(
    (a, b) => new Date(b.published_at).getTime() - new Date(a.published_at).getTime(),
  );

  const map = new Map<string, SourceArticle[]>();
  for (const article of sorted) {
    const label = dayLabel(article.published_at);
    if (!map.has(label)) map.set(label, []);
    map.get(label)!.push(article);
  }

  return Array.from(map.entries()).map(([title, data]) => ({ title, data }));
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function ArticleListScreen({ navigation, route }: Props) {
  const event = (route.params?.event ?? {}) as EnrichedEvent;
  const sections: Section[] = useMemo(
    () => groupByDay(event.source_articles ?? []),
    [event.source_articles],
  );

  const handleShare = useCallback(async () => {
    const count = event.source_articles?.length ?? 0;
    try {
      await Share.share({
        title:   event.event_heading,
        message: `${event.event_heading}\n\n${count} ${count === 1 ? 'source' : 'sources'} · News That Matters`,
      });
    } catch {
      // user dismissed — no-op
    }
  }, [event]);

  return (
    <SafeAreaView style={styles.screen}>
      <SectionList
        sections={sections}
        keyExtractor={(item) => item.url}
        renderItem={({ item }) => <ArticleItem article={item} />}
        renderSectionHeader={({ section }) => (
          <DateGroupHeader label={section.title} />
        )}
        stickySectionHeadersEnabled
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.listContent}
        ListHeaderComponent={
          <ScreenHeader
            event={event}
            onBack={() => navigation.goBack()}
            onShare={handleShare}
          />
        }
        ListFooterComponent={<Disclaimer />}
        ListEmptyComponent={<EmptyState />}
      />
    </SafeAreaView>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function ScreenHeader({
  event,
  onBack,
  onShare,
}: {
  event: EnrichedEvent;
  onBack: () => void;
  onShare: () => void;
}) {
  const count = event.source_articles?.length ?? 0;

  return (
    <View style={styles.header}>
      {/* Nav row */}
      <View style={styles.navRow}>
        <Pressable
          onPress={onBack}
          style={({ pressed }) => [styles.navBtn, pressed && styles.navBtnPressed]}
          accessibilityRole="button"
          accessibilityLabel="Go back"
          hitSlop={12}
        >
          <Text style={styles.navBtnText}>← Back</Text>
        </Pressable>

        <Pressable
          onPress={onShare}
          style={({ pressed }) => [styles.navBtn, pressed && styles.navBtnPressed]}
          accessibilityRole="button"
          accessibilityLabel="Share this event"
          hitSlop={12}
        >
          <Text style={styles.navBtnText}>Share ⬆</Text>
        </Pressable>
      </View>

      {/* Event heading */}
      <Text style={styles.heading} numberOfLines={3}>
        {event.event_heading}
      </Text>

      {/* Meta row: source count + sector chips */}
      <View style={styles.metaRow}>
        <Text style={styles.sourceMeta}>
          {count} {count === 1 ? 'source' : 'sources'}
        </Text>
        <View style={styles.tags}>
          {(event.sectors_impacted ?? []).slice(0, 3).map((s) => (
            <SectorTag key={s.name} name={s.name} />
          ))}
        </View>
      </View>

      {/* Trend insight pill */}
      {!!event.trend_insight && (
        <View style={styles.insightPill}>
          <Text style={styles.insightText}>{event.trend_insight}</Text>
        </View>
      )}
    </View>
  );
}

function Disclaimer() {
  return (
    <View style={styles.disclaimer}>
      <Text style={styles.disclaimerText}>
        News That Matters surfaces trending news for informational purposes only.
        Not financial or investment advice. Always verify with primary sources.
      </Text>
    </View>
  );
}

function EmptyState() {
  return (
    <View style={styles.empty}>
      <Text style={styles.emptyEmoji}>📭</Text>
      <Text style={styles.emptyText}>No articles in this cluster yet.</Text>
    </View>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: Colors.bgBase,
  },
  listContent: {
    paddingBottom: Spacing.xl3,
  },

  // ── Header ──────────────────────────────────────────
  header: {
    paddingHorizontal: Layout.screenPadding,
    paddingTop: Spacing.md,
    paddingBottom: Spacing.lg,
    gap: Spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: Colors.borderSubtle,
  },
  navRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  navBtn: {
    paddingVertical: Spacing.xs,
    paddingHorizontal: Spacing.sm,
    borderRadius: Radius.tag,
    minHeight: 44,
    justifyContent: 'center',
  },
  navBtnPressed: {
    backgroundColor: Colors.bgElevated,
  },
  navBtnText: {
    fontFamily: FontFamily.bodyMedium,
    fontSize: FontSize.sm,
    color: Colors.accent,
  },
  heading: {
    fontFamily: FontFamily.displayBold,
    fontSize: FontSize.xl2,
    lineHeight: LineHeight.xl2,
    letterSpacing: LetterSpacing.tight,
    color: Colors.textPrimary,
  },
  metaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: Spacing.sm,
  },
  sourceMeta: {
    fontFamily: FontFamily.body,
    fontSize: FontSize.sm,
    color: Colors.textMuted,
    letterSpacing: LetterSpacing.wide,
  },
  tags: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.xs,
  },

  // ── Trend insight pill ───────────────────────────────
  insightPill: {
    backgroundColor: Colors.bgElevated,
    borderRadius: Radius.tag,
    paddingVertical: Spacing.xs,
    paddingHorizontal: Spacing.sm,
  },
  insightText: {
    fontFamily: FontFamily.body,
    fontSize: FontSize.xs,
    lineHeight: LineHeight.sm,
    color: Colors.textMuted,
    fontStyle: 'italic',
  },

  // ── Disclaimer ───────────────────────────────────────
  disclaimer: {
    marginTop: Spacing.xl,
    marginHorizontal: Layout.screenPadding,
    paddingVertical: Spacing.lg,
    paddingHorizontal: Spacing.md,
    borderTopWidth: 1,
    borderTopColor: Colors.borderSubtle,
  },
  disclaimerText: {
    fontFamily: FontFamily.body,
    fontSize: FontSize.xs,
    color: Colors.textMuted,
    textAlign: 'center',
    lineHeight: 16,
  },

  // ── Empty state ──────────────────────────────────────
  empty: {
    alignItems: 'center',
    paddingVertical: Spacing.xl3,
    gap: Spacing.md,
  },
  emptyEmoji: {
    fontSize: 36,
  },
  emptyText: {
    fontFamily: FontFamily.body,
    fontSize: FontSize.base,
    color: Colors.textMuted,
  },
});
