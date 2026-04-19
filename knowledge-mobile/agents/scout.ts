import { getRuntimeConfig } from '../config';
import { GemmaInferenceModule } from '../modules/gemma-inference';

type ConceptTag = { concept: string; confidence: number };

function buildScoutPrompt(text: string): string {
  return `Extract key learning concepts from this student-provided content.\nReturn strict JSON array: [{\"concept\":\"...\",\"confidence\":0.0}]\nText:\n${text}`;
}

function parseConceptTags(raw: string): ConceptTag[] {
  try {
    const data = JSON.parse(raw);
    if (!Array.isArray(data)) return [];
    return data
      .map((x) => ({ concept: String(x.concept || ''), confidence: Number(x.confidence || 0.5) }))
      .filter((x) => x.concept.length > 0);
  } catch {
    return [];
  }
}

async function serverTag(text: string): Promise<ConceptTag[]> {
  const { serverUrl } = getRuntimeConfig();
  const res = await fetch(`${serverUrl}/api/scout`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) return [];
  const body = await res.json();
  if (Array.isArray(body.concepts)) return body.concepts;
  return [];
}

export async function tagContent(text: string): Promise<ConceptTag[]> {
  const { inferenceMode } = getRuntimeConfig();
  if (inferenceMode === 'server_only') return serverTag(text);

  const available = await GemmaInferenceModule.isAvailable('e2b');
  if (!available) return [];

  const response = await GemmaInferenceModule.generate('e2b', buildScoutPrompt(text), {
    maxTokens: 512,
    temperature: 0.1,
  });
  return parseConceptTags(response);
}
