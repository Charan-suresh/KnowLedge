import React from 'react';
import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import NetInfo from '@react-native-community/netinfo';

import { SyncStatus } from '../components/SyncStatus';
import { useSync } from '../hooks/useSync';
import { colors, fonts, radius } from '../theme';

export default function ReportsScreen() {
  const { status, trigger, networkType, lastSyncLabel } = useSync('CS301', '2026-W16');
  const [networkLabel, setNetworkLabel] = React.useState('checking');
  const [canSync, setCanSync] = React.useState(false);

  React.useEffect(() => {
    const sub = NetInfo.addEventListener((state) => {
      const isWifi = state.type === 'wifi' && Boolean(state.isConnected);
      setCanSync(isWifi);
      setNetworkLabel(isWifi ? 'Wi-Fi connected' : 'Sync disabled (requires Wi-Fi)');
    });
    return () => sub();
  }, []);

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Text style={styles.title}>Reports</Text>
      <View style={styles.card}>
        <Text style={styles.cardTitle}>Instructor Sync</Text>
        <Text style={styles.body}>Only anonymized concept aggregates are shared.</Text>
        <Text style={styles.network}>{networkLabel} · hook network: {networkType}</Text>
        <Text style={styles.network}>Last sync: {lastSyncLabel}</Text>
        <SyncStatus status={status} />
        <TouchableOpacity style={[styles.btn, !canSync && styles.btnDisabled]} disabled={!canSync} onPress={trigger}>
          <Text style={styles.btnText}>Share Weekly Aggregate</Text>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.cream,
  },
  content: {
    padding: 14,
  },
  title: {
    fontFamily: fonts.serif,
    fontSize: 26,
    color: colors.ink,
  },
  card: {
    marginTop: 12,
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.rule,
    borderRadius: radius.lg,
    padding: 12,
  },
  cardTitle: {
    fontFamily: fonts.sansMedium,
    fontSize: 15,
    color: colors.ink,
  },
  body: {
    marginTop: 6,
    marginBottom: 10,
    fontFamily: fonts.sans,
    color: colors.inkMuted,
  },
  network: {
    marginBottom: 8,
    fontFamily: fonts.mono,
    fontSize: 12,
    color: colors.inkMuted,
  },
  btn: {
    marginTop: 12,
    backgroundColor: colors.ink,
    borderRadius: radius.md,
    paddingVertical: 10,
    alignItems: 'center',
  },
  btnDisabled: {
    backgroundColor: colors.inkMuted,
  },
  btnText: {
    color: colors.white,
    fontFamily: fonts.sansMedium,
  },
});
