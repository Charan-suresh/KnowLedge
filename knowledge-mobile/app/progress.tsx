import React from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { BarChart, LineChart, PieChart } from 'react-native-gifted-charts';

import { colors, fonts, radius } from '../theme';

const debtData = [
  { value: 72, label: 'Mon' },
  { value: 68, label: 'Tue' },
  { value: 63, label: 'Wed' },
  { value: 58, label: 'Thu' },
  { value: 52, label: 'Fri' },
];

export default function ProgressScreen() {
  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Text style={styles.title}>Progress</Text>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>Debt Score Over Time</Text>
        <LineChart data={debtData} color={colors.amber} thickness={3} noOfSections={4} />
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>Clearing Velocity</Text>
        <BarChart data={debtData} frontColor={colors.teal} roundedTop />
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>Subject Breakdown</Text>
        <PieChart
          data={[
            { value: 40, color: colors.amber, text: 'Math' },
            { value: 28, color: colors.teal, text: 'Science' },
            { value: 18, color: colors.coral, text: 'Code' },
          ]}
          donut
          showText
          radius={90}
          textColor={colors.ink}
        />
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
    gap: 12,
  },
  title: {
    fontFamily: fonts.serif,
    fontSize: 26,
    color: colors.ink,
  },
  card: {
    backgroundColor: colors.white,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.rule,
    padding: 12,
  },
  cardTitle: {
    fontFamily: fonts.sansMedium,
    fontSize: 14,
    color: colors.ink,
    marginBottom: 8,
  },
});
