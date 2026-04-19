import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { colors, fonts } from '../theme';

export function SyncStatus({ status }: { status: string }) {
  const ok = status === 'sent' || status === 'ok';
  return (
    <View style={styles.row}>
      <View style={[styles.dot, { backgroundColor: ok ? colors.teal : colors.amber }]} />
      <Text style={styles.text}>Sync: {status || 'idle'}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  dot: {
    width: 10,
    height: 10,
    borderRadius: 99,
  },
  text: {
    fontFamily: fonts.mono,
    color: colors.inkMuted,
    fontSize: 12,
  },
});
