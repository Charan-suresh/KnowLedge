import * as SQLite from 'expo-sqlite';

export type DebtRow = {
  id: number;
  concept: string;
  subject: string;
  source_text: string | null;
  timestamp: string;
  confidence: number | null;
  status: string;
};

let cachedDb: SQLite.SQLiteDatabase | null = null;

export async function getDb(): Promise<SQLite.SQLiteDatabase> {
  if (!cachedDb) cachedDb = await SQLite.openDatabaseAsync('knowledge_mobile.db');
  return cachedDb;
}

export async function listDebtRows(): Promise<DebtRow[]> {
  const db = await getDb();
  const rows = await db.getAllAsync<DebtRow>('SELECT * FROM debt_log ORDER BY timestamp DESC');
  return rows;
}

export async function insertDebtRow(concept: string, sourceText: string, confidence: number): Promise<void> {
  const db = await getDb();
  await db.runAsync(
    'INSERT INTO debt_log (concept, source_text, confidence, status) VALUES (?, ?, ?, ?)',
    [concept, sourceText, confidence, 'on_loan']
  );
}

export async function updateDebtStatus(concept: string, status: string): Promise<void> {
  const db = await getDb();
  await db.runAsync('UPDATE debt_log SET status = ? WHERE concept = ?', [status, concept]);
}

export async function getSyncConceptRows(): Promise<Array<Record<string, unknown>>> {
  const db = await getDb();
  return db.getAllAsync(
    `SELECT concept, status, COALESCE(clearing_method,'') AS clearing_method,
            COALESCE(lens_signature,'') AS lens_signature,
            COALESCE(integrity_suspect,0) AS integrity_suspect
     FROM debt_log
     WHERE id IN (SELECT MAX(id) FROM debt_log GROUP BY concept)
     ORDER BY concept ASC`
  );
}
