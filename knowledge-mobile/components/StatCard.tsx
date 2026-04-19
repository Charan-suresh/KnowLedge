import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { colors, fonts, radius } from '../theme';

type Props = {
  label: string;
  value: string | number;
  sub: string;
  tone: 'amber' | 'teal' | 'coral' | 'ink';
};

const toneMap = {
  amber: colors.amberLight,
  teal: colors.tealLight,
  coral: colors.coralLight,
  ink: colors.creamDeep,
};

export function StatCard({ label, value, sub, tone }: Props) {
  return (
    <View style={[styles.card, { backgroundColor: toneMap[tone] }]}>
      <Text style={styles.label}>{label}</Text>
      <Text style={styles.value}>{value}</Text>
      <Text style={styles.sub}>{sub}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    minWidth: 140,
    borderRadius: radius.lg,
    padding: 14,
    borderWidth: 1,
    borderColor: colors.rule,
  },
  label: {
    fontFamily: fonts.mono,
    color: colors.inkMuted,
    fontSize: 12,
  },
  value: {
    fontFamily: fonts.serif,
    color: colors.ink,
    fontSize: 26,
    marginTop: 4,
  },
  sub: {
    fontFamily: fonts.sans,
    color: colors.inkMuted,
    fontSize: 12,
    marginTop: 4,
  },
});
