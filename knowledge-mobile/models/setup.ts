import * as FileSystem from 'expo-file-system';

import { GemmaInferenceModule } from '../modules/gemma-inference';

export type ModelSetupStatus = {
  e2bStatus: 'available' | 'downloading' | 'unavailable';
  e4bStatus: 'available' | 'downloading' | 'unavailable';
  requiresDownload: boolean;
};

const MODELS_DIR = `${FileSystem.documentDirectory}models/`;
const E2B_URL = 'https://huggingface.co/google/gemma-4-E2B-it/resolve/main/gemma-4-e2b-q4.task';

export async function getModelSetupStatus(): Promise<ModelSetupStatus> {
  const e2bStatus = await GemmaInferenceModule.checkFeatureStatus('e2b');
  const e4bStatus = await GemmaInferenceModule.checkFeatureStatus('e4b');
  const requiresDownload = e2bStatus !== 'available';
  return { e2bStatus, e4bStatus, requiresDownload };
}

export async function ensureModelDirectory(): Promise<void> {
  const info = await FileSystem.getInfoAsync(MODELS_DIR);
  if (!info.exists) await FileSystem.makeDirectoryAsync(MODELS_DIR, { intermediates: true });
}

export async function downloadE2BModel(onProgress?: (fraction: number) => void): Promise<string> {
  await ensureModelDirectory();
  const target = `${MODELS_DIR}gemma-4-e2b-q4.task`;
  const download = FileSystem.createDownloadResumable(
    E2B_URL,
    target,
    {},
    (event) => {
      if (!onProgress) return;
      if (event.totalBytesExpectedToWrite > 0) {
        onProgress(event.totalBytesWritten / event.totalBytesExpectedToWrite);
      }
    }
  );
  const result = await download.downloadAsync();
  if (!result?.uri) throw new Error('Model download failed');
  return result.uri;
}
