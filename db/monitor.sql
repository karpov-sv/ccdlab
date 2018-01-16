--- Status of the system
DROP TABLE monitor_status CASCADE;
create table monitor_status (
       id SERIAL PRIMARY KEY,
       time TIMESTAMP,
       status JSONB
);
CREATE INDEX ON monitor_status (time);
