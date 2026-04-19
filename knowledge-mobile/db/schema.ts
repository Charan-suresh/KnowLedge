export const SCHEMA = `
CREATE TABLE IF NOT EXISTS debt_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  concept TEXT NOT NULL,
  subject TEXT DEFAULT 'General',
  source_text TEXT,
  timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
  confidence REAL,
  status TEXT DEFAULT 'on_loan',
  language TEXT DEFAULT 'en',
  integrity_suspect INTEGER DEFAULT 0,
  clearing_method TEXT,
  lens_signature TEXT
);

CREATE TABLE IF NOT EXISTS clearing_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  concept TEXT NOT NULL,
  session_ts TEXT DEFAULT CURRENT_TIMESTAMP,
  result TEXT,
  notes TEXT,
  session_hash TEXT,
  spoof_attempts INTEGER DEFAULT 0,
  paste_detected INTEGER DEFAULT 0,
  integrity_suspect INTEGER DEFAULT 0,
  voice_mode INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS real_performance (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT,
  concept TEXT NOT NULL,
  mode TEXT NOT NULL,
  score INTEGER,
  reasoning TEXT,
  specific_gaps TEXT,
  question TEXT,
  response TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS session_fingerprints (
  session_id TEXT PRIMARY KEY,
  concept TEXT,
  total_duration_seconds INTEGER,
  turn_count INTEGER,
  response_times TEXT,
  response_lengths TEXT,
  timeout_count INTEGER,
  median_response_time REAL,
  response_time_variance REAL,
  voice_mode_used INTEGER DEFAULT 1,
  audio_recording_durations TEXT,
  average_audio_duration REAL,
  camera_used INTEGER DEFAULT 0,
  spoof_attempts_detected INTEGER DEFAULT 0,
  device_model TEXT,
  session_hash TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sync_audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  synced_at TEXT,
  course_id TEXT,
  week TEXT,
  concepts_shared INTEGER,
  payload_hash TEXT,
  status TEXT,
  server_acknowledged INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sync_pending (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  course_id TEXT,
  week TEXT,
  payload_json TEXT,
  payload_hash TEXT,
  last_error TEXT
);
`;
