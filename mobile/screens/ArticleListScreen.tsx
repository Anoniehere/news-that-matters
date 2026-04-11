/**
 * screens/ArticleListScreen.tsx — M6 placeholder.
 * Full implementation in M6. Navigation stub only.
 */

import React from 'react';
import { SafeAreaView, Text, StyleSheet, Pressable } from 'react-native';

import { Colors } from '../theme/colors';
import { FontFamily, FontSize } from '../theme/typography';
import { Spacing } from '../theme/spacing';

interface Props {
  navigation: any;
  route: any;
}

export default function ArticleListScreen({ navigation, route }: Props) {
  const { event } = route.params ?? {};

  return (
    <SafeAreaView style={styles.screen}>
      <Pressable onPress={() => navigation.goBack()} style={styles.back}>
        <Text style={styles.backText}>← Back</Text>
      </Pressable>
      <Text style={styles.heading}>{event?.event_heading ?? 'Articles'}</Text>
      <Text style={styles.note}>Full article list coming in M6 🐾</Text>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: Colors.bgBase,
    padding: Spacing.lg,
    gap: Spacing.lg,
  },
  back: {
    paddingVertical: Spacing.sm,
  },
  backText: {
    fontFamily: FontFamily.body,
    fontSize: FontSize.base,
    color: Colors.accent,
  },
  heading: {
    fontFamily: FontFamily.displayBold,
    fontSize: FontSize.xl,
    color: Colors.textPrimary,
  },
  note: {
    fontFamily: FontFamily.body,
    fontSize: FontSize.sm,
    color: Colors.textMuted,
  },
});
