-- Schema D1 para reportes de usuarios
CREATE TABLE IF NOT EXISTS reportes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  circuito_id TEXT NOT NULL,
  lugar TEXT NOT NULL,
  tipo TEXT NOT NULL CHECK (tipo IN ('on', 'off')),
  timestamp INTEGER NOT NULL,
  hash_usuario TEXT NOT NULL,
  lat REAL,
  lng REAL
);
CREATE INDEX IF NOT EXISTS idx_reportes_circuito ON reportes(circuito_id);
CREATE INDEX IF NOT EXISTS idx_reportes_timestamp ON reportes(timestamp);
