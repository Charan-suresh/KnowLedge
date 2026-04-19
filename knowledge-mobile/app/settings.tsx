import React, { useState } from 'react';
import { Alert, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';

import { InferenceMode, getRuntimeConfig, setRuntimeConfig } from '../config';
import { downloadE2BModel, getModelSetupStatus } from '../models/setup';
import { colors, fonts, radius } from '../theme';

const MODES: InferenceMode[] = ['on_device_full', 'on_device_scout', 'server_only'];

export default function SettingsScreen() {
  const runtime = getRuntimeConfig();
  const [mode, setMode] = useState<InferenceMode>(runtime.inferenceMode);
  const [server, setServer] = useState(runtime.serverUrl);
  const [modelStatus, setModelStatus] = useState('checking');

  React.useEffect(() => {
    (async () => {
      const status = await getModelSetupStatus();
      setModelStatus(`E2B: ${status.e2bStatus} · E4B: ${status.e4bStatus}`);
    })();
  }, []);

  const save = () => {
    setRuntimeConfig({ inferenceMode: mode, serverUrl: server });
    Alert.alert('Saved', 'Runtime configuration updated.');
  };

  return (
    <View style={styles.screen}>
      <Text style={styles.title}>Settings</Text>
      <Text style={styles.section}>Inference Mode</Text>
      <View style={styles.row}>
        {MODES.map((m) => (
          <TouchableOpacity key={m} style={[styles.modeBtn, mode === m && styles.modeBtnActive]} onPress={() => setMode(m)}>
            <Text style={[styles.modeText, mode === m && styles.modeTextActive]}>{m}</Text>
          </TouchableOpacity>
        ))}
      </View>

      <Text style={styles.section}>University Server</Text>
      <TextInput value={server} onChangeText={setServer} style={styles.input} autoCapitalize="none" />

      <Text style={styles.section}>Model Status</Text>
      <Text style={styles.modelText}>{modelStatus}</Text>

      <TouchableOpacity
        style={styles.secondaryBtn}
        onPress={async () => {
          setModelStatus('downloading E2B...');
          try {
            await downloadE2BModel();
            setModelStatus('E2B downloaded');
            Alert.alert('Done', 'E2B model downloaded successfully.');
          } catch {
            setModelStatus('download failed');
            Alert.alert('Download failed', 'Could not download the model.');
          }
        }}
      >
        <Text style={styles.secondaryText}>Download E2B Model</Text>
      </TouchableOpacity>

      <TouchableOpacity style={styles.saveBtn} onPress={save}>
        <Text style={styles.saveText}>Save</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.cream,
    padding: 16,
  },
  title: {
    fontFamily: fonts.serif,
    fontSize: 26,
    color: colors.ink,
  },
  section: {
    marginTop: 14,
    marginBottom: 8,
    fontFamily: fonts.mono,
    color: colors.inkMuted,
    fontSize: 12,
  },
  row: {
    gap: 8,
  },
  modeBtn: {
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.rule,
    padding: 10,
    backgroundColor: colors.white,
  },
  modeBtnActive: {
    borderColor: colors.teal,
    backgroundColor: colors.tealLight,
  },
  modeText: {
    fontFamily: fonts.sans,
    color: colors.ink,
  },
  modeTextActive: {
    color: colors.teal,
    fontFamily: fonts.sansMedium,
  },
  input: {
    borderWidth: 1,
    borderColor: colors.rule,
    borderRadius: radius.md,
    backgroundColor: colors.white,
    paddingHorizontal: 10,
    paddingVertical: 10,
    fontFamily: fonts.sans,
  },
  modelText: {
    marginBottom: 8,
    fontFamily: fonts.mono,
    color: colors.inkMuted,
    fontSize: 12,
  },
  secondaryBtn: {
    marginTop: 10,
    marginBottom: 10,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.rule,
    paddingVertical: 10,
    alignItems: 'center',
    backgroundColor: colors.white,
  },
  secondaryText: {
    color: colors.ink,
    fontFamily: fonts.sansMedium,
  },
  saveBtn: {
    marginTop: 16,
    backgroundColor: colors.ink,
    borderRadius: radius.md,
    paddingVertical: 10,
    alignItems: 'center',
  },
  saveText: {
    color: colors.white,
    fontFamily: fonts.sansMedium,
  },
});
