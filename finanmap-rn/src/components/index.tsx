/**
 * FinanMap Pro — Componentes Reutilizáveis
 */

import React from 'react';
import {
  View, Text, TouchableOpacity, ActivityIndicator,
  StyleSheet, ViewStyle, TextStyle,
} from 'react-native';
import { Colors, Typography, Spacing, Radii, Shadows } from '../theme';

// ── MetricCard ────────────────────────────────────────────────────────────────

interface MetricCardProps {
  label:     string;
  value:     string;
  sub?:      string;
  subColor?: string;
  accent?:   string;
  style?:    ViewStyle;
}

export function MetricCard({ label, value, sub, subColor, accent = Colors.purple, style }: MetricCardProps) {
  return (
    <View style={[styles.metricCard, { borderTopColor: accent }, style]}>
      <Text style={styles.metricLabel}>{label}</Text>
      <Text style={[styles.metricValue, { color: accent }]}>{value}</Text>
      {sub ? <Text style={[styles.metricSub, subColor ? { color: subColor } : {}]}>{sub}</Text> : null}
    </View>
  );
}

// ── Card ─────────────────────────────────────────────────────────────────────

interface CardProps {
  children:  React.ReactNode;
  style?:    ViewStyle;
  padding?:  number;
}

export function Card({ children, style, padding = Spacing.lg }: CardProps) {
  return (
    <View style={[styles.card, { padding }, style]}>
      {children}
    </View>
  );
}

// ── SectionHeader ─────────────────────────────────────────────────────────────

export function SectionHeader({ title, sub }: { title: string; sub?: string }) {
  return (
    <View style={{ marginBottom: sub ? Spacing.md : Spacing.sm }}>
      <Text style={styles.sectionTitle}>{title}</Text>
      {sub ? <Text style={styles.sectionSub}>{sub}</Text> : null}
    </View>
  );
}

// ── Chip ─────────────────────────────────────────────────────────────────────

interface ChipProps {
  label:   string;
  bg:      string;
  color:   string;
  style?:  ViewStyle;
}

export function Chip({ label, bg, color, style }: ChipProps) {
  return (
    <View style={[styles.chip, { backgroundColor: bg }, style]}>
      <Text style={[styles.chipText, { color }]}>{label}</Text>
    </View>
  );
}

// ── Button ────────────────────────────────────────────────────────────────────

interface ButtonProps {
  label:       string;
  onPress:     () => void;
  variant?:    'primary' | 'secondary' | 'ghost';
  loading?:    boolean;
  disabled?:   boolean;
  style?:      ViewStyle;
  icon?:       React.ReactNode;
}

export function Button({
  label, onPress, variant = 'primary',
  loading, disabled, style, icon,
}: ButtonProps) {
  const isPrimary = variant === 'primary';
  const isGhost   = variant === 'ghost';

  return (
    <TouchableOpacity
      onPress={onPress}
      disabled={disabled || loading}
      activeOpacity={0.8}
      style={[
        styles.button,
        isPrimary && styles.buttonPrimary,
        isGhost   && styles.buttonGhost,
        (disabled || loading) && styles.buttonDisabled,
        style,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={isPrimary ? '#fff' : Colors.purple} size="small" />
      ) : (
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
          {icon}
          <Text style={[styles.buttonText, isPrimary && { color: '#fff' }, isGhost && { color: Colors.purple }]}>
            {label}
          </Text>
        </View>
      )}
    </TouchableOpacity>
  );
}

// ── ProgressBar ───────────────────────────────────────────────────────────────

interface ProgressBarProps {
  progress:   number;    // 0–100
  color?:     string;
  height?:    number;
  style?:     ViewStyle;
}

export function ProgressBar({ progress, color = Colors.purple, height = 8, style }: ProgressBarProps) {
  return (
    <View style={[{ height, backgroundColor: Colors.bg, borderRadius: height / 2 }, style]}>
      <View style={{
        width: `${Math.min(100, Math.max(0, progress))}%`,
        height, borderRadius: height / 2, backgroundColor: color,
      }} />
    </View>
  );
}

// ── AllocBar ──────────────────────────────────────────────────────────────────

export function AllocBar({ alloc }: { alloc: Record<string, number> }) {
  const geneColors = Colors.gene as Record<string, string>;
  const entries = Object.entries(alloc).filter(([, v]) => v > 0);
  return (
    <View style={{ flexDirection: 'row', height: 6, borderRadius: 3, overflow: 'hidden', gap: 1 }}>
      {entries.map(([k, v]) => (
        <View key={k} style={{ flex: v, backgroundColor: geneColors[k] || Colors.purple }} />
      ))}
    </View>
  );
}

// ── LiveDot ───────────────────────────────────────────────────────────────────

export function LiveDot({ color = Colors.green }: { color?: string }) {
  return (
    <View style={{ width: 7, height: 7, borderRadius: 3.5, backgroundColor: color }} />
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  metricCard: {
    backgroundColor: Colors.surface,
    borderRadius:    Radii.lg,
    padding:         Spacing.lg,
    borderTopWidth:  3,
    borderTopColor:  Colors.purple,
    borderWidth:     1,
    borderColor:     Colors.border,
    ...Shadows.sm,
  },
  metricLabel: {
    fontSize:    Typography.xs,
    color:       Colors.text3,
    fontWeight:  Typography.semibold,
    textTransform:'uppercase',
    letterSpacing:0.5,
    marginBottom:Spacing.xs,
  },
  metricValue: {
    fontSize:   Typography.xl,
    fontWeight: Typography.black,
    color:      Colors.text,
    lineHeight: Typography.xl * 1.1,
  },
  metricSub: {
    fontSize:   Typography.xs,
    color:      Colors.text3,
    marginTop:  Spacing.xs,
  },

  card: {
    backgroundColor: Colors.surface,
    borderRadius:    Radii.lg,
    borderWidth:     1,
    borderColor:     Colors.border,
    ...Shadows.sm,
  },

  sectionTitle: {
    fontSize:   Typography.md,
    fontWeight: Typography.bold,
    color:      Colors.text,
  },
  sectionSub: {
    fontSize:   Typography.sm,
    color:      Colors.text3,
    marginTop:  2,
  },

  chip: {
    paddingHorizontal: Spacing.sm,
    paddingVertical:   3,
    borderRadius:      Radii.full,
    alignSelf:         'flex-start',
  },
  chipText: {
    fontSize:   Typography.xs,
    fontWeight: Typography.bold,
  },

  button: {
    paddingVertical:   Spacing.md,
    paddingHorizontal: Spacing.xl,
    borderRadius:      Radii.md,
    alignItems:        'center',
    justifyContent:    'center',
    borderWidth:       1,
    borderColor:       Colors.border,
    backgroundColor:   Colors.surface,
  },
  buttonPrimary: {
    backgroundColor: Colors.purple,
    borderColor:     Colors.purple,
  },
  buttonGhost: {
    backgroundColor: Colors.purpleLight,
    borderColor:     Colors.purpleMid,
  },
  buttonDisabled: {
    opacity: 0.45,
  },
  buttonText: {
    fontSize:   Typography.base,
    fontWeight: Typography.bold,
    color:      Colors.text,
  },
});
