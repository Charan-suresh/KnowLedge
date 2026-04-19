import NetInfo from '@react-native-community/netinfo';

import { getRuntimeConfig } from '../config';
import { getDb } from '../db/queries';
import { buildSyncPayload, SyncPayload } from './aggregator';
import { writeSyncAudit } from './auditLog';
import { getCurrentWeekLabel } from '../utils/date';

export type SyncResult = {
  skipped?: boolean;
  reason?: string;
  status?: string;
  error?: string;
};

async function queuePendingPayload(payload: SyncPayload, error: string): Promise<void> {
  const db = await getDb();
  await db.runAsync(
    'INSERT INTO sync_pending (course_id, week, payload_json, payload_hash, last_error) VALUES (?, ?, ?, ?, ?)',
    [payload.course_id, payload.week, JSON.stringify(payload), payload.payload_hash, error.slice(0, 500)]
  );
}

export async function sendPayload(payload: SyncPayload): Promise<SyncResult> {
  const { serverUrl } = getRuntimeConfig();
  try {
    const res = await fetch(`${serverUrl}/api/sync/share-weekly`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const body = await res.json();
    const status = body.status || 'ok';
    await writeSyncAudit(status, payload.course_id, payload.week, payload.concepts.length, payload.payload_hash);
    return { status };
  } catch (e) {
    const err = String(e);
    await queuePendingPayload(payload, err);
    await writeSyncAudit('queued', payload.course_id, payload.week, payload.concepts.length, payload.payload_hash);
    return { status: 'failed', error: err };
  }
}

export async function syncIfWifi(courseId: string, week: string): Promise<SyncResult> {
  const { syncOnWifiOnly } = getRuntimeConfig();
  const state = await NetInfo.fetch();
  if (syncOnWifiOnly && state.type !== 'wifi') {
    return { skipped: true, reason: 'not_on_wifi' };
  }
  const payload = await buildSyncPayload(courseId, week);
  return sendPayload(payload);
}

export async function retryPendingSyncs(): Promise<SyncResult> {
  const db = await getDb();
  const rows = await db.getAllAsync<Array<Record<string, unknown>>>(
    'SELECT id, payload_json FROM sync_pending ORDER BY id ASC LIMIT 20'
  );

  let sent = 0;
  for (const row of rows as unknown as Array<{ id: number; payload_json: string }>) {
    try {
      const payload = JSON.parse(row.payload_json) as SyncPayload;
      const result = await sendPayload(payload);
      if (result.status !== 'failed') {
        await db.runAsync('DELETE FROM sync_pending WHERE id = ?', [row.id]);
        sent += 1;
      }
    } catch {
      // Keep payload in pending queue.
    }
  }
  return { status: 'ok', reason: `retried_${rows.length}_sent_${sent}` };
}

export async function retryPendingSyncsIfWifi(courseId: string): Promise<void> {
  const week = getCurrentWeekLabel();
  await syncIfWifi(courseId, week);
  await retryPendingSyncs();
}
