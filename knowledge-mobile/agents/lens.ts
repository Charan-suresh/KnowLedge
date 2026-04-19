import { getRuntimeConfig } from '../config';
import { GemmaInferenceModule } from '../modules/gemma-inference';

export type LensVerdict = {
  verdict: 'genuine' | 'spoofed' | 'unclear';
  explanation: string;
};

function parseVerdict(raw: string): LensVerdict {
  const lower = raw.toLowerCase();
  if (lower.includes('spoofed')) return { verdict: 'spoofed', explanation: raw };
  if (lower.includes('genuine')) return { verdict: 'genuine', explanation: raw };
  return { verdict: 'unclear', explanation: raw };
}

export async function verifyHandwriting(imageBase64: string, concept: string): Promise<LensVerdict> {
  const { inferenceMode, serverUrl } = getRuntimeConfig();

  if (inferenceMode === 'on_device_full') {
    const prompt = `Verify handwritten reasoning for concept: ${concept}. Reply with genuine, spoofed, or unclear and explanation.`;
    const raw = await GemmaInferenceModule.generateWithImage('e4b', prompt, imageBase64);
    return parseVerdict(raw);
  }

  const form = new FormData();
  form.append('concept', concept);
  form.append('file', {
    uri: `data:image/jpeg;base64,${imageBase64}`,
    name: 'capture.jpg',
    type: 'image/jpeg',
  } as unknown as Blob);

  const res = await fetch(`${serverUrl}/api/lens/verify`, { method: 'POST', body: form });
  const data = await res.json();
  return {
    verdict: data.explanation?.toLowerCase().includes('error') ? 'unclear' : 'genuine',
    explanation: data.explanation || 'No explanation',
  };
}
