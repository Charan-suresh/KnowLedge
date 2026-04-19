import * as Crypto from 'expo-crypto';
import * as Device from 'expo-device';
import * as SecureStore from 'expo-secure-store';

const DEVICE_KEY = 'knowledge_mobile_device_key';

export interface MobileSessionFingerprint {
  sessionId: string;
  concept: string;
  totalDurationSeconds: number;
  turnCount: number;
  responseTimes: number[];
  responseLengths: number[];
  timeoutCount: number;
  voiceModeUsed: boolean;
  audioRecordingDurations: number[];
  averageAudioDuration: number;
  cameraUsed: boolean;
  spoofAttemptsDetected: number;
  deviceModel: string;
  sessionHash: string;
}

export async function generateDeviceKeyIfMissing(): Promise<string> {
  const existing = await SecureStore.getItemAsync(DEVICE_KEY);
  if (existing) return existing;
  const seed = `${Date.now()}-${Math.random()}`;
  const hash = await Crypto.digestStringAsync(Crypto.CryptoDigestAlgorithm.SHA256, seed);
  await SecureStore.setItemAsync(DEVICE_KEY, hash);
  return hash;
}

export async function signFingerprint(fingerprint: Omit<MobileSessionFingerprint, 'sessionHash'>): Promise<string> {
  const key = await generateDeviceKeyIfMissing();
  const canonical = JSON.stringify(fingerprint);
  return Crypto.digestStringAsync(Crypto.CryptoDigestAlgorithm.SHA256, `${key}:${canonical}`);
}

export async function createFingerprint(input: Omit<MobileSessionFingerprint, 'deviceModel' | 'sessionHash'>): Promise<MobileSessionFingerprint> {
  const base = {
    ...input,
    deviceModel: Device.modelName || 'unknown-device',
  };
  const sessionHash = await signFingerprint(base);
  return { ...base, sessionHash };
}

export function summarizeVoiceUse(audioRecordingDurations: number[]): { averageAudioDuration: number } {
  if (audioRecordingDurations.length === 0) {
    return { averageAudioDuration: 0 };
  }
  const total = audioRecordingDurations.reduce((sum, value) => sum + value, 0);
  return { averageAudioDuration: total / audioRecordingDurations.length };
}

export async function makeMinimalFingerprint(sessionId: string, concept: string): Promise<MobileSessionFingerprint> {
  return createFingerprint({
    sessionId,
    concept,
    totalDurationSeconds: 0,
    turnCount: 0,
    responseTimes: [],
    responseLengths: [],
    timeoutCount: 0,
    voiceModeUsed: true,
    audioRecordingDurations: [],
    averageAudioDuration: 0,
    cameraUsed: false,
    spoofAttemptsDetected: 0,
  });
}
