/**
 * components/ArticleItem.tsx — single article row for ArticleListScreen.
 *
 * Layout (left → right):
 *   [content: title (2 lines) + meta row (source · timestamp)] [→ arrow]
 *
 * Tap → opens article URL in expo-web-browser in-app sheet.
 * Min height 44pt (WCAG 2.2 AA tap target).
 */

import * as WebBrowser from 'expo-web-browser';
import React from 'react';
import {
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import { formatRelativeDate } from '../services/api';
import { Colors } from '../theme/colors';
import { Spacing } from '../theme/spacing';
import { FontFamily, FontSize, LineHeight } from '../theme/typography';
import { SourceArticle } from '../types/brief';

interface Props {
  article: SourceArticle;
}

export default function ArticleItem({ article }: Props) {
  const handlePress = async () => {
    await WebBrowser.openBrowserAsync(article.url, {
      toolbarColor: Colors.bgSurface,
      controlsColor: Colors.accent,
      presentationStyle: WebBrowser.WebBrowserPresentationStyle.PAGE_SHEET,
    });
  };

  const timestamp = formatRelativeDate(article.published_at);

  return (
    <Pressable
      onPress={handlePress}
      style={({ pressed }) => [styles.row, pressed && styles.rowPressed]}
      accessibilityRole="link"
      accessibilityLabel={`${article.title} — ${article.source_name}, ${timestamp}`}
      accessibilityHint="Opens article in browser"
    >
      <View style={styles.content}>
        <Text style={styles.title} numberOfLines={2}>
          {article.title}
        </Text>
        <View style={styles.meta}>
          <Text style={styles.source} numberOfLines={1}>
            {article.source_name}
          </Text>
          <Text style={styles.dot}>·</Text>
          <Text style={styles.timestamp}>{timestamp}</Text>
        </View>
      </View>
      <Text style={styles.arrow} accessibilityElementsHidden>→</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: Spacing.md,
    paddingHorizontal: Spacing.lg,
    gap: Spacing.sm,
    minHeight: 44,
    borderBottomWidth: 1,
    borderBottomColor: Colors.borderSubtle,
    backgroundColor: Colors.bgSurface,
  },
  rowPressed: {
    backgroundColor: Colors.bgElevated,
  },
  content: {
    flex: 1,
    gap: Spacing.xs,
  },
  title: {
    fontFamily: FontFamily.bodyMedium,
    fontSize: FontSize.base,
    lineHeight: LineHeight.base,
    color: Colors.textPrimary,
  },
  meta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
  },
  source: {
    fontFamily: FontFamily.body,
    fontSize: FontSize.xs,
    lineHeight: LineHeight.xs,
    color: Colors.accent,
    flexShrink: 1,
  },
  dot: {
    fontFamily: FontFamily.body,
    fontSize: FontSize.xs,
    color: Colors.textMuted,
  },
  timestamp: {
    fontFamily: FontFamily.body,
    fontSize: FontSize.xs,
    lineHeight: LineHeight.xs,
    color: Colors.textMuted,
  },
  arrow: {
    fontSize: FontSize.sm,
    color: Colors.accent,
    paddingLeft: Spacing.xs,
  },
});
