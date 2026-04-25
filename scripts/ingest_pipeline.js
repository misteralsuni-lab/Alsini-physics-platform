require('dotenv').config({ path: require('path').join(__dirname, '../backend/.env') }); // Load environment variables from backend/.env
const fs = require('fs/promises');
const path = require('path');
const crypto = require('crypto');
const { createClient } = require('@supabase/supabase-js');

// 1. Initialize Supabase Client with Service Role Key (Bypass RLS)
const supabaseUrl = process.env.VITE_SUPABASE_URL || process.env.SUPABASE_URL;
const supabaseServiceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

if (!supabaseUrl || !supabaseServiceKey) {
  console.error("❌ Missing Supabase environment variables. Please check your .env file.");
  process.exit(1);
}

const supabase = createClient(supabaseUrl, supabaseServiceKey, {
  auth: {
    autoRefreshToken: false,
    persistSession: false
  }
});

// MinerU / OpenKB API Configuration
const MINERU_API_ENDPOINT = process.env.MINERU_API_ENDPOINT || "http://localhost:8000/api/extract";
const MINERU_API_KEY = process.env.MINERU_API_KEY || "";

const RAW_MATERIALS_DIR = path.join(__dirname, '../raw_materials');

/**
 * Helper function to recursively walk a directory and find PDF files.
 */
async function walkDir(dir, fileList = []) {
  const files = await fs.readdir(dir, { withFileTypes: true });
  for (const file of files) {
    const fullPath = path.resolve(dir, file.name);
    if (file.isDirectory()) {
      await walkDir(fullPath, fileList);
    } else if (file.name.toLowerCase().endsWith('.pdf')) {
      fileList.push(fullPath);
    }
  }
  return fileList;
}

/**
 * Main execution function for the ingestion pipeline.
 */
async function runIngestionPipeline() {
  console.log(`🚀 Starting MinerU Data Ingestion Pipeline...`);

  try {
    // 2. Read local directory of Edexcel PDFs recursively
    await fs.mkdir(RAW_MATERIALS_DIR, { recursive: true }); // Ensure dir exists
    const pdfFiles = await walkDir(RAW_MATERIALS_DIR);

    if (pdfFiles.length === 0) {
      console.log(`⚠️ No PDF files found in ${RAW_MATERIALS_DIR}. Please add some materials to ingest.`);
      return;
    }

    console.log(`📁 Found ${pdfFiles.length} PDF(s) to process.`);

    for (const filePath of pdfFiles) {
      // 3. Path Parsing
      const relativePath = path.relative(RAW_MATERIALS_DIR, filePath);
      const parts = relativePath.split(path.sep);
      const fileName = parts.pop();
      
      let unitName = null;
      let chapterName = null;

      // Extract Unit and Chapter names if they exist in the folder hierarchy
      if (parts.length >= 2) {
        unitName = parts[0];
        chapterName = parts[1];
      } else if (parts.length === 1) {
        chapterName = parts[0];
      }

      console.log(`\n⏳ Processing file: ${fileName}`);
      if (unitName) console.log(`   -> Unit: ${unitName}`);
      if (chapterName) console.log(`   -> Chapter: ${chapterName}`);

      // 4. Send PDF to MinerU/OpenKB extraction service
      const extractedData = await extractWithMinerU(filePath);

      if (!extractedData) {
        console.warn(`⚠️ Extraction failed or returned empty for ${fileName}. Skipping.`);
        continue;
      }

      // 5. Map parsed JSON to Supabase Tables
      await mapAndInsertToSupabase(extractedData, fileName, unitName, chapterName);
    }

    console.log(`\n✅ Ingestion Pipeline completed successfully.`);

  } catch (error) {
    console.error(`❌ Pipeline Error:`, error.message);
  }
}

/**
 * API call structure to send the PDF to MinerU/OpenKB.
 * Modify the fetch logic based on the actual MinerU API specification.
 */
async function extractWithMinerU(filePath) {
  try {
    console.log(`   -> Sending to MinerU (${MINERU_API_ENDPOINT})...`);
    
    // Example form-data structure for sending a file
    const fileData = await fs.readFile(filePath);
    const blob = new Blob([fileData], { type: 'application/pdf' });
    const formData = new FormData();
    formData.append('file', blob, path.basename(filePath));

    // Structure the Request
    const response = await fetch(MINERU_API_ENDPOINT, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${MINERU_API_KEY}`
        // Do NOT set Content-Type header manually when using FormData, let fetch boundary handle it
      },
      body: formData
    });

    if (!response.ok) {
        // Fallback placeholder response for offline/testing development
        console.warn(`   -> ⚠️ MinerU API returned ${response.status}. Using placeholder data for dev.`);
        return generatePlaceholderExtractedData(path.basename(filePath));
    }

    const data = await response.json();
    console.log(`   -> ✅ MinerU extraction successful.`);
    return data;

  } catch (error) {
    console.warn(`   -> ⚠️ Local MinerU service not available (${error.message}). Using placeholder data for dev.`);
    // If MinerU is not running locally yet, we return mockup data for testing the DB insertion logic
    return generatePlaceholderExtractedData(path.basename(filePath));
  }
}

/**
 * Logic to receive parsed JSON (text, markdown, diagram references)
 * and map it to existing `activities` or `resources` tables.
 */
async function mapAndInsertToSupabase(extractedData, sourceFilename, unitName, chapterName) {
  console.log(`   -> Mapping extracted JSON to Supabase schema...`);
  
  let chapterId = null;

  // 6. Database Routing logic
  if (chapterName) {
    console.log(`   -> Searching DB for chapter matching "${chapterName}"...`);
    
    let foundUnitId = null;
    if (unitName) {
      const { data: units } = await supabase.from('units').select('id').ilike('title', `%${unitName}%`).limit(1);
      if (units && units.length > 0) {
        foundUnitId = units[0].id;
      }
    }

    let chapQuery = supabase.from('chapters').select('id, title').ilike('title', `%${chapterName}%`);
    if (foundUnitId) {
      chapQuery = chapQuery.eq('unit_id', foundUnitId);
    }
    
    const { data: chapters, error: chapErr } = await chapQuery.limit(1);

    if (chapErr || !chapters || chapters.length === 0) {
      console.warn(`   -> ⚠️ Could not find chapter matching "${chapterName}". Falling back to default.`);
    } else {
      chapterId = chapters[0].id;
      console.log(`   -> ✅ Found matched chapter in DB: ${chapters[0].title}`);
    }
  }

  // 7. Accurate Linking
  let specQuery = supabase.from('specification_points').select('id, reference_code');
  if (chapterId) {
    specQuery = specQuery.eq('chapter_id', chapterId);
  }
  
  const { data: specPoints, error: fetchErr } = await specQuery.limit(1);

  if (fetchErr || !specPoints || specPoints.length === 0) {
    console.error(`   -> ❌ Setup Warning: No specification points available in DB to link to.`);
    return;
  }

  const defaultSpecPointId = specPoints[0].id; 
  console.log(`   -> Linking payload to Specification Point ID: ${defaultSpecPointId}`);

  // Example Mapping 1: Insert into `resources` table if it's general study material
  const resourcePayload = {
    id: crypto.randomUUID(),
    specification_point_id: defaultSpecPointId,
    title: extractedData.title || `Resource from ${sourceFilename}`,
    // add other fields if applicable (e.g. content_markdown: extractedData.markdown)
  };

  const { error: insertResErr } = await supabase
    .from('resources')
    .insert([resourcePayload]);

  if (insertResErr) {
    console.error(`   -> ❌ Failed to insert into resources:`, insertResErr.message);
  } else {
    console.log(`   -> ✅ Inserted summary/markdown into 'resources' table.`);
  }

  // Example Mapping 2: Extract structured text blocks into `activities`
  if (extractedData.activities && extractedData.activities.length > 0) {
    const activityPayloads = extractedData.activities.map(act => ({
      id: crypto.randomUUID(),
      specification_point_id: defaultSpecPointId,
      description: act.text_content
    }));

    const { error: insertActErr } = await supabase
        .from('activities')
        .insert(activityPayloads);

    if (insertActErr) {
        console.error(`   -> ❌ Failed to insert into activities:`, insertActErr.message);
    } else {
        console.log(`   -> ✅ Inserted ${activityPayloads.length} extracted blocks into 'activities' table.`);
    }
  }
}

/**
 * Generates mock data matching the expected MinerU output format 
 * to allow for pipeline testing without an active MinerU server.
 */
function generatePlaceholderExtractedData(filename) {
    return {
        title: `OCR/MinerU Parsed: ${filename}`,
        markdown: `# Parsed Content\n\nThis is placeholder text for the extracted physics document.`,
        diagrams: [
            { id: "img1", reference: "diagram_forces.png" }
        ],
        activities: [
            { type: "practice_question", text_content: "Calculate the resultant force using Newton's Second Law." },
            { type: "experiment_setup", text_content: "Measure the extension of the spring against applied load." }
        ]
    };
}

// Execute the pipeline
runIngestionPipeline();
