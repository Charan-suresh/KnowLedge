import 'react-native-reanimated';

import React, { useEffect, useState } from 'react';
import { Tabs } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { useFonts } from 'expo-font';
import { ActivityIndicator, StyleSheet, Text, TouchableOpacity, View } from 'react-native';

import { detectCapabilities, getRuntimeConfig, setRuntimeConfig } from '../config';
import { runDatabaseMigrations } from '../db/migrations';
import { generateDeviceKeyIfMissing } from '../integrity/fingerprinter';
import { getModelSetupStatus, downloadE2BModel } from '../models/setup';
import { retryPendingSyncsIfWifi } from '../sync/sender';
import { colors, fonts } from '../theme';

SplashScreen.preventAutoHideAsync().catch(() => undefined);

export default function RootLayout() {
  const [ready, setReady] = useState(false);
  const [modeLabel, setModeLabel] = useState('detecting');
  const [showModelSetup, setShowModelSetup] = useState(false);
  const [setupProgress, setSetupProgress] = useState(0.67);
  const [setupMessage, setSetupMessage] = useState('Gemma 4 E2B');
  const [fontsLoaded] = useFonts({
    // Add concrete font files in assets/fonts and wire here.
  });

  useEffect(() => {
    (async () => {
      await runDatabaseMigrations();
      await generateDeviceKeyIfMissing();
      const mode = await detectCapabilities();
      setModeLabel(mode.replace(/_/g, ' '));
      const modelStatus = await getModelSetupStatus();
      if (modelStatus.requiresDownload && mode !== 'server_only') {
        setShowModelSetup(true);
      }
      await retryPendingSyncsIfWifi('CS301');
      setReady(true);
      await SplashScreen.hideAsync();
    })();
  }, []);

  if (!fontsLoaded || !ready) {
    return (
      <View style={styles.loading}>
        <ActivityIndicator color={colors.teal} />
        <Text style={styles.loadingText}>Setting up KnowLedge Mobile...</Text>
      </View>
    );
  }

  if (showModelSetup) {
    return (
      <View style={styles.setupScreen}>
        <Text style={styles.setupTitle}>Setting up KnowLedge</Text>
        <Text style={styles.setupBody}>
          We need to download AI models. Until then, the app can run in server-only mode.
        </Text>
        <View style={styles.progressTrack}>
          <View style={[styles.progressFill, { width: `${Math.max(5, Math.round(setupProgress * 100))}%` }]} />
        </View>
        <Text style={styles.progressLabel}>{Math.round(setupProgress * 100)}% - {setupMessage}</Text>
        <TouchableOpacity
          style={styles.downloadBtn}
          onPress={async () => {
            try {
              setSetupMessage('Downloading Gemma 4 E2B');
              await downloadE2BModel((fraction) => setSetupProgress(fraction));
              setSetupMessage('Model ready');
              setShowModelSetup(false);
            } catch (e) {
              setSetupMessage('Download failed - use server mode or retry');
            }
          }}
        >
          <Text style={styles.downloadText}>Download Model Now</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.skipBtn}
          onPress={() => {
            setRuntimeConfig({ inferenceMode: 'server_only' });
            setModeLabel('server only');
            setShowModelSetup(false);
          }}
        >
          <Text style={styles.skipText}>Skip - use server mode instead</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <>
      <View style={styles.badgeWrap}>
        <Text style={styles.badge}>Mode: {modeLabel}</Text>
        <Text style={styles.subBadge}>Server: {getRuntimeConfig().serverUrl}</Text>
      </View>
      <Tabs screenOptions={{ headerShown: true, tabBarActiveTintColor: colors.teal }}>
        <Tabs.Screen name="ledger" options={{ title: 'Ledger' }} />
        <Tabs.Screen name="progress" options={{ title: 'Progress' }} />
        <Tabs.Screen name="reports" options={{ title: 'Reports' }} />
        <Tabs.Screen name="solo" options={{ title: 'Solo' }} />
        <Tabs.Screen name="settings" options={{ title: 'Settings' }} />
        <Tabs.Screen name="index" options={{ href: null }} />
      </Tabs>
    </>
  );
}

const styles = StyleSheet.create({
  loading: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.cream,
  },
  loadingText: {
    marginTop: 10,
    fontFamily: fonts.mono,
    color: colors.inkMuted,
  },
  badgeWrap: {
    paddingTop: 44,
    paddingHorizontal: 14,
    backgroundColor: colors.cream,
  },
  badge: {
    fontFamily: fonts.mono,
    color: colors.ink,
    fontSize: 12,
  },
  subBadge: {
    fontFamily: fonts.mono,
    color: colors.inkMuted,
    fontSize: 11,
    marginTop: 2,
    marginBottom: 4,
  },
  setupScreen: {
    flex: 1,
    justifyContent: 'center',
    padding: 20,
    backgroundColor: colors.cream,
  },
  setupTitle: {
    fontFamily: fonts.serif,
    color: colors.ink,
    fontSize: 28,
  },
  setupBody: {
    marginTop: 10,
    fontFamily: fonts.sans,
    color: colors.inkMuted,
    fontSize: 14,
    lineHeight: 20,
  },
  progressTrack: {
    marginTop: 20,
    height: 12,
    borderRadius: 999,
    backgroundColor: colors.creamDeep,
    overflow: 'hidden',
  },
  progressFill: {
    width: '67%',
    height: 12,
    backgroundColor: colors.teal,
  },
  progressLabel: {
    marginTop: 8,
    fontFamily: fonts.mono,
    color: colors.inkMuted,
    fontSize: 12,
  },
  skipBtn: {
    marginTop: 20,
    alignSelf: 'flex-start',
    borderWidth: 1,
    borderColor: colors.rule,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 8,
    backgroundColor: colors.white,
  },
  downloadBtn: {
    marginTop: 16,
    alignSelf: 'flex-start',
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 8,
    backgroundColor: colors.teal,
  },
  downloadText: {
    fontFamily: fonts.sansMedium,
    color: colors.white,
    fontSize: 13,
  },
  skipText: {
    fontFamily: fonts.sansMedium,
    color: colors.ink,
    fontSize: 13,
  },
});
