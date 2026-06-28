const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
function uuidv4() { return crypto.randomUUID(); }

const content = fs.readFileSync(path.join(__dirname, '../agency-agents-main/MinerU_markdown_SOW_2043379928930082816.md'), 'utf-8');
const rows = content.match(/<tr>.*?<\/tr>/gs) || [];

let data = [];
let currentUnit = null;
let currentChapter = null;
let currentSpec = null;

function getText(td) {
    if (!td) return '';
    return td.replace(/<[^>]+>/g, '').trim();
}

rows.forEach((row, index) => {
    if (index < 2) return;
    const tds = row.match(/<td[^>]*>(.*?)<\/td>/gs);
    if (!tds || tds.length < 6) return;

    const resourceText = getText(tds[tds.length - 1]);
    const activityText = getText(tds[tds.length - 2]);
    const descText = getText(tds[tds.length - 3]);
    const refText = getText(tds[tds.length - 4]);
    const chapterText = getText(tds[tds.length - 5]);
    const unitText = getText(tds[tds.length - 6]);

    if (unitText) currentUnit = unitText;
    if (chapterText) currentChapter = chapterText;

    if (!currentUnit) return;

    let spec = null;
    if (refText) {
        currentSpec = {
            id: uuidv4(),
            reference_code: refText,
            description: descText,
            is_physics_only: refText.toUpperCase().includes('P'),
            activities: [],
            resources: []
        };
        spec = currentSpec;

        let unitNode = data.find(u => u.title === currentUnit);
        if (!unitNode) {
            unitNode = { id: uuidv4(), title: currentUnit, chapters: [] };
            data.push(unitNode);
        }

        let chapterNode = unitNode.chapters.find(c => c.title === currentChapter);
        if (!chapterNode) {
            chapterNode = { id: uuidv4(), title: currentChapter, specs: [] };
            unitNode.chapters.push(chapterNode);
        }

        chapterNode.specs.push(currentSpec);
    } else if (!refText && currentSpec && (activityText || resourceText)) {
        spec = currentSpec;
    }

    if (spec) {
        if (activityText && activityText.length > 0) spec.activities.push(activityText);
        if (resourceText && resourceText.length > 0) spec.resources.push(resourceText);
    }
});

function esc(t) {
    if (t == null) return "";
    return String(t).replace(/'/g, "''");
}

let sqlTables = `-- ==============================================================================
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
`;

let sqlUnitsChapters = "";
data.forEach(u => {
    sqlUnitsChapters += `INSERT INTO units (id, title) VALUES ('${u.id}', '${esc(u.title)}') ON CONFLICT DO NOTHING;\n`;
});
sqlUnitsChapters += "\n";

data.forEach(u => {
    u.chapters.forEach(c => {
        sqlUnitsChapters += `INSERT INTO chapters (id, unit_id, title) VALUES ('${c.id}', '${u.id}', '${esc(c.title)}');\n`;
    });
});
sqlUnitsChapters += "\n";

let sqlSpecs = "";
data.forEach(u => {
    u.chapters.forEach(c => {
        c.specs.forEach(p => {
            sqlSpecs += `INSERT INTO specification_points (id, chapter_id, reference_code, description, is_physics_only) VALUES ('${p.id}', '${c.id}', '${esc(p.reference_code)}', '${esc(p.description)}', ${p.is_physics_only});\n`;
        });
    });
});
sqlSpecs += "\n";

let sqlActivitiesResources = "";
data.forEach(u => {
    u.chapters.forEach(c => {
        c.specs.forEach(p => {
            p.activities.forEach(act => {
                sqlActivitiesResources += `INSERT INTO activities (id, specification_point_id, description) VALUES ('${uuidv4()}', '${p.id}', '${esc(act)}');\n`;
            });
            p.resources.forEach(res => {
                sqlActivitiesResources += `INSERT INTO resources (id, specification_point_id, title) VALUES ('${uuidv4()}', '${p.id}', '${esc(res)}');\n`;
            });
        });
    });
});

const outPath1 = path.join(__dirname, 'mig_1_tables.sql');
fs.writeFileSync(outPath1, sqlTables, 'utf-8');

const outPath2 = path.join(__dirname, 'mig_2_units_chapters.sql');
fs.writeFileSync(outPath2, sqlUnitsChapters, 'utf-8');

const outPath3 = path.join(__dirname, 'mig_3_specs.sql');
fs.writeFileSync(outPath3, sqlSpecs, 'utf-8');

const outPath4 = path.join(__dirname, 'mig_4_activities_resources.sql');
fs.writeFileSync(outPath4, sqlActivitiesResources, 'utf-8');

console.log("Schema chunked into 4 files successfully.");
