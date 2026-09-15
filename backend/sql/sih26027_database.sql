-- =====================================================================
-- SIH26027 â€” AI-Powered Automatic Railway Block Planning,
-- Integrated Maintenance Coordination & Emergency Response System
-- COMPLETE POSTGRESQL + POSTGIS DATABASE SCRIPT
-- Generated from: SIH26027_Context_Prompt.md, SIH26027_Project_Description.md,
--                 overall_prompt_claude.txt, login_setup.txt,
--                 postgres_sql_command_description.txt, tech_stack_27.txt,
--                 workflow_diagram.txt
--
-- Run this in pgAdmin's Query Tool against a NEW, empty PostgreSQL database.
--
-- Design notes (read before executing):
-- 1. All geometry columns use SRID 4326 (WGS84 lat/lon) â€” the spec did not
--    pin a specific SRID, and 4326 pairs naturally with the latitude/
--    longitude columns already present on the same tables.
-- 2. Two of the uploaded documents describe the maintenance-request status
--    flow slightly differently (one starts at DRAFT/SUBMITTED, an older one
--    at PENDING). Rather than dropping either, maintenance_request_status
--    is a superset enum containing every state named across both documents,
--    so neither document's workflow is unrepresentable.
-- 3. Section 11.3 of SIH26027_Project_Description.md explicitly lists 8
--    database gaps ("Known Gaps to Close Before Production Inference").
--    Those gap tables/columns are included below and are commented
--    "-- [gap-closing, Section 11.3]" so you can tell them apart from the
--    21 originally-listed tables.
-- 4. A few small supporting structures were added because the 21 named
--    tables imply them but don't name them explicitly:
--      - department_roles: makes "DEPARTMENT â‰  ROLE" a real constraint
--        (a composite FK from users) instead of just a comment.
--      - optimized_block_sources: traces which block_requests were merged
--        into a multi-department optimized_blocks row (the spec requires
--        multi-department integration to be "explicitly represented").
--    Nothing pre-existing was renamed or removed to make room for these.
-- 5. Business logic (Safety Engine rules, OR-Tools optimization, ML
--    inference) stays in the backend, per the spec. This script only
--    persists inputs/outputs and integrity constraints.
-- =====================================================================

BEGIN;

-- =====================================================================
-- 1. EXTENSIONS
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS postgis;

-- =====================================================================
-- 2. ENUM TYPES
-- =====================================================================

CREATE TYPE user_role AS ENUM (
    'MAINTENANCE_STAFF',
    'ENGINEER_REVIEWER',
    'OPERATOR',
    'CONTROLLER',
    'AUTHORIZED_OFFICIAL',
    'EMERGENCY_OPERATOR'
);

-- Reused for maintenance priority, ML risk_level, incident severity,
-- and affected-train impact level â€” all four are defined in the specs
-- as the same LOW/MEDIUM/HIGH/CRITICAL scale.
CREATE TYPE severity_level AS ENUM ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL');

-- notifications.priority uses NORMAL instead of MEDIUM per the spec â€”
-- kept as its own type rather than overloading severity_level.
CREATE TYPE notification_priority AS ENUM ('LOW', 'NORMAL', 'HIGH', 'CRITICAL');

-- Superset of the DRAFT/SUBMITTED flow (login_setup.txt, Project
-- Description) and the PENDING flow (postgres_sql_command_description.txt)
-- â€” see design note 2 above.
CREATE TYPE maintenance_request_status AS ENUM (
    'DRAFT',
    'SUBMITTED',
    'PENDING',
    'UNDER_REVIEW',
    'VERIFIED',
    'REJECTED',
    'REVISION_REQUIRED',
    'BLOCK_PLANNING',
    'AI_RECOMMENDATION',
    'OFFICIAL_REVIEW',
    'APPROVED',
    'MODIFIED',
    'IN_PROGRESS',
    'COMPLETED'
);

CREATE TYPE block_request_status AS ENUM (
    'REQUESTED', 'UNDER_REVIEW', 'PROPOSED', 'PENDING_APPROVAL',
    'APPROVED', 'REJECTED', 'ACTIVE', 'COMPLETED', 'CANCELLED'
);

CREATE TYPE optimized_block_status AS ENUM (
    'PROPOSED', 'PENDING_APPROVAL', 'APPROVED', 'MODIFIED',
    'REJECTED', 'ACTIVE', 'COMPLETED', 'CANCELLED'
);

CREATE TYPE integration_response AS ENUM ('ACCEPT', 'REJECT', 'MODIFY');

CREATE TYPE integration_final_status AS ENUM (
    'PENDING', 'ACCEPTED', 'REJECTED', 'MODIFIED', 'APPROVED'
);

CREATE TYPE incident_type AS ENUM (
    'ACCIDENT', 'DERAILMENT_RELATED', 'TRACK_FAILURE', 'SIGNAL_FAILURE',
    'OHE_FAILURE', 'OBSTRUCTION', 'PERSON_ON_TRACK', 'SUSPECTED_SUICIDE',
    'OTHER_EMERGENCY'
);

CREATE TYPE incident_response_status AS ENUM ('OPEN', 'IN_PROGRESS', 'CLEARED');

-- Matches the 5-stage timeline named in overall_prompt_claude.txt Section 25.
CREATE TYPE emergency_response_status AS ENUM (
    'ALERT_RECEIVED', 'TEAM_DISPATCHED', 'TEAM_ARRIVED',
    'INCIDENT_HANDED_OVER', 'AREA_CLEARED'
);

CREATE TYPE notification_type AS ENUM (
    'NEW_MAINTENANCE_REQUEST', 'REQUEST_VERIFICATION', 'REVISION_REQUIRED',
    'BLOCK_INTEGRATION_OPPORTUNITY', 'INTEGRATION_ACCEPTED',
    'INTEGRATION_REJECTED', 'AI_RECOMMENDATION_READY',
    'OFFICIAL_APPROVAL_REQUIRED', 'BLOCK_APPROVED', 'BLOCK_MODIFIED',
    'BLOCK_REJECTED', 'EMERGENCY_ALERT', 'EMERGENCY_REPLANNING'
);

-- =====================================================================
-- 3. SHARED TRIGGER FUNCTION (updated_at bookkeeping only â€” no business logic)
-- =====================================================================

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =====================================================================
-- 4. DEPARTMENTS
-- =====================================================================

CREATE TABLE departments (
    id          BIGSERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL UNIQUE,
    code        VARCHAR(20)  NOT NULL UNIQUE
                CHECK (code IN ('ENG','ELEC','SNT','OPS','CONTROL','RAILWAY','EMERGENCY')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =====================================================================
-- 5. DEPARTMENT_ROLES  (supporting table â€” see design note 4)
-- Makes every valid Department+Role combination an explicit row so a
-- composite FK from users can reject invalid combinations declaratively.
-- =====================================================================

CREATE TABLE department_roles (
    department_id BIGINT NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    role          user_role NOT NULL,
    PRIMARY KEY (department_id, role)
);

-- =====================================================================
-- 6. USERS
-- =====================================================================

CREATE TABLE users (
    id             BIGSERIAL PRIMARY KEY,
    name           VARCHAR(150) NOT NULL,
    email          VARCHAR(150) NOT NULL UNIQUE,
    password_hash  VARCHAR(255) NOT NULL,   -- bcrypt/passlib hash only, never plaintext
    role           user_role NOT NULL,
    department_id  BIGINT NOT NULL REFERENCES departments(id),
    is_active      BOOLEAN NOT NULL DEFAULT TRUE,
    last_login     TIMESTAMPTZ,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Enforces "DEPARTMENT â‰  ROLE" as a real constraint, not just a rule
    -- documented in prose: a user's (department_id, role) pair must exist
    -- in department_roles.
    FOREIGN KEY (department_id, role) REFERENCES department_roles(department_id, role)
);

CREATE INDEX idx_users_department ON users(department_id);
CREATE INDEX idx_users_role ON users(role);
CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =====================================================================
-- 7. STATIONS
-- =====================================================================

CREATE TABLE stations (
    id          BIGSERIAL PRIMARY KEY,
    name        VARCHAR(150) NOT NULL,
    code        VARCHAR(20)  NOT NULL UNIQUE,
    zone        VARCHAR(50),
    latitude    NUMERIC(9,6),
    longitude   NUMERIC(9,6),
    location    geometry(Point, 4326),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_stations_location ON stations USING GIST (location);

-- =====================================================================
-- 8. RAILWAY_SECTIONS
-- =====================================================================

CREATE TABLE railway_sections (
    id                BIGSERIAL PRIMARY KEY,
    section_code      VARCHAR(20) NOT NULL UNIQUE,
    name              VARCHAR(150),
    start_station_id  BIGINT NOT NULL REFERENCES stations(id),
    end_station_id    BIGINT NOT NULL REFERENCES stations(id),
    distance_km       NUMERIC(7,2),
    max_speed_kmph    INT,
    number_of_tracks  INT NOT NULL DEFAULT 1,
    geometry          geometry(LineString, 4326),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (start_station_id <> end_station_id)
);

CREATE INDEX idx_railway_sections_start ON railway_sections(start_station_id);
CREATE INDEX idx_railway_sections_end ON railway_sections(end_station_id);
CREATE INDEX idx_railway_sections_geometry ON railway_sections USING GIST (geometry);

-- =====================================================================
-- 9. TRACKS
-- One section can contain multiple tracks; blocking one track does not
-- automatically block the others (adjacent-line protection is a Safety
-- Engine decision, not a schema-level cascade).
-- =====================================================================

CREATE TABLE tracks (
    id          BIGSERIAL PRIMARY KEY,
    section_id  BIGINT NOT NULL REFERENCES railway_sections(id) ON DELETE CASCADE,
    track_code  VARCHAR(20) NOT NULL,
    track_name  VARCHAR(100),
    direction   VARCHAR(20),
    track_type  VARCHAR(50),
    status      VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',   -- ACTIVE / INACTIVE / etc. per spec
    geometry    geometry(LineString, 4326),
    UNIQUE (section_id, track_code)
);

CREATE INDEX idx_tracks_section ON tracks(section_id);
CREATE INDEX idx_tracks_status ON tracks(status);
CREATE INDEX idx_tracks_geometry ON tracks USING GIST (geometry);

-- =====================================================================
-- 10. ASSETS
-- =====================================================================

CREATE TABLE assets (
    id                     BIGSERIAL PRIMARY KEY,
    asset_code             VARCHAR(30) NOT NULL UNIQUE,
    name                   VARCHAR(150),
    asset_type             VARCHAR(50) NOT NULL,   -- Track / Rail / Signal / OHE / Electrical / Switch / Point / Bridge / Other
    department_id          BIGINT NOT NULL REFERENCES departments(id),
    section_id             BIGINT REFERENCES railway_sections(id),
    track_id               BIGINT REFERENCES tracks(id),
    installation_date      DATE,
    condition_score        NUMERIC(5,2) CHECK (condition_score BETWEEN 0 AND 100),
    asset_health_score     NUMERIC(5,2) CHECK (asset_health_score BETWEEN 0 AND 100),
    last_inspection_date   DATE,
    location               geometry(Point, 4326),
    status                 VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_assets_department ON assets(department_id);
CREATE INDEX idx_assets_section ON assets(section_id);
CREATE INDEX idx_assets_track ON assets(track_id);
CREATE INDEX idx_assets_type ON assets(asset_type);
CREATE INDEX idx_assets_location ON assets USING GIST (location);

-- =====================================================================
-- 11. ASSET_SENSOR_READINGS  [gap-closing, Section 11.3]
-- Time-series per-asset condition data the Asset Risk model actually
-- needs as input (vibration, wear, temperatures, brake/bearing condition)
-- â€” the spec flagged this as "not currently stored per-asset."
-- Column names mirror the Asset Risk model's documented input fields.
-- =====================================================================

CREATE TABLE asset_sensor_readings (
    id                      BIGSERIAL PRIMARY KEY,
    asset_id                BIGINT NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    recorded_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    rail_wear_mm            NUMERIC(6,2),
    wheel_wear_percent      NUMERIC(5,2),
    vibration_level         NUMERIC(6,3),
    ballast_condition       VARCHAR(30),
    track_curvature_degree  NUMERIC(6,3),
    ambient_temperature_c   NUMERIC(5,2),
    humidity_percent        NUMERIC(5,2),
    rainfall_mm             NUMERIC(6,2),
    axle_temperature_c      NUMERIC(5,2),
    bearing_temperature_c   NUMERIC(5,2),
    traction_motor_temp_c   NUMERIC(5,2),
    brake_pressure_psi      NUMERIC(6,2),
    brake_pad_wear_percent  NUMERIC(5,2),
    signal_system_status    VARCHAR(30),
    inspection_score        NUMERIC(5,2),
    sensor_health_index     NUMERIC(5,2),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_asset_sensor_readings_asset ON asset_sensor_readings(asset_id, recorded_at DESC);

-- =====================================================================
-- 12. ASSET_FAILURE_HISTORY  [gap-closing, Section 11.3]
-- "No historical failure log exists yet" â€” needed as Asset Risk model input.
-- =====================================================================

CREATE TABLE asset_failure_history (
    id             BIGSERIAL PRIMARY KEY,
    asset_id       BIGINT NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    failure_type   VARCHAR(100),
    failure_date   TIMESTAMPTZ NOT NULL,
    description    TEXT,
    downtime_mins  INT,
    resolved_at    TIMESTAMPTZ,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_asset_failure_history_asset ON asset_failure_history(asset_id);

-- =====================================================================
-- 13. WEATHER_READINGS  [gap-closing, Section 11.3]
-- =====================================================================

CREATE TABLE weather_readings (
    id                BIGSERIAL PRIMARY KEY,
    section_id        BIGINT REFERENCES railway_sections(id),
    station_id        BIGINT REFERENCES stations(id),
    recorded_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    temperature_c     NUMERIC(5,2),
    humidity_percent  NUMERIC(5,2),
    rainfall_mm       NUMERIC(6,2),
    wind_speed_kmph   NUMERIC(6,2),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (section_id IS NOT NULL OR station_id IS NOT NULL)
);

CREATE INDEX idx_weather_readings_section ON weather_readings(section_id, recorded_at DESC);
CREATE INDEX idx_weather_readings_station ON weather_readings(station_id, recorded_at DESC);

-- =====================================================================
-- 14. RESOURCES
-- =====================================================================

CREATE TABLE resources (
    id               BIGSERIAL PRIMARY KEY,
    resource_code    VARCHAR(30) NOT NULL UNIQUE,
    name             VARCHAR(150),
    department_id    BIGINT NOT NULL REFERENCES departments(id),
    resource_type    VARCHAR(50),   -- Worker / Track machine / Inspection equipment / etc.
    quantity         INT NOT NULL DEFAULT 1,
    is_available     BOOLEAN NOT NULL DEFAULT TRUE,
    available_from   TIMESTAMPTZ,
    available_until  TIMESTAMPTZ,
    location         geometry(Point, 4326),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (available_until IS NULL OR available_from IS NULL OR available_until > available_from)
);

CREATE INDEX idx_resources_department ON resources(department_id);
CREATE INDEX idx_resources_availability ON resources(is_available, available_from, available_until);
CREATE INDEX idx_resources_location ON resources USING GIST (location);

-- =====================================================================
-- 15. TRAINS
-- =====================================================================

CREATE TABLE trains (
    id                       BIGSERIAL PRIMARY KEY,
    train_number             VARCHAR(20) NOT NULL UNIQUE,
    train_name               VARCHAR(150),
    train_type               VARCHAR(30),   -- Express / Passenger / Freight / etc.
    priority                 VARCHAR(20),   -- operational priority
    source_station_id        BIGINT REFERENCES stations(id),
    destination_station_id   BIGINT REFERENCES stations(id),
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_trains_source ON trains(source_station_id);
CREATE INDEX idx_trains_destination ON trains(destination_station_id);

-- =====================================================================
-- 16. TRAIN_SCHEDULES
-- =====================================================================

CREATE TABLE train_schedules (
    id                    BIGSERIAL PRIMARY KEY,
    train_id              BIGINT NOT NULL REFERENCES trains(id) ON DELETE CASCADE,
    section_id            BIGINT NOT NULL REFERENCES railway_sections(id),
    track_id              BIGINT REFERENCES tracks(id),
    entry_time            TIMESTAMPTZ NOT NULL,
    exit_time             TIMESTAMPTZ NOT NULL,
    direction             VARCHAR(20),
    scheduled_delay_mins  INT NOT NULL DEFAULT 0,
    CHECK (exit_time > entry_time)
);

CREATE INDEX idx_train_schedules_train ON train_schedules(train_id);
CREATE INDEX idx_train_schedules_section_time ON train_schedules(section_id, entry_time, exit_time);
CREATE INDEX idx_train_schedules_track ON train_schedules(track_id);

-- =====================================================================
-- 17. MAINTENANCE_REQUESTS
-- Extended with actual_* outcome columns [gap-closing, Section 11.3 â€”
-- "maintenance_requests only stores the requested duration, not the
-- actual one; needed both for the Duration model's training labels and
-- for realistic re-estimation"], and with reviewed_by/rejection/revision
-- fields needed for self-approval protection (Section 9 of the SQL
-- generation instructions: "creator â‰  reviewer â‰  final approver").
-- =====================================================================

CREATE TABLE maintenance_requests (
    id                        BIGSERIAL PRIMARY KEY,
    request_code              VARCHAR(30) NOT NULL UNIQUE,
    asset_id                  BIGINT NOT NULL REFERENCES assets(id),
    department_id             BIGINT NOT NULL REFERENCES departments(id),
    requested_by              BIGINT NOT NULL REFERENCES users(id),
    section_id                BIGINT NOT NULL REFERENCES railway_sections(id),
    track_id                  BIGINT REFERENCES tracks(id),
    maintenance_type          VARCHAR(100) NOT NULL,
    description               TEXT,
    priority                  severity_level NOT NULL DEFAULT 'MEDIUM',
    requested_start           TIMESTAMPTZ NOT NULL,
    requested_end             TIMESTAMPTZ NOT NULL,
    requested_duration_mins   INT,
    status                    maintenance_request_status NOT NULL DEFAULT 'DRAFT',

    -- Review / self-approval-protection trail
    reviewed_by               BIGINT REFERENCES users(id),
    reviewed_at               TIMESTAMPTZ,
    rejection_reason          TEXT,
    revision_notes            TEXT,

    -- [gap-closing, Section 11.3] actual (vs requested) outcome, needed
    -- as Duration-model training labels and for realistic re-estimation
    actual_start              TIMESTAMPTZ,
    actual_end                TIMESTAMPTZ,
    actual_duration_mins      INT,
    actual_workers_used       INT,
    actual_equipment_count    INT,

    created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT now(),

    CHECK (requested_end > requested_start),
    CHECK (actual_end IS NULL OR actual_start IS NULL OR actual_end > actual_start),
    -- A reviewer can never be the same person who requested the work.
    CHECK (reviewed_by IS NULL OR reviewed_by <> requested_by)
);

CREATE INDEX idx_maintenance_requests_department ON maintenance_requests(department_id);
CREATE INDEX idx_maintenance_requests_status ON maintenance_requests(status);
CREATE INDEX idx_maintenance_requests_requested_by ON maintenance_requests(requested_by);
CREATE INDEX idx_maintenance_requests_section ON maintenance_requests(section_id);
CREATE INDEX idx_maintenance_requests_track ON maintenance_requests(track_id);
CREATE INDEX idx_maintenance_requests_asset ON maintenance_requests(asset_id);
CREATE INDEX idx_maintenance_requests_window ON maintenance_requests(requested_start, requested_end);
CREATE TRIGGER trg_maintenance_requests_updated_at
    BEFORE UPDATE ON maintenance_requests
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =====================================================================
-- 18. MAINTENANCE_PREDICTIONS
-- input_features column added [gap-closing, Section 11.3 â€” "only
-- prediction outputs are stored; the feature vector sent to the model
-- isn't persisted, which hurts explainability/audit"].
-- =====================================================================

CREATE TABLE maintenance_predictions (
    id                        BIGSERIAL PRIMARY KEY,
    maintenance_request_id    BIGINT NOT NULL REFERENCES maintenance_requests(id) ON DELETE CASCADE,
    asset_risk_score          NUMERIC(4,3) CHECK (asset_risk_score BETWEEN 0 AND 1),
    risk_level                severity_level,
    predicted_duration_mins   INT,
    train_impact_score        NUMERIC(6,3),
    predicted_delay_mins      INT,
    affected_train_count      INT,
    model_version             VARCHAR(50),
    input_features            JSONB,   -- [gap-closing] logged feature vector for audit/explainability
    predicted_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_maintenance_predictions_request ON maintenance_predictions(maintenance_request_id);

-- =====================================================================
-- 19. ML_MODEL_REGISTRY  [gap-closing, Section 11.3]
-- "No table tracks which model version is currently active per model
-- type (needed for the demoâ†’real adapter swap)."
-- =====================================================================

CREATE TABLE ml_model_registry (
    id                BIGSERIAL PRIMARY KEY,
    model_type        VARCHAR(30) NOT NULL
                      CHECK (model_type IN ('ASSET_RISK','MAINTENANCE_DURATION','TRAIN_IMPACT')),
    version           VARCHAR(50) NOT NULL,
    artifact_filename VARCHAR(255),      -- e.g. railway_maintenance_model_pipeline.joblib
    is_demo           BOOLEAN NOT NULL DEFAULT TRUE,   -- FALSE once a real trained model is plugged in
    is_active         BOOLEAN NOT NULL DEFAULT FALSE,
    trained_at        TIMESTAMPTZ,
    activated_at      TIMESTAMPTZ,
    notes             TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (model_type, version)
);

-- Only one active version per model type at a time.
CREATE UNIQUE INDEX idx_ml_model_registry_one_active
    ON ml_model_registry(model_type) WHERE is_active = TRUE;

-- =====================================================================
-- 20. BLOCK_REQUESTS
-- =====================================================================

CREATE TABLE block_requests (
    id                       BIGSERIAL PRIMARY KEY,
    block_code               VARCHAR(30) NOT NULL UNIQUE,
    maintenance_request_id   BIGINT NOT NULL REFERENCES maintenance_requests(id) ON DELETE CASCADE,
    section_id               BIGINT NOT NULL REFERENCES railway_sections(id),
    track_id                 BIGINT REFERENCES tracks(id),
    requested_start          TIMESTAMPTZ NOT NULL,
    requested_end            TIMESTAMPTZ NOT NULL,
    block_type               VARCHAR(50),
    status                   block_request_status NOT NULL DEFAULT 'REQUESTED',
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (requested_end > requested_start)
);

CREATE INDEX idx_block_requests_maintenance ON block_requests(maintenance_request_id);
CREATE INDEX idx_block_requests_section_track ON block_requests(section_id, track_id);
CREATE INDEX idx_block_requests_status ON block_requests(status);
CREATE INDEX idx_block_requests_window ON block_requests(requested_start, requested_end);

-- =====================================================================
-- 21. BLOCK_INTEGRATION_REQUESTS
-- Cross-department "Request to Join Block" workflow. Never auto-merged â€”
-- every row requires an explicit ACCEPT/REJECT/MODIFY response.
-- =====================================================================

CREATE TABLE block_integration_requests (
    id                          BIGSERIAL PRIMARY KEY,
    source_block_id             BIGINT NOT NULL REFERENCES block_requests(id) ON DELETE CASCADE,
    target_block_id             BIGINT NOT NULL REFERENCES block_requests(id) ON DELETE CASCADE,
    requesting_department_id    BIGINT NOT NULL REFERENCES departments(id),
    target_department_id        BIGINT NOT NULL REFERENCES departments(id),
    overlap_duration_mins       INT,
    compatibility_status        VARCHAR(30),
    requested_by                BIGINT NOT NULL REFERENCES users(id),
    response_by                 BIGINT REFERENCES users(id),
    response                    integration_response,
    reason                      TEXT,
    final_status                integration_final_status NOT NULL DEFAULT 'PENDING',
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (source_block_id <> target_block_id),
    CHECK (requesting_department_id <> target_department_id)
);

CREATE INDEX idx_block_integration_source ON block_integration_requests(source_block_id);
CREATE INDEX idx_block_integration_target ON block_integration_requests(target_block_id);
CREATE INDEX idx_block_integration_status ON block_integration_requests(final_status);
CREATE INDEX idx_block_integration_target_dept ON block_integration_requests(target_department_id);

-- =====================================================================
-- 22. OPTIMIZED_BLOCKS
-- Output of ML + Safety Engine + OR-Tools CP-SAT. combined_departments
-- is kept as an array exactly as named in the spec; optimized_block_sources
-- (next table) gives the queryable, referentially-checked version of the
-- same information.
-- =====================================================================

CREATE TABLE optimized_blocks (
    id                        BIGSERIAL PRIMARY KEY,
    block_code                VARCHAR(30) NOT NULL UNIQUE,
    section_id                BIGINT NOT NULL REFERENCES railway_sections(id),
    track_id                  BIGINT REFERENCES tracks(id),
    start_time                TIMESTAMPTZ NOT NULL,
    end_time                  TIMESTAMPTZ NOT NULL,
    total_duration_mins       INT,
    total_delay_mins          INT,
    affected_train_count      INT,
    ripple_impact_score       NUMERIC(6,3),
    resource_conflict_count   INT NOT NULL DEFAULT 0,
    combined_departments      TEXT[],
    optimization_score        NUMERIC(6,3),
    recommendation_reason     TEXT,
    status                    optimized_block_status NOT NULL DEFAULT 'PROPOSED',

    approved_by               BIGINT REFERENCES users(id),
    approved_at               TIMESTAMPTZ,
    -- Extended per Section 9 of the SQL-generation spec (store modified_by/
    -- rejected_by alongside approved_by for full decision traceability).
    modified_by               BIGINT REFERENCES users(id),
    modified_at               TIMESTAMPTZ,
    rejected_by               BIGINT REFERENCES users(id),
    rejected_at               TIMESTAMPTZ,
    rejection_reason          TEXT,

    created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (end_time > start_time)
);

CREATE INDEX idx_optimized_blocks_section_track ON optimized_blocks(section_id, track_id);
CREATE INDEX idx_optimized_blocks_status ON optimized_blocks(status);
CREATE INDEX idx_optimized_blocks_window ON optimized_blocks(start_time, end_time);

-- =====================================================================
-- 23. BLOCK_CANDIDATES  [gap-closing, Section 11.3]
-- "Only the final optimized_blocks row is stored; rejected candidates
-- (with their predicted delay/duration/risk and safety status) aren't
-- retained, which limits the explanation report promised to officials."
-- =====================================================================

CREATE TABLE block_candidates (
    id                            BIGSERIAL PRIMARY KEY,
    block_request_id              BIGINT NOT NULL REFERENCES block_requests(id) ON DELETE CASCADE,
    section_id                    BIGINT NOT NULL REFERENCES railway_sections(id),
    track_id                      BIGINT REFERENCES tracks(id),
    candidate_start               TIMESTAMPTZ NOT NULL,
    candidate_end                 TIMESTAMPTZ NOT NULL,
    predicted_duration_mins       INT,
    predicted_delay_mins          INT,
    affected_train_count          INT,
    asset_risk_score              NUMERIC(4,3),
    safety_status                 VARCHAR(12) NOT NULL CHECK (safety_status IN ('FEASIBLE','INFEASIBLE')),
    safety_rejection_reason       TEXT,
    optimization_score            NUMERIC(6,3),
    is_selected                   BOOLEAN NOT NULL DEFAULT FALSE,
    selected_optimized_block_id   BIGINT REFERENCES optimized_blocks(id),
    created_at                    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (candidate_end > candidate_start)
);

CREATE INDEX idx_block_candidates_request ON block_candidates(block_request_id);
CREATE INDEX idx_block_candidates_selected ON block_candidates(is_selected);

-- =====================================================================
-- 24. OPTIMIZED_BLOCK_SOURCES  (supporting table â€” see design note 4)
-- Which original block_requests (one per department) were merged into
-- a given optimized_blocks row. Required so "3+ department integrated
-- blocks" (Project Description Section 3 example) stay traceable rather
-- than relying solely on the free-text combined_departments array.
-- =====================================================================

CREATE TABLE optimized_block_sources (
    id                  BIGSERIAL PRIMARY KEY,
    optimized_block_id  BIGINT NOT NULL REFERENCES optimized_blocks(id) ON DELETE CASCADE,
    block_request_id    BIGINT NOT NULL REFERENCES block_requests(id) ON DELETE CASCADE,
    UNIQUE (optimized_block_id, block_request_id)
);

CREATE INDEX idx_optimized_block_sources_block ON optimized_block_sources(optimized_block_id);
CREATE INDEX idx_optimized_block_sources_request ON optimized_block_sources(block_request_id);

-- =====================================================================
-- 25. BLOCK_AFFECTED_TRAINS
-- =====================================================================

CREATE TABLE block_affected_trains (
    id                            BIGSERIAL PRIMARY KEY,
    block_id                      BIGINT NOT NULL REFERENCES optimized_blocks(id) ON DELETE CASCADE,
    train_id                      BIGINT NOT NULL REFERENCES trains(id),
    predicted_delay_mins          INT,
    impact_level                  severity_level,
    alternative_route_available   BOOLEAN NOT NULL DEFAULT FALSE,
    created_at                    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (block_id, train_id)
);

CREATE INDEX idx_block_affected_trains_block ON block_affected_trains(block_id);
CREATE INDEX idx_block_affected_trains_train ON block_affected_trains(train_id);

-- =====================================================================
-- 26. BLOCK_RESOURCE_ALLOCATIONS
-- =====================================================================

CREATE TABLE block_resource_allocations (
    id                  BIGSERIAL PRIMARY KEY,
    block_id            BIGINT NOT NULL REFERENCES optimized_blocks(id) ON DELETE CASCADE,
    resource_id         BIGINT NOT NULL REFERENCES resources(id),
    quantity_required   INT NOT NULL DEFAULT 1,
    allocated_from      TIMESTAMPTZ NOT NULL,
    allocated_until     TIMESTAMPTZ NOT NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'ALLOCATED'
                        CHECK (status IN ('ALLOCATED','RELEASED','CANCELLED')),
    CHECK (allocated_until > allocated_from)
);

CREATE INDEX idx_block_resource_allocations_block ON block_resource_allocations(block_id);
CREATE INDEX idx_block_resource_allocations_resource ON block_resource_allocations(resource_id, allocated_from, allocated_until);

-- =====================================================================
-- 27. NOTIFICATIONS
-- block_request_id added alongside optimized_block_id: integration-
-- opportunity notifications fire before an optimized_blocks row exists,
-- so a single "block_id" column can't unambiguously reference both
-- stages. Neither replaces the other.
-- =====================================================================

CREATE TABLE notifications (
    id                         BIGSERIAL PRIMARY KEY,
    recipient_user_id          BIGINT REFERENCES users(id),
    recipient_department_id    BIGINT REFERENCES departments(id),
    type                       notification_type NOT NULL,
    title                      VARCHAR(150) NOT NULL,
    message                    TEXT,
    section_id                 BIGINT REFERENCES railway_sections(id),
    track_id                   BIGINT REFERENCES tracks(id),
    block_request_id           BIGINT REFERENCES block_requests(id),
    optimized_block_id         BIGINT REFERENCES optimized_blocks(id),
    integration_request_id     BIGINT REFERENCES block_integration_requests(id),
    priority                   notification_priority NOT NULL DEFAULT 'NORMAL',
    is_read                    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at                 TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (recipient_user_id IS NOT NULL OR recipient_department_id IS NOT NULL)
);

CREATE INDEX idx_notifications_recipient_user ON notifications(recipient_user_id, is_read);
CREATE INDEX idx_notifications_recipient_dept ON notifications(recipient_department_id, is_read);
CREATE INDEX idx_notifications_type ON notifications(type);
CREATE INDEX idx_notifications_created ON notifications(created_at DESC);

-- =====================================================================
-- 28. INCIDENTS
-- =====================================================================

CREATE TABLE incidents (
    id                     BIGSERIAL PRIMARY KEY,
    incident_code          VARCHAR(30) NOT NULL UNIQUE,
    incident_type          incident_type NOT NULL,
    severity               severity_level NOT NULL DEFAULT 'HIGH',
    description            TEXT,
    section_id             BIGINT REFERENCES railway_sections(id),
    track_id               BIGINT REFERENCES tracks(id),
    latitude               NUMERIC(9,6),
    longitude              NUMERIC(9,6),
    location               geometry(Point, 4326),
    reported_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    reported_by            BIGINT REFERENCES users(id),
    railway_alert_status   VARCHAR(30),
    police_alert_status    VARCHAR(30),
    response_status        incident_response_status NOT NULL DEFAULT 'OPEN',
    clearance_time         TIMESTAMPTZ
);

CREATE INDEX idx_incidents_section ON incidents(section_id);
CREATE INDEX idx_incidents_track ON incidents(track_id);
CREATE INDEX idx_incidents_status ON incidents(response_status);
CREATE INDEX idx_incidents_reported_at ON incidents(reported_at DESC);
CREATE INDEX idx_incidents_location ON incidents USING GIST (location);

-- =====================================================================
-- 29. EMERGENCY_RESPONSES
-- Prototype data only â€” no autonomous police/emergency dispatch is
-- implied; this table tracks acknowledgement through a designated,
-- authorized communication channel.
-- =====================================================================

CREATE TABLE emergency_responses (
    id                      BIGSERIAL PRIMARY KEY,
    incident_id             BIGINT NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    authority_type          VARCHAR(50),
    authority_name          VARCHAR(150),
    notification_time       TIMESTAMPTZ,
    acknowledgement_time    TIMESTAMPTZ,
    arrival_time            TIMESTAMPTZ,
    clearance_time          TIMESTAMPTZ,
    status                  emergency_response_status NOT NULL DEFAULT 'ALERT_RECEIVED',
    notes                   TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_emergency_responses_incident ON emergency_responses(incident_id);
CREATE INDEX idx_emergency_responses_status ON emergency_responses(status);

-- =====================================================================
-- 30. SIMULATIONS
-- What-if / Digital Twin scenarios. Must never modify the original block
-- â€” enforced by convention (no UPDATE path onto optimized_blocks from
-- this table) plus the fact that modified_* fields live here, not there.
-- =====================================================================

CREATE TABLE simulations (
    id                          BIGSERIAL PRIMARY KEY,
    simulation_name             VARCHAR(150),
    created_by                  BIGINT NOT NULL REFERENCES users(id),
    original_block_id           BIGINT NOT NULL REFERENCES optimized_blocks(id),
    modified_start_time         TIMESTAMPTZ,
    modified_end_time           TIMESTAMPTZ,
    additional_department_id    BIGINT REFERENCES departments(id),
    predicted_delay_mins        INT,
    affected_train_count        INT,
    ripple_impact_score         NUMERIC(6,3),
    optimization_score          NUMERIC(6,3),
    result_summary              TEXT,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        modified_end_time IS NULL OR modified_start_time IS NULL
        OR modified_end_time > modified_start_time
    )
);

CREATE INDEX idx_simulations_original_block ON simulations(original_block_id);
CREATE INDEX idx_simulations_created_by ON simulations(created_by);

-- =====================================================================
-- 31. AUDIT_LOGS
-- action is free-text (not an enum) because the specs across documents
-- use several overlapping-but-not-identical vocabularies for the same
-- events (e.g. "APPROVE_BLOCK" vs "Block approval") and audit logging
-- is meant to be extensible without a schema migration each time.
-- Append-oriented: no UPDATE/DELETE grants should be given to app roles.
-- =====================================================================

CREATE TABLE audit_logs (
    id            BIGSERIAL PRIMARY KEY,
    user_id       BIGINT REFERENCES users(id),   -- nullable: e.g. failed login before identity is known
    action        VARCHAR(100) NOT NULL,
    entity_type   VARCHAR(50),
    entity_id     BIGINT,
    old_status    VARCHAR(50),
    new_status    VARCHAR(50),
    description   TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_logs_user ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_entity ON audit_logs(entity_type, entity_id);
CREATE INDEX idx_audit_logs_created ON audit_logs(created_at DESC);

-- =====================================================================
-- 32. VIEW: SECTION_TRAFFIC_STATS  [gap-closing, Section 11.3]
-- "Section traffic density â€” derivable from train_schedules but worth
-- pre-aggregating into a section_traffic_stats view for the Train
-- Impact model." Implemented as a view (not a table) since it is fully
-- derivable and should never drift out of sync with train_schedules.
-- =====================================================================

CREATE VIEW section_traffic_stats AS
SELECT
    ts.section_id,
    COUNT(*)                                                   AS total_scheduled_trains,
    COUNT(*) FILTER (WHERE ts.entry_time::date = CURRENT_DATE) AS trains_today,
    AVG(ts.scheduled_delay_mins)                               AS avg_scheduled_delay_mins,
    MAX(ts.scheduled_delay_mins)                                AS max_scheduled_delay_mins
FROM train_schedules ts
GROUP BY ts.section_id;

-- =====================================================================
-- 33. SEED / REFERENCE DATA
-- Only the two lookup tables required for the schema itself to be usable
-- are seeded here (departments + their valid roles). Per Section 26 of
-- the generation instructions, no large synthetic operational dataset
-- (stations/trains/assets/etc.) is inserted â€” that belongs to the
-- backend's own DEMO/SYNTHETIC data loader, clearly labelled as such.
-- =====================================================================

INSERT INTO departments (name, code) VALUES
    ('Engineering', 'ENG'),
    ('Electrical / Traction', 'ELEC'),
    ('Signal & Telecommunication', 'SNT'),
    ('Operations / Traffic', 'OPS'),
    ('Railway Control', 'CONTROL'),
    ('Railway', 'RAILWAY'),
    ('Emergency', 'EMERGENCY');

INSERT INTO department_roles (department_id, role)
SELECT d.id, r.role
FROM departments d
JOIN (VALUES
    ('ENG',       'MAINTENANCE_STAFF'::user_role),
    ('ENG',       'ENGINEER_REVIEWER'::user_role),
    ('ELEC',      'MAINTENANCE_STAFF'::user_role),
    ('ELEC',      'ENGINEER_REVIEWER'::user_role),
    ('SNT',       'MAINTENANCE_STAFF'::user_role),
    ('SNT',       'ENGINEER_REVIEWER'::user_role),
    ('OPS',       'OPERATOR'::user_role),
    ('CONTROL',   'CONTROLLER'::user_role),
    ('RAILWAY',   'AUTHORIZED_OFFICIAL'::user_role),
    ('EMERGENCY', 'EMERGENCY_OPERATOR'::user_role)
) AS r(code, role) ON r.code = d.code;

COMMIT;

-- =====================================================================
-- END OF SCRIPT
-- =====================================================================

