-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS pg_partman CASCADE;
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Create partman schema
CREATE SCHEMA IF NOT EXISTS partman;

-- Grant permissions
GRANT ALL ON SCHEMA partman TO postgres;
GRANT ALL ON ALL TABLES IN SCHEMA partman TO postgres;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA partman TO postgres;
GRANT EXECUTE ON ALL PROCEDURES IN SCHEMA partman TO postgres;

-- Create base tables (if not exists)
CREATE TABLE IF NOT EXISTS departments (
    id INTEGER PRIMARY KEY,
    department VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY,
    job VARCHAR(255) NOT NULL
);

-- Create partitioned hired_employees table
CREATE TABLE IF NOT EXISTS hired_employees (
    id BIGINT PRIMARY KEY,
    name TEXT NOT NULL,
    hire_dt TIMESTAMP WITH TIME ZONE NOT NULL,
    hire_year INTEGER GENERATED ALWAYS AS (EXTRACT(YEAR FROM hire_dt AT TIME ZONE 'UTC')::INTEGER) STORED,
    department_id INTEGER REFERENCES departments(id),
    job_id INTEGER REFERENCES jobs(id)
) PARTITION BY RANGE (hire_dt);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_hired_employees_dept_job_date 
    ON hired_employees (department_id, job_id, hire_dt);
CREATE INDEX IF NOT EXISTS idx_hired_employees_year_dept 
    ON hired_employees (hire_year, department_id);

-- Setup partitioning with pg_partman
SELECT partman.create_parent(
    p_parent_table => 'public.hired_employees',
    p_control => 'hire_dt',
    p_type => 'range',
    p_interval => '1 year',
    p_premake => 3
);

-- Update partman config
UPDATE partman.part_config 
SET infinite_time_partitions = true,
    retention_keep_table = false,
    retention_keep_index = true
WHERE parent_table = 'public.hired_employees';

-- Create partitions for years 2020-2025
DO $$
DECLARE
    v_year INTEGER;
    v_start_date DATE;
    v_end_date DATE;
BEGIN
    FOR v_year IN 2020..2025 LOOP
        BEGIN
            v_start_date := make_date(v_year, 1, 1);
            v_end_date := make_date(v_year + 1, 1, 1);
            EXECUTE format('CREATE TABLE IF NOT EXISTS hired_employees_%s PARTITION OF hired_employees FOR VALUES FROM (%L) TO (%L)',
                v_year, v_start_date, v_end_date);
        EXCEPTION WHEN duplicate_table THEN
            -- Partition already exists, continue
            NULL;
        END;
    END LOOP;
END $$;

-- Create materialized view for quarterly hires
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_hires_q AS
SELECT 
    department_id,
    job_id,
    date_trunc('quarter', hire_dt)::date AS quarter,
    COUNT(*) AS hires
FROM hired_employees
GROUP BY department_id, job_id, quarter;

-- Create unique index for concurrent refresh
CREATE UNIQUE INDEX IF NOT EXISTS mv_hires_q_pk 
    ON mv_hires_q (department_id, job_id, quarter);

-- Create materialized view for departments above mean
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_dept_mean AS
WITH yearly_hires AS (
    SELECT 
        department_id,
        EXTRACT(YEAR FROM hire_dt) as year,
        COUNT(*) AS hired
    FROM hired_employees
    GROUP BY department_id, year
),
mean_by_year AS (
    SELECT 
        year,
        AVG(hired) as mean_hires
    FROM yearly_hires
    GROUP BY year
)
SELECT 
    d.id,
    d.department,
    yh.hired,
    yh.year,
    m.mean_hires
FROM yearly_hires yh
JOIN departments d ON yh.department_id = d.id
JOIN mean_by_year m ON yh.year = m.year
WHERE yh.hired > m.mean_hires;

-- Create unique index for concurrent refresh
CREATE UNIQUE INDEX IF NOT EXISTS mv_dept_mean_pk 
    ON mv_dept_mean (id, year);

-- Schedule automatic refresh of materialized views using pg_cron
SELECT cron.schedule('refresh-mv-hires-q', '*/5 * * * *', 
    $$REFRESH MATERIALIZED VIEW CONCURRENTLY mv_hires_q;$$);

SELECT cron.schedule('refresh-mv-dept-mean', '*/5 * * * *', 
    $$REFRESH MATERIALIZED VIEW CONCURRENTLY mv_dept_mean;$$);

-- Schedule partition maintenance
SELECT cron.schedule('partman-maintenance', '0 2 * * *', 
    $$CALL partman.run_maintenance();$$); 