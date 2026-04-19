import { getRuntimeConfig } from '../config';
import { GemmaInferenceModule } from '../modules/gemma-inference';

export type SageSession = {
  sessionId: string;
  concept: string;
  turns: Array<{ role: 'student' | 'sage'; content: string }>;
};

export type SageReply = {
  text: string;
  cleared: boolean;
};

export async function startSageSession(concept: string): Promise<SageSession> {
  return {
    sessionId: `sage-${Date.now()}`,
    concept,
    turns: [],
  };
}

export async function sendResponse(
  session: SageSession,
  studentResponse: string,
  onToken?: (token: string) => void,
  audioBase64?: string
): Promise<SageReply> {
  const { inferenceMode, serverUrl } = getRuntimeConfig();
  if (inferenceMode === 'on_device_full') {
    if (audioBase64) {
      const prompt = `Concept: ${session.concept}. Evaluate the student's spoken answer and respond Socratically.`;
      const text = await GemmaInferenceModule.generateWithAudio('e4b', prompt, audioBase64);
      return { text, cleared: text.toLowerCase().includes('cleared') };
    }
    const prompt = `Concept: ${session.concept}\nStudent response: ${studentResponse}\nReply Socratically.`;
    const text = await GemmaInferenceModule.generate('e4b', prompt, { onToken, maxTokens: 512, temperature: 0.2 });
    return { text, cleared: text.toLowerCase().includes('cleared') };
  }

  const res = await fetch(`${serverUrl}/api/sage/turn`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      concept: session.concept,
      chat_history: [{ role: 'user', content: studentResponse }],
      session_id: session.sessionId,
    }),
  });
  const data = await res.json();
  return { text: data.response || '', cleared: Boolean(data.cleared) };
}
