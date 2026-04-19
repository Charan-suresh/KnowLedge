import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { colors, fonts, radius } from '../theme';

export function DebtMap({ onLoan, persists, owned }: { onLoan: number; persists: number; owned: number }) {
  return (
    <View style={styles.card}>
      <Text style={styles.title}>Debt Overview</Text>
      <Text style={styles.row}>On Loan: {onLoan}</Text>
      <Text style={styles.row}>Persists: {persists}</Text>
      <Text style={styles.row}>Owned: {owned}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.white,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.rule,
    padding: 14,
  },
  title: {
    fontFamily: fonts.serif,
    fontSize: 16,
    color: colors.ink,
  },
  row: {
    marginTop: 6,
    fontFamily: fonts.mono,
    color: colors.inkMuted,
    fontSize: 12,
  },
});
