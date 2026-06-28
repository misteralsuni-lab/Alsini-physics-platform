-- ==============================================================================
-- ALSINI PHYSICS: SCHEME OF WORK SUMMARY SCHEMA & DATA (CORRECTED MAPPING)
-- ==============================================================================

-- DROP OLD INCORRECT TABLES IF THEY EXIST
DROP TABLE IF EXISTS questions CASCADE;
DROP TABLE IF EXISTS resources CASCADE;
DROP TABLE IF EXISTS activities CASCADE;
DROP TABLE IF EXISTS specification_points CASCADE;
DROP TABLE IF EXISTS sections CASCADE;
DROP TABLE IF EXISTS chapters CASCADE;
DROP TABLE IF EXISTS units CASCADE;

CREATE TABLE units (
    id UUID PRIMARY KEY,
    title VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE chapters (
    id UUID PRIMARY KEY,
    unit_id UUID REFERENCES units(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(unit_id, title)
);

CREATE TABLE specification_points (
    id UUID PRIMARY KEY,
    chapter_id UUID REFERENCES chapters(id) ON DELETE CASCADE,
    reference_code VARCHAR(50) NOT NULL UNIQUE,
    description TEXT NOT NULL,
    is_physics_only BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE activities (
    id UUID PRIMARY KEY,
    specification_point_id UUID REFERENCES specification_points(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE resources (
    id UUID PRIMARY KEY,
    specification_point_id UUID REFERENCES specification_points(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE questions (
    id UUID PRIMARY KEY,
    specification_point_id UUID REFERENCES specification_points(id) ON DELETE CASCADE,
    question_pdf_url TEXT,
    mark_scheme_pdf_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_chapters_unit_id ON chapters(unit_id);
CREATE INDEX idx_spec_points_chapter_id ON specification_points(chapter_id);
CREATE INDEX idx_spec_points_code ON specification_points(reference_code);
CREATE INDEX idx_activities_spec_id ON activities(specification_point_id);
CREATE INDEX idx_resources_spec_id ON resources(specification_point_id);
CREATE INDEX idx_questions_spec_id ON questions(specification_point_id);
