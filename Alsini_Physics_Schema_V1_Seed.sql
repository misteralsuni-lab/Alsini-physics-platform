-- ======================================================================================
-- A-Level / IGCSE Physics Data Seed
-- Section 1: Forces and Motion
-- Structure: Courses -> Chapters -> Topics -> Subtopics
-- ======================================================================================

WITH new_course AS (
    INSERT INTO public.courses (title, description)
    VALUES (
        'Edexcel IGCSE Physics (4PH1)', 
        'Complete comprehensive revision for the Edexcel IGCSE (4PH1) specification.'
    )
    RETURNING id
),
new_chapter AS (
    INSERT INTO public.chapters (course_id, chapter_number, title, description)
    SELECT 
        id, 
        1, 
        'Forces and Motion', 
        'Understanding units, movement, position, forces, shape, and momentum.'
    FROM new_course
    RETURNING id
),
new_topics AS (
    INSERT INTO public.topics (chapter_id, title)
    SELECT id, 'Units' FROM new_chapter UNION ALL
    SELECT id, 'Movement and position' FROM new_chapter UNION ALL
    SELECT id, 'Forces, movement, shape and momentum' FROM new_chapter
    RETURNING id, title
)
INSERT INTO public.subtopics (topic_id, title)
-- Subtopics matched to the dynamically generated "Units" UUID
SELECT id, 'Base and Derived Units' FROM new_topics WHERE title = 'Units'
UNION ALL

-- Subtopics matched to the dynamically generated "Movement and position" UUID
SELECT id, 'Distance, Speed and Time' FROM new_topics WHERE title = 'Movement and position' UNION ALL
SELECT id, 'Acceleration' FROM new_topics WHERE title = 'Movement and position' UNION ALL
SELECT id, 'Distance-Time and Velocity-Time Graphs' FROM new_topics WHERE title = 'Movement and position' UNION ALL

-- Subtopics matched to the dynamically generated "Forces, movement, shape and momentum" UUID
SELECT id, 'Types of Forces' FROM new_topics WHERE title = 'Forces, movement, shape and momentum' UNION ALL
SELECT id, 'Resultant Forces and Friction' FROM new_topics WHERE title = 'Forces, movement, shape and momentum' UNION ALL
SELECT id, 'Weight, Mass and Gravity' FROM new_topics WHERE title = 'Forces, movement, shape and momentum' UNION ALL
SELECT id, 'Stopping Distances' FROM new_topics WHERE title = 'Forces, movement, shape and momentum' UNION ALL
SELECT id, 'Terminal Velocity' FROM new_topics WHERE title = 'Forces, movement, shape and momentum' UNION ALL
SELECT id, 'Hooke''s Law and Elasticity' FROM new_topics WHERE title = 'Forces, movement, shape and momentum' UNION ALL
SELECT id, 'Momentum and Conservation' FROM new_topics WHERE title = 'Forces, movement, shape and momentum' UNION ALL
SELECT id, 'Newton''s Laws of Motion' FROM new_topics WHERE title = 'Forces, movement, shape and momentum' UNION ALL
SELECT id, 'Moments and Centre of Gravity' FROM new_topics WHERE title = 'Forces, movement, shape and momentum';
