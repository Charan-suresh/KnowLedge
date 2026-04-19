import React, { useMemo, useState } from 'react';
import { Alert, FlatList, Modal, ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';

import { ConceptCard } from '../components/ConceptCard';
import { SageSession } from '../components/SageSession';
import { StatCard } from '../components/StatCard';
import { useDebtLog } from '../hooks/useDebtLog';
import { useOrchestrator } from '../hooks/useOrchestrator';
import { insertDebtRow, updateDebtStatus } from '../db/queries';
import { colors, fonts, radius } from '../theme';

export default function LedgerScreen() {
  const { rows, refresh } = useDebtLog();
  const orchestrator = useOrchestrator();
  const [sheetOpen, setSheetOpen] = useState(false);
  const [pasteText, setPasteText] = useState('');
  const [sageOpen, setSageOpen] = useState(false);
  const [sageSession, setSageSession] = useState<any>(null);
  const [scouting, setScouting] = useState(false);

  const stats = useMemo(() => {
    const onLoan = rows.filter((r) => r.status === 'on_loan').length;
    const owned = rows.filter((r) => r.status === 'clear' || r.status === 'owned').length;
    const persists = rows.filter((r) => r.status === 'persists').length;
    const total = rows.length || 1;
    const debtScore = Math.round(((onLoan + persists) / total) * 100);
    return { onLoan, owned, persists, debtScore };
  }, [rows]);

  const onPasteSubmit = async () => {
    if (!pasteText.trim()) return;
    setScouting(true);
    const tags = await orchestrator.tagContent(pasteText.trim());
    for (const tag of tags) {
      await insertDebtRow(tag.concept, pasteText.trim(), tag.confidence);
    }
    setPasteText('');
    setSheetOpen(false);
    setScouting(false);
    await refresh();
    Alert.alert('Scout complete', `Tagged ${tags.length} concept(s).`);
  };

  const startSage = async (concept: string) => {
    const session = await orchestrator.startSageSession(concept);
    setSageSession(session);
    setSageOpen(true);
  };

  return (
    <View style={styles.container}>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.statsRow}>
        <StatCard label="On Loan" value={stats.onLoan} sub="borrowed" tone="amber" />
        <StatCard label="Owned" value={stats.owned} sub="cleared" tone="teal" />
        <StatCard label="Persists" value={stats.persists} sub="needs review" tone="coral" />
        <StatCard label="Debt Score" value={`${stats.debtScore}%`} sub="classical index" tone="ink" />
      </ScrollView>

      <FlatList
        data={rows}
        keyExtractor={(item) => String(item.id)}
        contentContainerStyle={styles.list}
        renderItem={({ item }) => (
          <ConceptCard
            concept={item.concept}
            subject={item.subject || 'General'}
            lastSeen={new Date(item.timestamp).toLocaleDateString()}
            status={item.status as any}
            confidence={item.confidence || 0.5}
            onStartSage={() => startSage(item.concept)}
            onReviewing={async () => {
              await updateDebtStatus(item.concept, 'on_loan');
              refresh();
            }}
            onPress={() => startSage(item.concept)}
          />
        )}
      />

      <TouchableOpacity style={styles.fab} onPress={() => setSheetOpen(true)}>
        <Text style={styles.fabText}>📋</Text>
      </TouchableOpacity>

      <Modal visible={sheetOpen} animationType="slide" transparent onRequestClose={() => setSheetOpen(false)}>
        <View style={styles.sheetBackdrop}>
          <View style={styles.sheet}>
            <Text style={styles.sheetTitle}>Paste AI Content</Text>
            <TextInput
              style={styles.input}
              multiline
              value={pasteText}
              onChangeText={setPasteText}
              placeholder="Paste content for Scout tagging"
            />
            <TouchableOpacity style={styles.btn} onPress={onPasteSubmit} disabled={scouting}>
              <Text style={styles.btnText}>{scouting ? 'Tagging...' : 'Tag Concepts'}</Text>
            </TouchableOpacity>
            <TouchableOpacity onPress={() => setSheetOpen(false)}><Text style={styles.cancel}>Cancel</Text></TouchableOpacity>
          </View>
        </View>
      </Modal>

      <SageSession
        visible={sageOpen}
        session={sageSession}
        onClose={() => {
          setSageOpen(false);
          setSageSession(null);
        }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.cream,
  },
  statsRow: {
    gap: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
  },
  list: {
    paddingHorizontal: 12,
    paddingBottom: 80,
  },
  fab: {
    position: 'absolute',
    bottom: 24,
    right: 20,
    width: 56,
    height: 56,
    borderRadius: 99,
    backgroundColor: colors.ink,
    justifyContent: 'center',
    alignItems: 'center',
  },
  fabText: {
    fontSize: 22,
  },
  sheetBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.2)',
    justifyContent: 'flex-end',
  },
  sheet: {
    backgroundColor: colors.white,
    borderTopLeftRadius: radius.xl,
    borderTopRightRadius: radius.xl,
    padding: 16,
  },
  sheetTitle: {
    fontFamily: fonts.serif,
    color: colors.ink,
    fontSize: 22,
    marginBottom: 10,
  },
  input: {
    minHeight: 120,
    borderWidth: 1,
    borderColor: colors.rule,
    borderRadius: radius.md,
    padding: 10,
    textAlignVertical: 'top',
    fontFamily: fonts.sans,
  },
  btn: {
    marginTop: 10,
    backgroundColor: colors.teal,
    borderRadius: radius.md,
    paddingVertical: 10,
    alignItems: 'center',
  },
  btnText: {
    color: colors.white,
    fontFamily: fonts.sansMedium,
  },
  cancel: {
    textAlign: 'center',
    marginTop: 10,
    color: colors.inkMuted,
    fontFamily: fonts.mono,
  },
});
