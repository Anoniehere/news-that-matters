/**
 * services/api.ts — typed wrapper around GET /brief.
 *
 * API_BASE: set to your machine's LAN IP when testing on a physical device
 * via Expo Go (phone can't reach "localhost" on your laptop).
 * For simulator: localhost works fine.
 *
 * Override at runtime by setting EXPO_PUBLIC_API_URL in your .env.
 */

import { BriefResponse } from '../types/brief';

export const API_BASE =
  process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8001';

export async function fetchBrief(): Promise<BriefResponse> {
  const res = await fetch(`${API_BASE}/brief`, {
    headers: { Accept: 'application/json' },
  });

  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${await res.text()}`);
  }

  return res.json() as Promise<BriefResponse>;
}

/** Format age in minutes into a human label. */
export function formatAge(ageMinutes: number): string {
  if (ageMinutes < 2)  return 'just now';
  if (ageMinutes < 60) return `${Math.round(ageMinutes)}m ago`;
  const h = Math.floor(ageMinutes / 60);
  const m = Math.round(ageMinutes % 60);
  return m > 0 ? `${h}h ${m}m ago` : `${h}h ago`;
}

/** Format an ISO datetime string to a relative label for article timestamps. */
export function formatRelativeDate(isoString: string): string {
  const date = new Date(isoString);
  const now  = new Date();
  const diffMs  = now.getTime() - date.getTime();
  const diffMin = diffMs / 60_000;
  const diffH   = diffMin / 60;
  const diffD   = diffH / 24;

  if (diffMin < 60)  return `${Math.round(diffMin)}m ago`;
  if (diffH   < 24)  return `${Math.round(diffH)}h ago`;
  if (diffD   < 2)   return 'Yesterday';
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}
