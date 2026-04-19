import React, { useEffect, useState } from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { Audio } from 'expo-av';
import * as FileSystem from 'expo-file-system';

import { LensCamera } from '../components/LensCamera';
import { SAGE_TIMEOUT_SECONDS } from '../config';
import { startSageSession, sendResponse } from '../agents/sage';
import { colors, fonts, radius } from '../theme';

export default function SoloScreen() {
  const [seconds, setSeconds] = useState(SAGE_TIMEOUT_SECONDS);
  const [cameraOpen, setCameraOpen] = useState(false);
  const [recording, setRecording] = useState<Audio.Recording | null>(null);
  const [sessionId, setSessionId] = useState('');
  const [concept] = useState('Active Solo Challenge');
  const [reply, setReply] = useState('');

  useEffect(() => {
    (async () => {
      const session = await startSageSession(concept);
      setSessionId(session.sessionId);
    })();
  }, [concept]);

  useEffect(() => {
    const t = setInterval(() => setSeconds((s) => Math.max(0, s - 1)), 1000);
    return () => clearInterval(t);
  }, []);

  const startRecording = async () => {
    const perm = await Audio.requestPermissionsAsync();
    if (!perm.granted) return;
    await Audio.setAudioModeAsync({ allowsRecordingIOS: true, playsInSilentModeIOS: true });
    const rec = new Audio.Recording();
    await rec.prepareToRecordAsync(Audio.RecordingOptionsPresets.HIGH_QUALITY);
    await rec.startAsync();
    setRecording(rec);
  };

  const stopRecordingAndSend = async () => {
    if (!recording || !sessionId) return;
    await recording.stopAndUnloadAsync();
    const uri = recording.getURI();
    setRecording(null);
    if (!uri) return;
    const audioBase64 = await FileSystem.readAsStringAsync(uri, { encoding: FileSystem.EncodingType.Base64 });
    const result = await sendResponse({ sessionId, concept, turns: [] }, 'spoken response', undefined, audioBase64);
    setReply(result.text);
  };

  return (
    <View style={styles.screen}>
      <Text style={styles.timer}>{seconds}s</Text>
      <Text style={styles.concept}>Concept: {concept}</Text>

      <View style={styles.actions}>
        <TouchableOpacity
          style={[styles.roundBtn, recording && styles.roundBtnActive]}
          onPressIn={startRecording}
          onPressOut={stopRecordingAndSend}
        >
          <Text style={styles.icon}>🎤</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.roundBtn} onPress={() => setCameraOpen((x) => !x)}><Text style={styles.icon}>📷</Text></TouchableOpacity>
      </View>

      {cameraOpen ? <LensCamera concept="Solo Concept" /> : null}

      {!!reply && <Text style={styles.reply}>{reply}</Text>}

      <Text style={styles.note}>
        Offline note: local timer is used offline; server verification occurs when connection returns.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.cream,
    padding: 16,
  },
  timer: {
    fontFamily: fonts.serif,
    fontSize: 44,
    color: colors.ink,
    textAlign: 'center',
    marginTop: 20,
  },
  concept: {
    marginTop: 14,
    textAlign: 'center',
    fontFamily: fonts.mono,
    color: colors.inkMuted,
  },
  actions: {
    marginTop: 18,
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 20,
  },
  roundBtn: {
    width: 86,
    height: 86,
    borderRadius: 50,
    backgroundColor: colors.ink,
    alignItems: 'center',
    justifyContent: 'center',
  },
  roundBtnActive: {
    backgroundColor: colors.teal,
  },
  icon: {
    fontSize: 34,
  },
  reply: {
    marginTop: 12,
    fontFamily: fonts.sans,
    color: colors.ink,
    textAlign: 'center',
  },
  note: {
    marginTop: 14,
    fontFamily: fonts.sans,
    color: colors.inkMuted,
    textAlign: 'center',
  },
});
