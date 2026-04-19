import * as Device from 'expo-device';

import { GemmaInferenceModule } from './modules/gemma-inference';

export type InferenceMode =
  | 'on_device_full'
  | 'on_device_scout'
  | 'server_only';

export const INFERENCE_MODE: InferenceMode = 'on_device_scout';
export const UNIVERSITY_SERVER = 'https://knowledge.youruniversity.edu';
export const SAGE_TIMEOUT_SECONDS = 75;
export const VOICE_MODE = true;
export const LOW_RAM_LOCK = true;

export type RuntimeConfig = {
  inferenceMode: InferenceMode;
  serverUrl: string;
  syncOnWifiOnly: boolean;
  voiceMode: boolean;
};

let runtimeConfig: RuntimeConfig = {
  inferenceMode: INFERENCE_MODE,
  serverUrl: UNIVERSITY_SERVER,
  syncOnWifiOnly: true,
  voiceMode: VOICE_MODE,
};

export function getRuntimeConfig(): RuntimeConfig {
  return runtimeConfig;
}

export function setRuntimeConfig(patch: Partial<RuntimeConfig>): RuntimeConfig {
  runtimeConfig = { ...runtimeConfig, ...patch };
  return runtimeConfig;
}

export async function detectCapabilities(): Promise<InferenceMode> {
  const ramGb = Device.totalMemory ? Device.totalMemory / (1024 ** 3) : 0;
  const e2bStatus = await GemmaInferenceModule.checkFeatureStatus('e2b');
  const e4bStatus = await GemmaInferenceModule.checkFeatureStatus('e4b');

  if (ramGb >= 12 && e2bStatus === 'available' && e4bStatus === 'available') {
    setRuntimeConfig({ inferenceMode: 'on_device_full' });
    return 'on_device_full';
  }
  if (ramGb >= 8 && e2bStatus === 'available') {
    setRuntimeConfig({ inferenceMode: 'on_device_scout' });
    return 'on_device_scout';
  }
  setRuntimeConfig({ inferenceMode: 'server_only' });
  return 'server_only';
}
