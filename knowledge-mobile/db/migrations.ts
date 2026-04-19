import * as SQLite from 'expo-sqlite';

import { SCHEMA } from './schema';

export async function runDatabaseMigrations(db?: SQLite.SQLiteDatabase): Promise<void> {
  const database = db ?? await SQLite.openDatabaseAsync('knowledge_mobile.db');
  const statements = SCHEMA.split(';').map((s) => s.trim()).filter(Boolean);
  for (const statement of statements) {
    await database.execAsync(statement + ';');
  }
}
