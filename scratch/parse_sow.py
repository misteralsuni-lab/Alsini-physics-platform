from bs4 import BeautifulSoup
import json
import re
import uuid
import os

with open(r'agency-agents-main\MinerU_markdown_SOW_2043379928930082816.md', 'r', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')

data = []
current_unit = None
current_chapter = None
current_spec = None

for i, row in enumerate(soup.find_all('tr')):
    if i < 2: continue # skip headers
    
    tds = row.find_all('td')
    if len(tds) < 6: continue
    
    # Use backward indexing to ignore broken colspan alignment
    resource_text = tds[-1].get_text(strip=True)
    activity_text = tds[-2].get_text(strip=True)
    desc_text = tds[-3].get_text(strip=True)
    ref_text = tds[-4].get_text(strip=True)
    chapter_text = tds[-5].get_text(strip=True)
    unit_text = tds[-6].get_text(strip=True)

    if unit_text: current_unit = unit_text
    if chapter_text: current_chapter = chapter_text
    
    # We must skip rows that don't belong to any valid unit/chapter
    if not current_unit: continue

    spec = None
    if ref_text:
        current_spec = {
            'reference_code': ref_text,
            'description': desc_text,
            'is_physics_only': 'P' in ref_text.upper(),
            'activities': [],
            'resources': []
        }
        spec = current_spec
        # Ensure unit and chapter exist
        unit_node = next((u for u in data if u['title'] == current_unit), None)
        if not unit_node:
            unit_node = {'title': current_unit, 'chapters': []}
            data.append(unit_node)
            
        chapter_node = next((c for c in unit_node['chapters'] if c['title'] == current_chapter), None)
        if not chapter_node:
            chapter_node = {'title': current_chapter, 'specs': []}
            unit_node['chapters'].append(chapter_node)
            
        chapter_node['specs'].append(current_spec)
        
    elif not ref_text and current_spec and (activity_text or resource_text):
        # Activity/Resource corresponding to current spec
        spec = current_spec
        
    if spec:
        if activity_text: spec['activities'].append(activity_text)
        if resource_text: spec['resources'].append(resource_text)

# Generate SQL
sql = """-- ==============================================================================
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

-- ------------------------------------------------------------------------------
-- 1. SCHEMA DESIGN
-- ------------------------------------------------------------------------------

CREATE TABLE units (
    id UUID PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE chapters (
    id UUID PRIMARY KEY,
    unit_id UUID REFERENCES units(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE specification_points (
    id UUID PRIMARY KEY,
    chapter_id UUID REFERENCES chapters(id) ON DELETE CASCADE,
    reference_code VARCHAR(50) NOT NULL,
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

-- Indexing for high-performance reading
CREATE INDEX idx_chapters_unit_id ON chapters(unit_id);
CREATE INDEX idx_spec_points_chapter_id ON specification_points(chapter_id);
CREATE INDEX idx_spec_points_code ON specification_points(reference_code);
CREATE INDEX idx_activities_spec_id ON activities(specification_point_id);
CREATE INDEX idx_resources_spec_id ON resources(specification_point_id);
CREATE INDEX idx_questions_spec_id ON questions(specification_point_id);

-- ------------------------------------------------------------------------------
-- 2. DATA SEEDING
-- ------------------------------------------------------------------------------
"""

def esc(t):
    return t.replace("'", "''")

# First generate UUIDs for everything
for u in data:
    u['id'] = str(uuid.uuid4())
    for c in u['chapters']:
        c['id'] = str(uuid.uuid4())
        for p in c['specs']:
            p['id'] = str(uuid.uuid4())

# Now write single block inserts (for batching)
def write_insert(table, columns, rows):
    if not rows: return ""
    chunk_size = 50
    res = ""
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i:i+chunk_size]
        res += f"INSERT INTO {table} ({', '.join(columns)}) VALUES\n"
        values = []
        for r in chunk:
            vals = []
            for v in r:
                if isinstance(v, bool): vals.append('true' if v else 'false')
                elif v is None: vals.append('NULL')
                else: vals.append(f"'{esc(str(v))}'")
            values.append(f"({', '.join(vals)})")
        res += ",\n".join(values) + ";\n\n"
    return res

unit_rows = []
chapter_rows = []
spec_rows = []
activity_rows = []
resource_rows = []

for u in data:
    unit_rows.append((u['id'], u['title']))
    for c in u['chapters']:
        chapter_rows.append((c['id'], u['id'], c['title']))
        for p in c['specs']:
            spec_rows.append((p['id'], c['id'], p['reference_code'], p['description'], p['is_physics_only']))
            for act in p['activities']:
                activity_rows.append((str(uuid.uuid4()), p['id'], act))
            for res in p['resources']:
                resource_rows.append((str(uuid.uuid4()), p['id'], res))

sql += write_insert("units", ["id", "title"], unit_rows)
sql += write_insert("chapters", ["id", "unit_id", "title"], chapter_rows)
sql += write_insert("specification_points", ["id", "chapter_id", "reference_code", "description", "is_physics_only"], spec_rows)
sql += write_insert("activities", ["id", "specification_point_id", "description"], activity_rows)
sql += write_insert("resources", ["id", "specification_point_id", "title"], resource_rows)

out_file = os.path.join(os.path.dirname(__file__), 'save_my_exams_schema.sql')
with open(out_file, 'w', encoding='utf-8') as f:
    f.write(sql)

print(f"Schema generated successfully at {out_file}")
