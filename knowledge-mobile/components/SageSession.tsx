import React, { useRef, useState } from 'react';
import { Modal, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { Audio } from 'expo-av';
import * as FileSystem from 'expo-file-system';

import { VOICE_MODE } from '../config';
import { SAGE_TIMEOUT_SECONDS } from '../config';
import { sendResponse, SageSession as SageSessionType } from '../agents/sage';
import { colors, fonts, radius } from '../theme';
import { CountdownTimer } from './CountdownTimer';

type Props = {
  visible: boolean;
  session: SageSessionType | null;
  onClose: () => void;
};

export function SageSession({ visible, session, onClose }: Props) {
  const [text, setText] = useState('');
  const [reply, setReply] = useState('');
  const [recording, setRecording] = useState<Audio.Recording | null>(null);
  const [busy, setBusy] = useState(false);
  const replyRef = useRef('');

  const submit = async () => {
    if (!session || !text.trim()) return;
    setBusy(true);
    replyRef.current = '';
    const out = await sendResponse(session, text.trim(), (token) => {
      replyRef.current += token;
      setReply(replyRef.current);
    });
    if (!replyRef.current) setReply(out.text);
    setText('');
    setBusy(false);
  };

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
    if (!recording || !session) return;
    setBusy(true);
    await recording.stopAndUnloadAsync();
    const uri = recording.getURI();
    setRecording(null);
    if (!uri) {
      setBusy(false);
      return;
    }
    const audioBase64 = await FileSystem.readAsStringAsync(uri, { encoding: FileSystem.EncodingType.Base64 });
    replyRef.current = '';
    const out = await sendResponse(session, text.trim() || 'spoken response', (token) => {
      replyRef.current += token;
      setReply(replyRef.current);
    }, audioBase64);
    if (!replyRef.current) setReply(out.text);
    setBusy(false);
  };

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={onClose}>
      <View style={styles.container}>
        <View style={styles.header}>
          <Text style={styles.title}>{session?.concept || 'Sage Session'}</Text>
          <CountdownTimer seconds={SAGE_TIMEOUT_SECONDS} />
        </View>

        <View style={styles.chatArea}>
          <Text style={styles.sageBubble}>{reply || 'Sage is ready. Explain in your own words.'}</Text>
        </View>

        {VOICE_MODE ? (
          <View style={styles.voiceRow}>
            <TouchableOpacity
              style={[styles.voiceBtn, recording && styles.voiceBtnActive]}
              onPressIn={startRecording}
              onPressOut={stopRecordingAndSend}
              disabled={busy}
            >
              <Text style={styles.voiceText}>{recording ? 'Release to send' : 'Hold to speak'}</Text>
            </TouchableOpacity>
          </View>
        ) : (
          <View style={styles.inputRow}>
            <TextInput
              value={text}
              onChangeText={setText}
              style={styles.input}
              placeholder="Your response"
            />
            <TouchableOpacity style={styles.send} onPress={submit}>
              <Text style={styles.sendText}>Send</Text>
            </TouchableOpacity>
          </View>
        )}

        <TouchableOpacity style={styles.close} onPress={onClose}>
          <Text style={styles.closeText}>Close</Text>
        </TouchableOpacity>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.cream,
    paddingTop: 56,
    paddingHorizontal: 16,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  title: {
    fontFamily: fonts.serif,
    fontSize: 22,
    color: colors.ink,
  },
  chatArea: {
    flex: 1,
    marginTop: 16,
  },
  sageBubble: {
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.rule,
    borderRadius: radius.lg,
    padding: 12,
    fontFamily: fonts.sans,
    color: colors.ink,
  },
  inputRow: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 12,
  },
  voiceRow: {
    marginBottom: 12,
  },
  voiceBtn: {
    backgroundColor: colors.ink,
    borderRadius: radius.lg,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 16,
  },
  voiceBtnActive: {
    backgroundColor: colors.teal,
  },
  voiceText: {
    color: colors.white,
    fontFamily: fonts.sansMedium,
  },
  input: {
    flex: 1,
    borderWidth: 1,
    borderColor: colors.rule,
    borderRadius: radius.md,
    paddingHorizontal: 12,
    paddingVertical: 10,
    backgroundColor: colors.white,
    fontFamily: fonts.sans,
  },
  send: {
    backgroundColor: colors.teal,
    borderRadius: radius.md,
    paddingHorizontal: 14,
    justifyContent: 'center',
  },
  sendText: {
    color: colors.white,
    fontFamily: fonts.sansMedium,
  },
  close: {
    marginBottom: 30,
    alignSelf: 'center',
  },
  closeText: {
    fontFamily: fonts.mono,
    color: colors.inkMuted,
  },
});
