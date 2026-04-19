import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import Swipeable from 'react-native-gesture-handler/ReanimatedSwipeable';

import { colors, fonts, radius } from '../theme';

type Props = {
  concept: string;
  subject: string;
  lastSeen: string;
  status: 'on_loan' | 'clear' | 'owned' | 'persists';
  confidence: number;
  onStartSage: () => void;
  onReviewing: () => void;
  onPress: () => void;
};

function statusTone(status: Props['status']) {
  if (status === 'persists') return { bg: colors.coralLight, fg: colors.coral, label: 'Persists' };
  if (status === 'clear' || status === 'owned') return { bg: colors.tealLight, fg: colors.teal, label: 'Owned' };
  return { bg: colors.amberLight, fg: colors.amber, label: 'On Loan' };
}

export function ConceptCard(props: Props) {
  const tone = statusTone(props.status);

  return (
    <Swipeable
      renderLeftActions={() => (
        <TouchableOpacity style={[styles.action, styles.left]} onPress={props.onStartSage}>
          <Text style={styles.actionText}>🦉 Start Sage</Text>
        </TouchableOpacity>
      )}
      renderRightActions={() => (
        <TouchableOpacity style={[styles.action, styles.right]} onPress={props.onReviewing}>
          <Text style={styles.actionText}>Reviewing</Text>
        </TouchableOpacity>
      )}
    >
      <TouchableOpacity style={styles.card} onPress={props.onPress}>
        <Text style={styles.concept}>{props.concept}</Text>
        <Text style={styles.meta}>{props.subject} · {props.lastSeen}</Text>
        <View style={[styles.pill, { backgroundColor: tone.bg }]}>
          <Text style={[styles.pillText, { color: tone.fg }]}>{tone.label}</Text>
        </View>
        <View style={styles.track}>
          <View style={[styles.fill, { width: `${Math.round((props.confidence || 0) * 100)}%`, backgroundColor: tone.fg }]} />
        </View>
      </TouchableOpacity>
    </Swipeable>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.white,
    borderRadius: radius.lg,
    padding: 14,
    borderWidth: 1,
    borderColor: colors.rule,
    marginBottom: 10,
  },
  concept: {
    fontFamily: fonts.serif,
    fontSize: 18,
    color: colors.ink,
  },
  meta: {
    marginTop: 4,
    fontFamily: fonts.mono,
    fontSize: 12,
    color: colors.inkMuted,
  },
  pill: {
    marginTop: 8,
    alignSelf: 'flex-start',
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 999,
  },
  pillText: {
    fontFamily: fonts.sansMedium,
    fontSize: 12,
  },
  track: {
    marginTop: 10,
    height: 5,
    backgroundColor: colors.creamDeep,
    borderRadius: 99,
    overflow: 'hidden',
  },
  fill: {
    height: 5,
    borderRadius: 99,
  },
  action: {
    justifyContent: 'center',
    alignItems: 'center',
    width: 120,
    borderRadius: radius.md,
    marginVertical: 5,
  },
  left: {
    backgroundColor: colors.teal,
  },
  right: {
    backgroundColor: colors.amber,
  },
  actionText: {
    color: colors.white,
    fontFamily: fonts.sansMedium,
    fontSize: 12,
  },
});
