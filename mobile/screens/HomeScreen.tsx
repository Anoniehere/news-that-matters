/**
 * screens/HomeScreen.tsx — the main feed.
 * FlatList of EventCards, pull-to-refresh, stale badge, ActivityIndicator.
 * ADR-011: ActivityIndicator used for loading state (not full SkeletonCard).
 */

import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  RefreshControl,
  SafeAreaView,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import EventCard from '../components/EventCard';
import { fetchBrief, formatAge } from '../services/api';
import { Colors } from '../theme/colors';
import { Layout, Spacing } from '../theme/spacing';
import { FontFamily, FontSize, LetterSpacing, LineHeight } from '../theme/typography';
import { BriefMeta, EnrichedEvent } from '../types/brief';

interface Props {
  navigation: any;
}

export default function HomeScreen({ navigation }: Props) {
  const [events,    setEvents]    = useState<EnrichedEvent[]>([]);
  const [meta,      setMeta]      = useState<BriefMeta | null>(null);
  const [loading,   setLoading]   = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error,     setError]     = useState<string | null>(null);

  const load = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else           setLoading(true);
    setError(null);

    try {
      const data = await fetchBrief();
      setEvents(data.brief.events);
      setMeta(data.meta);
    } catch (e: any) {
      setError(e.message ?? 'Could not load brief. Check your connection.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleCardPress = useCallback((event: EnrichedEvent) => {
    navigation.navigate('ArticleList', { event });
  }, [navigation]);

  // ── Loading state ────────────────────────────────────────────────────────
  if (loading) {
    return (
      <SafeAreaView style={styles.centered}>
        <ActivityIndicator size="large" color={Colors.accent} />
        <Text style={styles.loadingText}>Fetching signal…</Text>
      </SafeAreaView>
    );
  }

  // ── Error state ──────────────────────────────────────────────────────────
  if (error) {
    return (
      <SafeAreaView style={styles.centered}>
        <Text style={styles.errorEmoji}>⚡</Text>
        <Text style={styles.errorTitle}>Couldn't load brief</Text>
        <Text style={styles.errorBody}>{error}</Text>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.screen}>
      <FlatList
        data={events}
        keyExtractor={(item) => String(item.rank)}
        renderItem={({ item }) => (
          <EventCard event={item} onPress={() => handleCardPress(item)} />
        )}
        contentContainerStyle={styles.list}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => load(true)}
            tintColor={Colors.accent}
          />
        }
        ListHeaderComponent={<Header meta={meta} />}
        ListFooterComponent={<Footer />}
      />
    </SafeAreaView>
  );
}

// ── Sub-components ───────────────────────────────────────────────────────────

function Header({ meta }: { meta: BriefMeta | null }) {
  const age = meta ? formatAge(meta.age_minutes) : '';

  return (
    <View style={styles.header}>
      <Text style={styles.headerTitle}>⚡ Signal Brief</Text>
      <Text style={styles.headerSub}>
        {meta
          ? `Updated ${age}${meta.is_stale ? '  ·  ⚠ stale' : ''}`
          : 'Loading…'}
      </Text>
    </View>
  );
}

function Footer() {
  return (
    <View style={styles.footer}>
      <Text style={styles.footerText}>
        Signal Brief surfaces trending news for informational purposes only.
        Not financial or investment advice.
      </Text>
    </View>
  );
}

// ── Styles ───────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: Colors.bgBase,
  },
  centered: {
    flex: 1,
    backgroundColor: Colors.bgBase,
    alignItems: 'center',
    justifyContent: 'center',
    padding: Spacing.xl,
    gap: Spacing.md,
  },
  list: {
    paddingHorizontal: Layout.screenPadding,
    paddingBottom: Spacing.xl3,
  },

  // Header
  header: {
    paddingTop: Spacing.xl,
    paddingBottom: Spacing.lg,
    gap: Spacing.xs,
  },
  headerTitle: {
    fontFamily: FontFamily.displayBold,
    fontSize: FontSize.xl,
    lineHeight: LineHeight.xl,
    color: Colors.textPrimary,
    letterSpacing: LetterSpacing.tight,
  },
  headerSub: {
    fontFamily: FontFamily.body,
    fontSize: FontSize.sm,
    color: Colors.textMuted,
    letterSpacing: LetterSpacing.wide,
  },

  // Loading / Error
  loadingText: {
    fontFamily: FontFamily.body,
    fontSize: FontSize.sm,
    color: Colors.textMuted,
    letterSpacing: LetterSpacing.wide,
  },
  errorEmoji: {
    fontSize: 40,
  },
  errorTitle: {
    fontFamily: FontFamily.displayBold,
    fontSize: FontSize.lg,
    color: Colors.textPrimary,
  },
  errorBody: {
    fontFamily: FontFamily.body,
    fontSize: FontSize.base,
    color: Colors.textSecondary,
    textAlign: 'center',
  },

  // Footer
  footer: {
    paddingVertical: Spacing.xl,
    paddingHorizontal: Spacing.lg,
    borderTopWidth: 1,
    borderTopColor: Colors.borderSubtle,
    marginTop: Spacing.md,
  },
  footerText: {
    fontFamily: FontFamily.body,
    fontSize: FontSize.xs,
    color: Colors.textMuted,
    textAlign: 'center',
    lineHeight: 16,
  },
});
