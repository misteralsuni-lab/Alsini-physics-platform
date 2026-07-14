# Alsini Physics VLE - Project Summary & Backup Plan

This document serves as a comprehensive summary and backup of all the work completed so far on the **Alsini Physics Frontend** project.

## 1. Project Overview
The project is a modern, Open Access educational website tailored for **Edexcel IGCSE and A-Level Physics** revision. It is designed to mimic a traditional university Virtual Learning Environment (VLE) while maintaining a premium, modern user experience. 
- **Core Aesthetic**: Dark mode by default, clean layouts, and a highly responsive design.
- **Goal**: To provide an interactive, structured, and easy-to-navigate learning platform for physics students.

## 2. Technology Stack
- **Frontend Framework**: React (via Vite)
- **Styling**: Tailwind CSS
- **Animations**: GSAP, Framer Motion
- **Icons**: Lucide React
- **Backend & Auth**: Supabase (Database, Authentication, Row Level Security, Storage)
- **Backend API**: Dual stack — legacy Node.js Express (`backend/server.js`) and the primary FastAPI service (`backend/main.py`, Uvicorn, port 8000) that now powers chat, search, and grading
- **Embeddings / Vector Search**: pgvector on Supabase, NVIDIA `nv-embedqa-e5-v5` (1024-dim) via the NVIDIA API, HNSW cosine index
- **AI Models**: Google Gemini 2.5 Flash (Socratic tutor), Gemini/NVIDIA Nemotron for grading, NVIDIA NIM vision models for PDF ingestion
- **Ingestion**: Python pipeline using PyMuPDF (`fitz`), `pdf2image`, PyPDF2, Pillow, requests, `openai` SDK (NVIDIA base URL)
- **Testing**: Playwright (frontend QA), standalone Node/Python verification scripts
- **Environment**: Node.js + Python (venv) ecosystem

## 3. Features Implemented

### 3.1. Core Layout & Navigation
- **Sidebar & Dashboard**: A collapsible sidebar navigation system that houses links to various areas of the VLE. The main dashboard displays the available courses.
- **Dark Mode**: Fully integrated dark theme UI mimicking modern software platforms.
- **Global Search Bar**: Upgraded the `Navbar` with a premium glassmorphic search input featuring a neon glow focus state, micro-interactions, and `searchTerm` state management for future content filtering.

### 3.2. Course Pages (A-Level Physics Route)
- **Top Information Block**: Features a welcome banner, quick links, and a summary of exam board details and learning hours.
- **Announcements Section**: A designated area for general course announcements.
- **Topic Accordions**: Expandable sections for specific syllabus topics (e.g., "Mechanics", "Waves and Particle Nature of Light").
- **Learning Content**: Inside the accordions, placeholder structures exist for:
  - Discussion boards
  - Video lessons (iFrame embeds)
  - Quizzes and Past Paper tasks
  - Study resources (styled using Lucide icons)

### 3.3. Authentication & Backend Setup
- **Supabase Integration**: Connected the frontend to a Supabase backend project.
- **Database Schema**: Designed a comprehensive relational database schema to manage user profiles, access levels, hierarchical course content (modules, lessons, quizzes), and student progress tracking.
- **Security**: Configured strict security rules and generated necessary client files for communication.
- **Login/Signup Page**: Scaffolded a custom authentication UI that matches the dark aesthetic of the site. It features deep dark mode styling, a glassmorphic primary container, glowing neon edge borders upon input focus, and GSAP entrance animations.
- **Micro-interactions**: Added responsive `lucide-react` icons that cycle their color state based on focus, and dynamic GSAP error-shake animations when authentication fails.
- **Focus Mode**: Structured advanced routing in `App.jsx` to strip away the Navbar and Footer to eliminate cognitive friction when on the `/auth` route.
- **Password Recovery**: Implemented a complete "Forgot Password" flow within `Auth.jsx` utilizing `supabase.auth.resetPasswordForEmail`, and built a dedicated `UpdatePassword.jsx` route to securely override the password.
- **Environment Variables**: API keys (e.g., `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`) are securely stored in a `.env.local` file.

### 3.4. Legacy Backend Architecture
- **Initial Setup**: Initially designed a 6-tier schema (`courses -> chapters -> topics -> subtopics...`). This was later dropped to reduce technical debt in favor of a simpler hierarchy.
- **Event Trigger Confirmed**: The Supabase Authentication trigger was manually tested and successfully auto-generates new rows in the `profiles` table with the default 'Free' access tier upon user sign-up.
- **Safe Storage**: The master SQL architecture script was archived locally as `Alsini_Physics_Schema_V1.sql`.

### 3.5. SaveMyExams Schema Migration & Security Rollout
- **Unified Schema Deployment**: Migrated to a highly scalable hierarchy mimicking SaveMyExams, modeling the Edexcel IGCSE syllabus structure with a corrected terminology mapping: `units -> chapters -> specification_points -> activities/resources/questions`.
- **Data Seeding Completed**: Successfully parsed an SOW mapping and bulk-inserted the entire Edexcel curriculum data into the unified database schema via direct, chunked SQL migrations, accurately preserving referential integrity and circumventing duplicative key constraints.
- **Row Level Security (RLS) Enforcement**: Enforced strict RLS policies on all core curriculum tables. Explicit `SELECT` policies authorize only `authenticated` users, mathematically blocking anonymous access (verified via isolated NodeJS script `test_rls.js`).
- **Frontend Authentication Audit**: Completed a formal security review of `Auth.jsx`. Confirmed safe default error handling, secure token persistence via `@supabase/supabase-js`, and passive mitigation against XSS/CSRF threats.
- **Quality Gate Approved**: The Security Architect provided official, formal system sign-off verifying that backend security is production-ready for frontend integration.

### 3.6. EDU-VLE Dashboard Integration (Phase 2 Complete)
- **Master Layout**: Constructed `VLEDashboard.jsx` as a fluid desktop-style layout utilizing a premium, deep-dark immersive aesthetic (`#050505` backgrounds, `#0A0A0A` cards, and translucent `white/5` glassmorphic borders) calibrated to reduce eye strain.
- **Platform Rebranding**: Successfully rebranded the core application interface and visual identity to **EDU-VLE**.
- **Dynamic Curriculum Sidebar**: Built `Sidebar.jsx` with asynchronous wiring directly to Supabase. It natively parses the unified schema and is configured to sort syllabus components chronologically to maintain referential parity.
- **Triple Science Filtering**: Developed a sleek, high-tech boolean toggle switch to intuitively filter out `is_physics_only = true` specification points, seamlessly rendering targeted curriculum pathways on demand.

### 3.7. Interactive AI Tutor & Backend Integration (Phase 3 & 4 Complete)
- **Frontend Chat UI**: Built `InteractiveTutor.jsx`, a responsive split-screen interface featuring a glassmorphic document viewer and a dedicated, scrollable AI chat panel matching the EDU-VLE deep-dark aesthetic.
- **Node.js Express Backend**: Designed and deployed a secure custom backend server (`server.js`) to act as a bridge and handle state.
- **Gemini AI Integration**: Secured the Gemini API key via environment variables and configured the Gemini 2.5 Flash model with a custom overarching Socratic Physics Tutor persona.
- **Full End-to-End Wiring**: Successfully connected the React frontend directly to the new Node.js `/api/chat` endpoint. The AI Tutor is now fully alive, communicating, and safely handling user histories without client-side API exposure.

### 3.8. UI Overhaul (Phase 5 Complete)
- **Collapsible Sidebar**: Implemented a responsive state-driven toggle for the left navigation panel (`Sidebar.jsx`). When closed, it visually slides off screen and fully releases its flexbox space, allowing the document viewer to expand dynamically. Added a floating `Menu` toggle button for smooth interaction.
- **Sliding AI Tutor Drawer**: Refactored the AI Chat interface from a rigid split-screen into an absolute positioned drawer anchored to the right. Includes a stylized floating "Ask Tutor" action button with a neon aesthetic to trigger entry, maximizing main reading space while preserving immediate access to the AI.

### 3.9. Agentic UI Copilot Integration (Phase 6 Complete)
- **State-Lifted Navigation**: Refactored the dashboard to centrally manage `activeTab` states (`Lesson`, `Worksheet`, `Simulation`, `Quiz`), passing them down to the `InteractiveTutor` for synchronized rendering.
- **AI Prompt Engineering**: Injected specialized system instructions into the backend (`server.js`), conditioning the Gemini model to output hidden tags (e.g., `[SWITCH_TAB: Quiz]`) whenever educational resources are invoked by the student.
- **Frontend Regex Interceptor**: Built a message parser within `InteractiveTutor.jsx` that intercepts incoming AI responses, stealthily stripping the `[SWITCH_TAB]` tags before they reach the user. It then programmatically triggers the master dashboard state, resulting in a highly agentic interface that seamlessly navigates the UI on the student's behalf.
- **Dynamic Tab Header**: Constructed a premium glassmorphic title and tab row inside the Document Viewer that syncs live with the active tab state to visually present the AI's capability.

### 3.10. Dynamic Worksheet Rendering & Automated Testing
- **Supabase Integration**: Enabled the 'Worksheet' tab in the VLE Dashboard to dynamically fetch and display educational content from the Supabase `resources` table based on the active `specification_point_id`.
- **Markdown UI**: Updated the UI to intelligently render retrieved markdown content or display a beautifully styled empty state when no data is found.
- **Playwright QA Pipeline**: Integrated Playwright into the frontend environment. Created robust test scripts that handle asynchronous network requests to verify that Supabase data is correctly fetched and rendered.

### 3.11. Automated PDF Ingestion Pipeline
- **Hybrid AI Extraction**: Developed standalone ingestion scripts (including `master_ingestion.py` and Node.js equivalents) to automate the processing of Edexcel PDF materials.
- **Vision-Based Processing**: Utilized tools like `pdf2image`, `PyPDF2`, and advanced AI models (Gemini API, NVIDIA NIM endpoints with Llama 3.2 90B Vision and Nemotron 70B) to extract complex physics content and structure it into an OpenKB JSON graph.
- **Database Synchronization**: Built logic to connect to Supabase (using service role keys) and automatically map, format, and push the parsed JSON data into the `resources` table.
- **Secure Configuration**: Updated backend environment variables (`backend/.env`) with `NVIDIA_API_KEY` to enable seamless integration with NVIDIA-hosted models.

### 3.12. Hybrid Document Viewer (OpenKB Integration)
- **Hybrid Architecture**: Built `HybridDocumentViewer.jsx` to dynamically fetch and display OpenKB JSON data from the Supabase `resources` table.
- **Premium UI Toggle**: Implemented a smooth, glassmorphic toggle using Framer Motion (`layoutId`) to switch between a traditional "Document View" (rendering flat Markdown) and a dynamic "Interactive Tutor View".
- **Interactive Knowledge Graph**: Engineered a recursive `<KnowledgeNode />` React component to safely parse and render the deeply-nested OpenKB JSON structure into an interactive, visually stunning tree graph.
- **Dependency Management**: Integrated `framer-motion` into the frontend environment to power advanced micro-interactions and animations.

### 3.13. Agentic Split-Screen UI & Credential Sync
- **Responsive Split-Screen**: Refactored `InteractiveTutor.jsx` to utilize a robust Tailwind Flexbox architecture, establishing a side-by-side layout on desktop where the Hybrid Document Viewer and AI Chat pane dynamically share screen real estate.
- **Mobile Drawer Fallback**: Engineered a graceful degradation strategy for mobile devices, converting the chat interface back into a fixed, sliding overlay drawer to preserve the main reading space.
- **Automated Environment Sync**: Executed an automated credential sync to retrieve the public Supabase `anon` key from the MCP server and securely generated `.env` files in the frontend root, ensuring seamless local data fetching for the newly integrated OpenKB components.

### 3.14. Supabase MCP & Development Environment Hardening
- **Local & Remote MCP Architecture**: Configured a dual MCP (Model Context Protocol) setup. A custom Python-based local MCP server handles specialized database queries (like `resources` search), while the official Supabase Remote MCP (SSE) provides broad administrative capabilities. Documented the entire configuration across major IDEs (Cursor, VS Code, Claude Desktop) in `mcp_configuration_for_supabase.md`.
- **Git Security & Ignore Rules**: Audited and tightened `.gitignore` rules to prevent accidental commits of sensitive environment variables, IDE settings (`.understand-anything`), python environments (`python_interpreter/`, `__pycache__/`), and large scratch binaries. Set up local Git user configuration to standardize project commits.

### 3.15. Visual Asset Infrastructure (Milestone 1 — Session 2 Complete)
- **`resource_assets` Table**: Added a normalized 15-column table with UUID PK, FK to `resources(id)` (`ON DELETE CASCADE`), JSONB `bounding_box`/`metadata`, 4 B-Tree indexes, and RLS (public read, authenticated write). Migration: `migrations/mig_5_resource_assets.sql`.
- **Supabase Storage Bucket**: Created a public `resource-assets` bucket (10 MB limit) hosting uploaded PNG assets with permanent CDN URLs — no auth required for GET.
- **Extraction Pipeline**: Built a `backend/pipeline/` package (`asset_extractor.py`, `storage_uploader.py`, `run_asset_pipeline.py`) that uses PyMuPDF to extract embedded raster images, classify them (graph, plotting_grid, figure, etc.), verify content, and upload to Storage. Validated against the Golden Dataset (IGCSE Movement & Position worksheet — graph + plotting grid extracted, uploaded, verified).
- **Asset API Endpoints** (FastAPI): `GET /api/resources/{resource_id}/assets` and `GET /api/resources/{resource_id}/assets/{asset_type}` expose stored visual assets to the frontend.
- **Linked Question Resolver**: The resource detail / asset flow can resolve which question an asset belongs to via the semantic JSON relationship map.
- **`content_markdown` Column**: Added nullable `content_markdown` to `resources` for future flat-markdown rendering.

### 3.16. Hybrid Retrieval Foundation (Milestone 2 — Session 3 Complete)
- **`resource_chunks` Table**: Added a table with a `vector(1024)` embedding column, FK to `resources`, HNSW index (`vector_cosine_ops`, `m=16`, `ef_construction=200`), and RLS. Migration: `migrations/mig_6_resource_chunks.sql`.
- **`match_resource_chunks` RPC**: Postgres function performing cosine-similarity search with optional `filter_resource_id`, returning ranked chunks plus `similarity` scores. Migration: `migrations/mig_7_match_function.sql`.
- **Embedding Pipeline**: `backend/pipeline/embedding_pipeline.py` chunks OpenKB semantic JSON by node type (concept/formula/definition/relation), embeds via NVIDIA `nv-embedqa-e5-v5`, and stores in `resource_chunks` (idempotent — deletes before re-embedding).
- **Search Endpoints** (FastAPI): `POST /api/search` (pure semantic vector search) and `POST /api/search/hybrid` (combined relational + vector search with filter, merge, dedup, and +0.1 relevance boost for cross-matches).
- **Ingestion Integration**: `master_ingestion.py` now auto-runs the embedding pipeline after the semantic JSON push (non-fatal if NVIDIA API is unavailable).
- **Verified**: Golden Dataset (21 chunks embedded); "How does velocity relate to displacement?" correctly returned velocity/displacement chunks (similarity 0.34–0.50).

### 3.17. Agentic Search Panel & Document Viewer Integration
- **`SearchPanel.jsx`**: New frontend component exposing hybrid retrieval to the learner. Calls `POST /api/search/hybrid`, surfaces similarity scores, source resource, page number, and chunk type, with chunk-type filters (All / Concepts / Formulas / Relations / Questions). Clicking a result navigates the viewer to the relevant content.
- **Concept Pop-up**: `HybridDocumentViewer.jsx` gained an interactive `ConceptPopup` that opens a concept's equation, definition, and related concepts on click, with cross-linking between related concept nodes.
- **Rich Content Prioritization**: The Interactive Tutor now prioritizes rich content resources and the document viewer was hardened for concept rendering.

### 3.18. RAG-Enhanced AI Tutor & Backend Unification
- **FastAPI Supplants Express for AI**: The AI Tutor frontend now calls the FastAPI `POST /api/tutor` endpoint (port 8000) instead of the legacy Express `/api/chat`. The Express `server.js` remains for backward compatibility but is no longer the primary chat path.
- **True RAG**: `/api/tutor` embeds the student's question, retrieves the top-N (5) relevant `resource_chunks` via `_retrieve_relevant_chunks`, and injects only those chunks as context — replacing the old behaviour of dumping the entire OpenKB JSON into the system prompt. Retrieval is non-fatal (tutor still answers if retrieval fails).
- **Graded Responses & Sources**: The tutor response model returns cited `sources` (chunk id, concept, page, chunk type, similarity).
- **Question & Grading Endpoints**: `GET /api/question` (resolved from the resource) and `POST /api/grade` (Gemini acting as a strict Edexcel IGCSE examiner, returning marks + explanation) power the `QuizEngine.jsx`.
- **Routing**: A lightweight `evaluate_routing` classifier detects grading/calculation intents to tailor tutor behaviour.

### 3.19. Quiz Engine
- **`QuizEngine.jsx`**: New interactive quiz component that fetches a question for the active resource (`/api/question`) and submits student answers to the Gemini-backed `/api/grade` endpoint, rendering marks awarded and examiner feedback.

## 4. Troubleshooting & Architecture Changes
- **Build Configurations**: Resolved numerous Vite and production build errors to ensure the platform compiles successfully.
- **NPM Package Management**: Addressed missing `package.json` / `ENOENT` errors, restructuring the `frontend` subdirectory properly to run locally.
- **Component Modularity**: Focused on writing clean, modular, and well-commented React components for future scalability.
- **Component Routing**: Fixed an issue causing a blank screen ("white screen of death") by ensuring all global components (`Navbar`, `NoiseOverlay`, `Home`) remained imported correctly inside `App.jsx` during standard routing structure updates.
- **Version Control**: Implemented Git Version Control and optimized repository by excluding dependency folders.
- **Backend Connection Errors**: Debugged network 'Connection error' between frontend and backend by implementing permissive CORS settings for local development, adding X-Ray logging, and improving error handling in `backend/server.js`.

## 5. Next Steps
- **Frontend Asset Rendering**: Wire `resource_assets` into `HybridDocumentViewer`/`SearchPanel` so extracted graphs and plotting grids render inline (the `<img>` rendering gap noted in the forensic investigation).
- **Tutor ↔ Search Unification**: Have the AI Tutor call `/api/search` (RAG) per question rather than the scoped `match_resource_chunks` retrieval, and generalize beyond the single Golden Dataset resource (`TARGET_RESOURCE_ID`).
- **Backend Consolidation**: Unify Express (`server.js`) and FastAPI (`main.py`) behind one port / reverse proxy so the frontend only targets a single API origin.
- **Re-embedding Hook**: Add a trigger to re-run `embedding_pipeline.py` when a `resources.content` row is updated outside `master_ingestion.py`.
- **Interactive Resources**: Develop the dynamic PDF embed components and a toggle to switch between Question Papers and Mark Schemes per `specification_point`.
- **Content Expansion**: Extend the ingestion pipeline across additional chapters and integrate interactive physics simulations into the VLE.
- **Linked Question Population**: Backfill `resource_assets.linked_question_id` by cross-referencing the semantic JSON relationship map.
