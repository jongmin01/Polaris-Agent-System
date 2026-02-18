-- Polaris Memory Schema
-- DB file: data/polaris_memory.db

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,          -- 'user' | 'assistant'
    content TEXT NOT NULL,
    embedding BLOB               -- float list serialised as bytes (nullable)
);

CREATE TABLE IF NOT EXISTS traces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    session_id TEXT NOT NULL,
    thought TEXT,
    tool_name TEXT,
    tool_args TEXT,              -- JSON string
    result_summary TEXT,
    approval_level TEXT,
    approved BOOLEAN
);

CREATE TABLE IF NOT EXISTS knowledge (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    category TEXT NOT NULL,      -- research | daily | insight | reference
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding BLOB,              -- float list serialised as bytes (nullable)
    source TEXT,                 -- manual | arxiv | conversation | obsidian | email
    tags TEXT                    -- JSON array string
);

CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    original_action TEXT NOT NULL,
    correction TEXT NOT NULL,
    applied BOOLEAN DEFAULT 0,
    embedding BLOB,
    session_id TEXT,
    category TEXT
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversations(session_id);
CREATE INDEX IF NOT EXISTS idx_traces_session ON traces(session_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_category ON knowledge(category);
CREATE INDEX IF NOT EXISTS idx_feedback_applied ON feedback(applied);
