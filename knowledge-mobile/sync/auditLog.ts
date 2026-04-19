import { getDb } from '../db/queries';

export async function writeSyncAudit(status: string, courseId: string, week: string, conceptsShared: number, payloadHash: string): Promise<void> {
  const db = await getDb();
  await db.runAsync(
    'INSERT INTO sync_audit (synced_at, course_id, week, concepts_shared, payload_hash, status, server_acknowledged) VALUES (CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?)',
    [courseId, week, conceptsShared, payloadHash, status, status === 'sent' ? 1 : 0]
  );
}

export async function getSyncAuditRows(): Promise<Array<Record<string, unknown>>> {
  const db = await getDb();
  return db.getAllAsync('SELECT * FROM sync_audit ORDER BY id DESC LIMIT 20');
}
