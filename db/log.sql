--- Status of the system
DROP TABLE log CASCADE;
CREATE TABLE log (
       id SERIAL PRIMARY KEY,
       time TIMESTAMP,
       source TEXT,
       type TEXT DEFAULT 'info',
       message TEXT
);
CREATE INDEX ON log (time);
