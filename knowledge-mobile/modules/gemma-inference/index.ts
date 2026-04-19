import { EventEmitter, NativeModulesProxy } from 'expo-modules-core';

type ModelName = 'e2b' | 'e4b';

type FeatureStatus = 'available' | 'downloading' | 'unavailable';

type GenerateOptions = {
  maxTokens?: number;
  temperature?: number;
  onToken?: (token: string) => void;
};

const moduleName = 'GemmaInferenceModule';
const native = (NativeModulesProxy as Record<string, any>)[moduleName];
const emitter = new EventEmitter(native);

export const GemmaInferenceModule = {
  async isAvailable(model: ModelName): Promise<boolean> {
    if (!native?.isAvailable) return false;
    return native.isAvailable(model);
  },

  async checkFeatureStatus(model: ModelName): Promise<FeatureStatus> {
    if (!native?.checkFeatureStatus) return 'unavailable';
    return native.checkFeatureStatus(model);
  },

  async generate(model: ModelName, prompt: string, options?: GenerateOptions): Promise<string> {
    let sub: { remove: () => void } | undefined;
    if (options?.onToken) {
      sub = emitter.addListener('onToken', (event: { token: string }) => options.onToken?.(event.token));
    }
    try {
      if (!native?.generate) throw new Error('GemmaInference native module unavailable');
      return await native.generate(model, prompt, options || {});
    } finally {
      sub?.remove();
    }
  },

  async generateWithImage(model: 'e4b', prompt: string, imageBase64: string): Promise<string> {
    if (!native?.generateWithImage) throw new Error('GemmaInference native module unavailable');
    return native.generateWithImage(model, prompt, imageBase64);
  },

  async generateWithAudio(model: 'e4b', prompt: string, audioBase64: string): Promise<string> {
    if (!native?.generateWithAudio) throw new Error('GemmaInference native module unavailable');
    return native.generateWithAudio(model, prompt, audioBase64);
  },
};
