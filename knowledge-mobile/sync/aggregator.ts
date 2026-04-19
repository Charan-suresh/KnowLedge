import * as Crypto from 'expo-crypto';

import { getSyncConceptRows } from '../db/queries';

export type SyncPayload = {
  course_id: string;
  week: string;
  concepts: Array<Record<string, unknown>>;
  payload_hash: string;
};

export async function buildSyncPayload(courseId: string, week: string): Promise<SyncPayload> {
  const rows = await getSyncConceptRows();
  const concepts = rows.map((r) => ({
    concept: r.concept,
    status: r.status,
    clearing_method: r.clearing_method,
    lens_signature: r.lens_signature,
    integrity_suspect: Boolean(r.integrity_suspect),
  }));

  const payload = { course_id: courseId, week, concepts };
  const canonical = JSON.stringify(payload);
  const payload_hash = await Crypto.digestStringAsync(Crypto.CryptoDigestAlgorithm.SHA256, canonical);
  return { ...payload, payload_hash };
}
