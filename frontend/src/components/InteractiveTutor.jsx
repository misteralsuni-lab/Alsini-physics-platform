import React, { useState, useRef, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Bot, Send, Network, FileText, X, Loader2, Search, ChevronLeft, User, ChevronDown, Code2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import HybridDocumentViewer from './HybridDocumentViewer';
import SearchPanel from './SearchPanel';
import QuizEngine from './QuizEngine';
import { supabase } from '../lib/supabaseClient';
import {
  API_BASE,
  authenticatedFetch,
  formatApiError,
  parseApiErrorResponse,
} from '../lib/apiClient';

// Initial greeting — defined at module scope so the useState initializer
// and the chapter-reset effect reference the same stable constant (avoids
// react-hooks/exhaustive-deps warnings and TDZ ordering issues).
const INITIAL_MESSAGE = { id: 1, role: 'ai', text: 'Hello! I am your AI Physics Tutor. How can I help you with this topic?' };

// --- Citation label system ---
// Maps chunk_type → compact prefix. Produces traceable labels like SRC-A12, EQ-03, FIG-04.
const CHUNK_TYPE_PREFIX = {
  concept: 'SRC',
  definition: 'SRC',
  relation: 'SRC',
  formula: 'EQ',
  figure: 'FIG',
  graph: 'FIG',
  table: 'TAB',
  plot: 'FIG',
  plotting_grid: 'TAB',
  question: 'QN',
  page_text: 'TXT',
  metadata: 'META',
};

// Generate a compact citation label from chunk metadata.
// Format: PREFIX-NN (e.g. EQ-03, FIG-04, SRC-A12).
// Uses page (alpha) + sequential index for uniqueness within a resource.
//
// ISSUE 1 (Session 4A.2): For focused visual assets, the backend generates
// a canonical `asset_label` from the verified asset row. The frontend
// MUST prefer that server value over the response-array position so the
// citation matches the verified figure regardless of client-side ordering.
// The frontend no longer invents labels — it only renders what the backend
// returns. For non-asset chunks (concept/formula/etc.), the label is still
// derived locally from chunk_type + page + array index, since those chunks
// come directly from the backend's RAG retrieval and have a stable order.
function citationLabel(src, index) {
  // Server-canonical label for focused assets — never invented by the client.
  if (src.asset_label) return src.asset_label;

  const prefix = CHUNK_TYPE_PREFIX[src.chunk_type] || 'SRC';
  const page = src.page;
  if (page != null) {
    // Encode page as letter (1=A, 2=B, ...) + 2-digit index for compact traceability
    const pageLetter = String.fromCharCode(65 + ((page - 1) % 26));
    const idx = String(index + 1).padStart(2, '0');
    return `${prefix}-${pageLetter}${idx}`;
  }
  // No page — use sequential index only
  return `${prefix}-${String(index + 1).padStart(2, '0')}`;
}

// Expandable citation chip — compact for students, expandable for full traceability.
// Student mode (Task 2): shows only the compact label; on click expands
//   to reveal Resource title · Page · Specification reference. Nothing else.
// Developer mode (Task 2): additionally exposes chunk id, raw similarity,
//   resource id, chunk index, specification_point_id — full provenance per
//   RAG_ARCHITECTURE.md §Developer Mode.
const CitationChip = ({ src, index, devMode }) => {
  const [expanded, setExpanded] = useState(false);
  const label = citationLabel(src, index);

  return (
    <div className="inline-block">
      <button
        onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }}
        aria-expanded={expanded}
        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[#151515] border border-white/10 text-[10px] text-gray-500 font-mono hover:border-emerald-500/30 hover:text-emerald-400 transition-colors"
        title={devMode ? `${src.chunk_type} · similarity: ${(src.similarity || 0).toFixed(4)}` : label}
        aria-label={`Citation ${label}${devMode ? ' (developer mode)' : ''}`}
      >
        <span className="text-emerald-500/60">{label}</span>
        <ChevronDown className={`w-2.5 h-2.5 transition-transform ${expanded ? 'rotate-180' : ''}`} />
      </button>
      {expanded && (
        <div className="absolute mt-1 z-50 p-3 rounded-lg bg-[#0A0A0A] border border-white/10 shadow-xl text-[10px] font-mono space-y-1.5 min-w-[220px]">
          <div className="flex items-center justify-between border-b border-white/5 pb-1.5 mb-1.5">
            <span className="text-emerald-400 font-medium">{label}</span>
            {devMode && src.chunk_type && (
              <span className="text-gray-600 uppercase text-[9px]">{src.chunk_type}</span>
            )}
          </div>
          {/* Student-visible fields only (Task 2): Resource title, page, spec ref */}
          <div className="space-y-1 text-gray-400">
            {src.resource_title && (
              <div><span className="text-gray-600">Resource:</span> <span className="text-gray-300">{src.resource_title}</span></div>
            )}
            <div><span className="text-gray-600">Page:</span> <span className="text-gray-300">{src.page != null ? src.page : '—'}</span></div>
            {src.specification_point_ref && (
              <div><span className="text-gray-600">Spec:</span> <span className="text-gray-300">{src.specification_point_ref}</span></div>
            )}
          </div>
          {devMode && (
            <div className="mt-2 pt-1.5 border-t border-white/5 space-y-1 text-[9px] text-gray-600">
              <div className="text-amber-500/60 uppercase tracking-wider mb-0.5">Developer Mode</div>
              <div><span className="text-gray-700">chunk_id:</span> {src.chunk_id || '—'}</div>
              <div><span className="text-gray-700">chunk_type:</span> {src.chunk_type || '—'}</div>
              <div><span className="text-gray-700">similarity:</span> {src.similarity != null ? src.similarity.toFixed(4) : '—'}</div>
              <div className="truncate"><span className="text-gray-700">resource_id:</span> {src.resource_id || '—'}</div>
              <div><span className="text-gray-700">spec_id:</span> {src.specification_point_id || '—'}</div>
              <div><span className="text-gray-700">chunk_index:</span> {src.chunk_index != null ? src.chunk_index : '—'}</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const InteractiveTutor = ({ activeTab = 'Worksheet', setActiveTab }) => {
  const { chapterId } = useParams();
  const [messages, setMessages] = useState([INITIAL_MESSAGE]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [loadingPhase, setLoadingPhase] = useState(null);
  const [isTutorOpen, setIsTutorOpen] = useState(false);

  // Synchronization focus state (Stage 4: bidirectional sync)
  const [focus, setFocus] = useState(null);

  // Search panel toggle (Stage 5: exposes hybrid retrieval to the learner)
  const [showSearch, setShowSearch] = useState(false);

  // Developer mode — reveals full traceability in citations
  const [devMode, setDevMode] = useState(false);

  // Data Fetching States
  // NOTE: `specPoints` state is intentionally NOT kept — the spec-point
  // dropdown was removed (Session 4A.1 Task 3, per
  // PEDAGOGICAL_ARCHITECTURE.md). Specification points remain internal
  // curriculum references: the first spec point for the chapter is
  // resolved automatically to scope resource fetching, but the list is
  // no longer surfaced as student navigation.
  const [activeSpecPointId, setActiveSpecPointId] = useState(null);
  const [worksheetResource, setWorksheetResource] = useState(null);
  const [isFetchingResource, setIsFetchingResource] = useState(false);

  // Ref for scrolling concept cards into view when focus changes (focus sync)
  const conceptCardRefs = useRef({});

  // AbortController for in-flight resource fetches — cancelled on chapter/resource
  // transitions to prevent stale responses from overwriting newer state.
  const resourceAbortRef = useRef(null);

  // AbortController for in-flight tutor requests — cancelled on chapter change
  // or unmount so stale/aborted requests do not linger or overwrite newer state.
  const tutorAbortRef = useRef(null);

  // Monotonic message ID counter to avoid React key collisions.
  const messageSeqRef = useRef(1);
  const nextMessageId = () => {
    messageSeqRef.current += 1;
    return `${Date.now()}-${messageSeqRef.current}`;
  };

  // Generation counter for tutor requests — each send increments this; when a
  // response arrives, we check it's still the latest generation before applying.
  // This prevents stale tutor responses from a previous chapter from bleeding in.
  const tutorGenRef = useRef(0);

  const messagesEndRef = useRef(null);

  // Auto-scroll to the bottom when new messages or loading state appears
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  useEffect(() => {
    return () => {
      if (tutorAbortRef.current) {
        tutorAbortRef.current.abort();
        tutorAbortRef.current = null;
      }
    };
  }, []);

  // ISSUE 3 (Session 4A.2): Complete state reset on chapter change.
  // Every chapter/resource transition must clear all worksheet-slice state
  // so no information bleeds across chapters: LearningContext, focus,
  // selected asset, search results, citations, active graph, chat history,
  // and pending requests. The AbortController cancels any in-flight resource
  // fetch from the previous chapter. The tutor generation counter invalidates
  // any in-flight tutor request from the previous chapter.
  useEffect(() => {
    // Cancel any in-flight resource fetch from the previous chapter.
    if (resourceAbortRef.current) {
      resourceAbortRef.current.abort();
      resourceAbortRef.current = null;
    }
    // Abort any in-flight tutor fetch and invalidate stale generation.
    if (tutorAbortRef.current) {
      tutorAbortRef.current.abort();
      tutorAbortRef.current = null;
    }
    tutorGenRef.current += 1;

    // Reset all worksheet-scoped state.
    setMessages([INITIAL_MESSAGE]);
    setFocus(null);
    setWorksheetResource(null);
    setIsLoading(false);
    setLoadingPhase(null);
    setShowSearch(false);
    setActiveSpecPointId(null);
    // Reset the concept card scroll refs.
    conceptCardRefs.current = {};
  }, [chapterId]);

  // Fetch Specification Points for the Chapter
  // Resolves the first spec point id to scope resource fetching. The
  // spec points themselves are not surfaced as student navigation
  // (Task 3); they remain internal curriculum references.
  useEffect(() => {
    const fetchSpecPoints = async () => {
      if (!chapterId) return;
      try {
        const { data, error } = await supabase
          .from('specification_points')
          .select('id')
          .eq('chapter_id', chapterId)
          .order('created_at', { ascending: true })
          .limit(1);

        if (error) throw error;
        if (data && data.length > 0) {
          setActiveSpecPointId(data[0].id);
        }
      } catch (error) {
        console.error("Failed to fetch specification points:", error);
      }
    };
    fetchSpecPoints();
  }, [chapterId]);

  // Fetch Resource — pre-loads regardless of active tab so the worksheet
  // is ready immediately when the user clicks the Worksheet tab.
  // Root cause fix: the original guard `activeTab === 'Worksheet'` caused
  // a chicken-and-egg where the resource was never fetched until the user
  // explicitly clicked Worksheet, producing an empty-state flash.
  useEffect(() => {
    const fetchResource = async () => {
      if (!activeSpecPointId) return;

      // Abort any previous in-flight fetch for this same effect (stale
      // spec-point transition). The chapter-change effect already aborts
      // cross-chapter, but this guards same-chapter spec-point transitions.
      if (resourceAbortRef.current) {
        resourceAbortRef.current.abort();
      }
      const controller = new AbortController();
      resourceAbortRef.current = controller;

      // Clear stale resource state immediately so the viewer doesn't
      // render a previous chapter's content while the new one loads.
      setWorksheetResource(null);

      setIsFetchingResource(true);
      try {
        const { data, error } = await supabase
          .from('resources')
          .select('*')
          .eq('specification_point_id', activeSpecPointId)
          .abortSignal(controller.signal);

        // If this fetch was aborted (chapter/spec changed during fetch),
        // do not apply stale results.
        if (controller.signal.aborted) return;

        if (error) throw error;

        if (data && data.length > 0) {
          const isRich = (r) => {
            const c = r.content;
            if (!c || typeof c !== 'object') return false;
            return Boolean(
              c.formulae || c.key_concepts || c.common_mistakes ||
              Object.keys(c).some((k) => /^[0-9]+$/.test(k))
            );
          };
          const rich = data.find(isRich) || data[0];
          setWorksheetResource(rich);
        } else {
          setWorksheetResource(null);
        }
      } catch (error) {
        if (controller.signal.aborted) return;
        console.error("Failed to fetch worksheet resource:", error);
        setWorksheetResource(null);
      } finally {
        if (!controller.signal.aborted) {
          setIsFetchingResource(false);
        }
      }
    };

    fetchResource();

    return () => {
      if (resourceAbortRef.current) {
        resourceAbortRef.current.abort();
      }
    };
  }, [activeSpecPointId]);

  // Focus → scroll to concept card in HybridDocumentViewer
  // Root cause fix for BUG-7: SearchPanel navigation now scrolls HDV
  // to the matching concept card instead of only setting a hidden state.
  useEffect(() => {
    if (focus && focus.concept && conceptCardRefs.current[focus.concept]) {
      conceptCardRefs.current[focus.concept].scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      });
    }
  }, [focus]);

  const handleReauthenticate = async () => {
    try {
      await supabase.auth.signOut();
    } finally {
      window.location.assign('/auth');
    }
  };

  const handleSend = async (e) => {
    e.preventDefault();
    const userMessageText = inputValue.trim();
    if (!userMessageText || isLoading) return;

    // 1. Add user message to UI
    const newUserMsg = { id: nextMessageId(), role: 'user', text: userMessageText };
    setMessages((prev) => [...prev, newUserMsg]);
    setInputValue('');
    setIsLoading(true);
    setLoadingPhase('sending');

    // 2. Format history for Backend (exclude welcome banner and UI error bubbles)
    const formattedHistory = messages
      .filter((msg) => msg.id !== 1 && !msg.isError && typeof msg.text === 'string' && msg.text.trim())
      .map((msg) => ({
        role: msg.role === 'ai' ? 'model' : 'user',
        content: msg.text,
      }));

    // ISSUE 3 (Session 4A.2): Assign a generation counter before the
    // request so we can detect if the chapter changed during the fetch.
    // If the generation is stale when the response arrives, discard it.
    const myGen = ++tutorGenRef.current;

    if (tutorAbortRef.current) {
      tutorAbortRef.current.abort();
    }
    const controller = new AbortController();
    tutorAbortRef.current = controller;

    try {
      // 3. Call FastAPI /api/tutor with RAG-retrieved context + structured
      //    LearningContext (Session 4A.1). The context carries the
      //    focused asset/chunk/page/resource so the tutor can acknowledge
      //    the visible figure and guide from it rather than asking the
      //    student to "describe the graph". See GRAPH_CONTEXT_SYNCHRONIZATION.md.
      // ISSUE 1 (Session 4A.2): The frontend no longer sends
      // `focused_asset_label` — the backend generates canonical citation
      // IDs and returns them in the response. The learning context carries
      // only the asset identity (id, type, page) so the backend can verify
      // the asset and derive its canonical label.
      const parsedPage =
        focus?.page != null && Number.isFinite(Number(focus.page))
          ? Math.trunc(Number(focus.page))
          : null;
      const learningContext = focus ? {
        resource_id: worksheetResource?.id || null,
        chapter_id: chapterId || null,
        focused_chunk: focus.focused_chunk || null,
        focused_asset: focus.asset_id || focus.focused_asset || null,
        focused_asset_type: focus.asset_type || null,
        focused_question: focus.focused_question || null,
        page: parsedPage,
      } : null;

      const response = await authenticatedFetch(`${API_BASE}/api/tutor`, {
        method: 'POST',
        signal: controller.signal,
        onStatusChange: (phase) => {
          if (myGen === tutorGenRef.current) {
            setLoadingPhase(phase);
          }
        },
        body: JSON.stringify({
          student_prompt: userMessageText,
          history: formattedHistory,
          resource_id: worksheetResource?.id || null,
          learning_context: learningContext,
        })
      });

      if (!response.ok) {
        throw await parseApiErrorResponse(response);
      }

      let data;
      try {
        data = await response.json();
      } catch {
        throw new Error('The tutor server returned an unexpected response format.');
      }

      // ISSUE 3: Discard stale responses from a previous chapter/resource.
      // If the generation counter changed during the fetch, a chapter
      // transition occurred — do not apply the stale response.
      if (myGen !== tutorGenRef.current || controller.signal.aborted) return;

      let aiText = data?.response || '';
      const modelUsed = data?.model_used || 'Unknown Model';
      const sources = Array.isArray(data?.sources) ? data.sources : [];

      console.log(`[Semantic Router] Routed to: ${modelUsed}`);
      console.log(`[RAG] Sources: ${sources.length} chunks retrieved`);

      // Intercept navigation tag
      const tabTracker = /\[SWITCH_TAB:\s*(.*?)\]/i;
      const match = aiText.match(tabTracker);

      if (match && match[1]) {
         const newTab = match[1].trim();
         // Strip the tag from the text
         aiText = aiText.replace(match[0], '').trim();

         // Trigger state change
         if (setActiveTab) {
            setActiveTab(newTab);
         }
      }

      // Append successfully received message (with sources)
      setMessages((prev) => [
        ...prev,
        { id: nextMessageId(), role: 'ai', text: aiText, modelUsed: modelUsed, sources: sources }
      ]);

    } catch (error) {
      // ISSUE 3: If the generation changed or request was cancelled, ignore stale error.
      if (myGen !== tutorGenRef.current || error?.isAbort || controller.signal.aborted) return;
      console.error('Tutor request failed:', error?.status ?? error?.code ?? 'unknown');
      const formatted = formatApiError(error);
      // 4. Error Handling: surface status-aware, sanitized feedback via JSX interpolation.
      setMessages((prev) => [
        ...prev,
        {
          id: nextMessageId(),
          role: 'ai',
          text: formatted.message,
          isError: true,
          errorStatus: formatted.status,
          errorCode: formatted.code,
          isAuthError: formatted.isAuthError,
        }
      ]);
    } finally {
      if (tutorAbortRef.current === controller) {
        tutorAbortRef.current = null;
      }
      // ISSUE 3: Only clear loading if this is still the active generation.
      if (myGen === tutorGenRef.current) {
        setIsLoading(false);
        setLoadingPhase(null);
      }
    }
  };

  return (
    <div className="h-full w-full flex p-4 sm:p-6 lg:gap-6 relative overflow-hidden bg-[#050505]">

      {/* Floating Action Button (Ask Tutor) */}
      {!isTutorOpen && (
        <button
          onClick={() => setIsTutorOpen(true)}
          className="absolute top-1/2 -translate-y-1/2 right-0 z-40 flex items-center gap-2 bg-[#0A0A0A] border border-y-white/10 border-l-white/10 border-r-0 p-3 pr-4 rounded-l-2xl shadow-[0_0_20px_rgba(16,185,129,0.2)] text-emerald-400 hover:text-emerald-300 hover:bg-[#111] transition-all group"
          aria-label="Open AI Tutor"
        >
          <Bot className="w-5 h-5 group-hover:scale-110 transition-transform" />
          <span className="font-medium font-sans text-sm tracking-wide hidden sm:inline">Ask Tutor</span>
          <ChevronLeft className="w-4 h-4 ml-1 opacity-50 group-hover:-translate-x-1 transition-all" />
        </button>
      )}

      {/* Main Pane: Left Side (Document/Hybrid Viewer) */}
      <div className={`flex-1 w-full bg-[#0A0A0A] border border-white/5 rounded-2xl flex flex-col overflow-hidden relative shadow-[0_8px_30px_rgb(0,0,0,0.5)] transition-all duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] ${isTutorOpen ? 'lg:mr-0' : ''}`}>
         {/* Glassmorphic Header */}
         <div className="p-4 border-b border-white/5 bg-[#050505]/80 backdrop-blur-md z-10 flex flex-col xl:flex-row xl:items-center justify-between gap-4">
           <div className="flex items-center gap-3">
             <div className="p-2 bg-blue-500/10 rounded-lg shrink-0">
               <FileText className="w-5 h-5 text-blue-400" />
             </div>
             <div>
               <h3 className="text-gray-200 font-medium font-drama">{activeTab} Preview</h3>
               <p className="text-xs text-gray-500">Awaiting OpenKB Extraction...</p>
             </div>
           </div>

           {/* Tab Row + Search Toggle + Dev Mode */}
           <div className="flex items-center gap-2 flex-wrap">
             {/* Specification points are internal curriculum references
                 (PEDAGOGICAL_ARCHITECTURE.md §Curriculum Hierarchy) —
                 they remain in the DB, retrieval, citations, and
                 teacher analytics, but are no longer exposed as the
                 student's primary navigation. The active spec point is
                 still resolved automatically from the chapter's first
                 spec point (see fetchSpecPoints above) for resource
                 scoping. */}
             <div className="flex bg-[#111] border border-white/5 rounded-lg p-1 overflow-x-auto hide-scrollbar">
                {['Lesson', 'Worksheet', 'Simulation', 'Quiz'].map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setActiveTab && setActiveTab(tab)}
                    className={`px-4 py-1.5 text-sm font-medium rounded-md transition-all whitespace-nowrap ${activeTab === tab ? 'bg-[#222] text-white shadow-sm border border-white/10' : 'text-gray-500 hover:text-gray-300'}`}
                  >
                    {tab}
                  </button>
                ))}
             </div>
             {/* Search Panel Toggle — only visible on Worksheet tab */}
             {activeTab === 'Worksheet' && (
               <button
                 onClick={() => setShowSearch(!showSearch)}
                 className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all whitespace-nowrap flex items-center gap-1.5 border ${
                   showSearch
                     ? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-400'
                     : 'bg-[#111] border-white/5 text-gray-500 hover:text-gray-300'
                 }`}
                 title="Toggle knowledge search"
               >
                 <Search className="w-3.5 h-3.5" />
                 Search
               </button>
             )}
             {/* Developer mode toggle — reveals full citation traceability */}
             <button
               onClick={() => setDevMode(!devMode)}
               className={`px-2.5 py-1.5 text-xs font-medium rounded-md transition-all flex items-center gap-1 border ${
                 devMode
                   ? 'bg-amber-500/15 border-amber-500/40 text-amber-400'
                   : 'bg-[#111] border-white/5 text-gray-600 hover:text-gray-400'
               }`}
               title="Toggle developer mode for full citation traceability"
               aria-label="Developer mode toggle"
             >
               <Code2 className="w-3.5 h-3.5" />
             </button>
           </div>
         </div>

         {/* Document Body Area */}
         <div className="flex-1 flex flex-col relative overflow-hidden bg-gradient-to-b from-transparent to-[#050505]/50">
            <div className="flex-1 overflow-y-auto z-10 styled-scrollbar relative">
              {activeTab === 'Worksheet' ? (
                // --- HYBRID DOCUMENT VIEWER + SEARCH PANEL ---
                <div className="flex w-full h-full">
                  <div className={`${showSearch ? 'flex-1' : 'w-full'} h-full overflow-y-auto styled-scrollbar`}>
                    {isFetchingResource && !worksheetResource && (
                      <div className="flex flex-col items-center justify-center h-full gap-3">
                        <Loader2 className="w-8 h-8 text-emerald-500 animate-spin" />
                        <p className="text-gray-500 text-sm">Loading worksheet resource...</p>
                      </div>
                    )}
                    <HybridDocumentViewer
                      resourceId={worksheetResource?.id}
                      focus={focus}
                      onFocus={setFocus}
                      conceptCardRefs={conceptCardRefs}
                    />
                  </div>
                  {showSearch && (
                    <div className="w-80 h-full flex-shrink-0">
                      <SearchPanel
                        resourceId={worksheetResource?.id}
                        onNavigate={(result) => {
                          // Preserve the selected result identity and page so
                          // the next tutor request can ground on the same
                          // chunk rather than only displaying a concept chip.
                          const page = result.source_refs?.page ?? result.page_number ?? null;
                          setFocus({
                            concept: result.source_refs?.concept || null,
                            focused_chunk: result.id || null,
                            page,
                            type: result.chunk_type || 'concept',
                          });
                        }}
                      />
                    </div>
                  )}
                </div>
              ) : activeTab === 'Quiz' ? (
                <div className="w-full h-full">
                  <QuizEngine resourceId={worksheetResource?.id} />
                </div>
              ) : (
                /* Glass Box Placeholder for other tabs */
                <div className="flex flex-col items-center justify-center h-full p-8">
                  <div className="flex flex-col items-center gap-6 p-10 rounded-2xl border border-white/5 bg-white/[0.02] text-center max-w-md w-full shadow-lg relative overflow-hidden group">
                     {/* Shimmer Effect */}
                     <div className="absolute inset-0 -translate-x-[150%] bg-gradient-to-r from-transparent via-white/5 to-transparent skew-x-12 group-hover:animate-[shimmer_2s_infinite]"></div>

                     <FileText className="w-16 h-16 text-gray-700 mx-auto" />
                     <div className="space-y-3 w-full">
                        <div className="h-2 bg-white/5 rounded-full w-3/4 mx-auto"></div>
                        <div className="h-2 bg-white/5 rounded-full w-full mx-auto"></div>
                        <div className="h-2 bg-white/5 rounded-full w-5/6 mx-auto"></div>
                     </div>
                     <p className="text-gray-400 text-sm mt-4 font-light">Document will render here automatically when a dynamic resource is extracted.</p>
                  </div>
                </div>
              )}
            </div>
         </div>
      </div>

      {/* Right Pane: AI Chat Split-Screen / Drawer */}
      <div
        className={`
          fixed inset-y-0 right-0 z-50 w-full sm:w-[450px] p-4 sm:p-6 pl-0
          lg:static lg:p-0 lg:z-10
          transition-all duration-500 ease-[cubic-bezier(0.16,1,0.3,1)]
          ${isTutorOpen
            ? 'translate-x-0 lg:w-[400px] xl:w-[450px] lg:opacity-100'
            : 'translate-x-full lg:w-0 lg:opacity-0 lg:overflow-hidden lg:ml-0'}
        `}
      >
         <div className="h-full w-full bg-[#0A0A0A] border border-white/5 rounded-2xl flex flex-col overflow-hidden shadow-[-10px_0_30px_rgba(0,0,0,0.7)] lg:shadow-[0_8px_30px_rgb(0,0,0,0.5)]">
           {/* Chat Header */}
           <div className="p-4 border-b border-white/5 bg-[#050505]/80 backdrop-blur-md flex items-center justify-between z-10">
              <div className="flex items-center gap-3">
                 <div className="p-2 bg-emerald-500/10 rounded-lg shrink-0">
                    <Bot className="w-5 h-5 text-emerald-400" />
                 </div>
                 <div>
                    <h3 className="text-gray-200 font-medium font-drama">Interactive Tutor</h3>
                    <div className="flex items-center gap-2 mt-0.5">
                       <div className={`w-2 h-2 rounded-full ${isLoading ? 'bg-amber-500 animate-pulse' : 'bg-emerald-500'} shadow-sm`}></div>
                       <span className={`text-[10px] uppercase tracking-wider ${isLoading ? 'text-amber-500' : 'text-emerald-500/80'} font-medium transition-colors`}>
                         {isLoading
                           ? (loadingPhase === 'retrying'
                               ? 'Retrying...'
                               : loadingPhase === 'waking'
                                 ? 'Waking Server...'
                                 : 'Processing...')
                           : 'Session Active'}
                       </span>
                    </div>
                 </div>
              </div>
              <button
                onClick={() => setIsTutorOpen(false)}
                className="p-1.5 text-gray-400 hover:text-white hover:bg-white/5 rounded-lg transition-colors border border-transparent hover:border-white/10"
                aria-label="Close Tutor Drawer"
              >
                <X className="w-5 h-5" />
              </button>
           </div>

           {/* Message History Container */}
           <div className="flex-1 overflow-y-auto p-4 space-y-6 styled-scrollbar relative">
              <div className="absolute inset-0 bg-[linear-gradient(to_right,#80808012_1px,transparent_1px),linear-gradient(to_bottom,#80808012_1px,transparent_1px)] bg-[size:24px_24px] pointer-events-none opacity-20"></div>

              <div className="relative z-10 space-y-6 flex flex-col">
                {messages.map((msg) => (
                   <div key={msg.id} className={`flex gap-3 max-w-[90%] sm:max-w-[85%] ${msg.role === 'user' ? 'ml-auto flex-row-reverse' : 'mr-auto'}`}>
                     <div className={`w-8 h-8 rounded-full flex justify-center items-center shrink-0 ${msg.role === 'user' ? 'bg-blue-600/20 border border-blue-500/30 shadow-[0_0_15px_rgba(37,99,235,0.2)]' : (msg.isError ? 'bg-red-500/10 border border-red-500/30' : 'bg-[#151515] border border-white/10')}`}>
                         {msg.role === 'user' ? <User className="w-4 h-4 text-blue-400" /> : <Bot className={`w-4 h-4 ${msg.isError ? 'text-red-400' : 'text-emerald-400'}`} />}
                     </div>
                     <div className={`p-4 text-sm leading-relaxed shadow-sm font-light tracking-wide relative
                       ${msg.role === 'user'
                         ? 'bg-[#111]/80 backdrop-blur-sm border-blue-500/20 border text-blue-50/90 rounded-2xl rounded-tr-sm'
                         : (msg.isError ? 'bg-red-500/5 backdrop-blur-sm border border-red-500/20 text-red-200 rounded-2xl rounded-tl-sm' : 'bg-white/[0.03] backdrop-blur-sm border border-white/10 text-gray-300 rounded-2xl rounded-tl-sm w-full')}`}>
                         {msg.isError ? (
                           <div role="alert" className="text-sm leading-relaxed font-normal text-red-200 space-y-2">
                             <p className="whitespace-pre-wrap break-words">{msg.text}</p>
                             {msg.isAuthError && (
                               <button
                                 type="button"
                                 onClick={handleReauthenticate}
                                 className="inline-flex items-center px-3 py-1.5 rounded-lg bg-red-500/20 border border-red-400/30 text-xs font-medium text-red-100 hover:bg-red-500/30 transition-colors"
                               >
                                 Sign in again
                               </button>
                             )}
                           </div>
                         ) : (
                           <div className="prose prose-invert prose-emerald max-w-none prose-p:my-0 prose-pre:my-2 prose-sm font-light">
                             <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                               {msg.text}
                             </ReactMarkdown>
                           </div>
                         )}
                         {/* RAG Source Citations — compact, clickable, expandable, traceable */}
                         {msg.sources && msg.sources.length > 0 && (
                           <div className="mt-3 pt-2 border-t border-white/5 flex flex-wrap gap-1.5 relative">
                             {msg.sources.map((src, i) => (
                               <CitationChip key={src.chunk_id || i} src={src} index={i} devMode={devMode} />
                             ))}
                           </div>
                         )}
                         {msg.modelUsed && (
                           <div className="absolute -bottom-3 right-2 bg-[#1a1a1a] border border-white/10 px-2 py-0.5 rounded-full text-[9px] text-gray-500 font-mono flex items-center gap-1 shadow-sm opacity-80 hover:opacity-100 transition-opacity cursor-default">
                              <Bot className="w-2.5 h-2.5" /> {msg.modelUsed.replace('_', ' ')}
                           </div>
                         )}
                     </div>
                   </div>
                ))}

                {/* Typing Indicator */}
                {isLoading && (
                   <div className="flex gap-3 max-w-[90%] sm:max-w-[85%] mr-auto items-end animate-in fade-in zoom-in duration-300">
                      <div className="w-8 h-8 rounded-full flex justify-center items-center shrink-0 bg-[#151515] border border-white/10">
                          <Bot className="w-4 h-4 text-emerald-400" />
                      </div>
                      <div className="p-4 bg-white/[0.03] backdrop-blur-sm border border-white/10 rounded-2xl rounded-tl-sm flex flex-col gap-2 min-h-[52px] justify-center">
                          <div className="flex gap-1.5 items-center">
                              <div className="w-1.5 h-1.5 bg-emerald-500/60 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
                              <div className="w-1.5 h-1.5 bg-emerald-500/60 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
                              <div className="w-1.5 h-1.5 bg-emerald-500/60 rounded-full animate-bounce"></div>
                          </div>
                          {(loadingPhase === 'waking' || loadingPhase === 'retrying') && (
                            <span role="status" aria-live="polite" className="text-xs text-amber-300/80 font-normal">
                              {loadingPhase === 'retrying'
                                ? 'Server is waking up — retrying connection...'
                                : 'Waking up the AI Tutor server (first request may take ~30s)...'}
                            </span>
                          )}
                      </div>
                   </div>
                )}
                <div ref={messagesEndRef} />
              </div>
           </div>

           {/* Chat Input Area */}
           <div className="p-4 bg-[#050505]/80 backdrop-blur-md border-t border-white/5 z-10">
              {/* Sync context chip — shows what the student focused on in
                  the viewer. ISSUE 1 (Session 4A.2): does NOT show a
                  citation ID label — those are canonical and backend-owned.
                  Only the asset type and page (verified viewer metadata)
                  are shown here. Citation IDs appear only in response
                  citation chips, rendered from backend-returned values. */}
              {focus && (
                <div className="mb-2 flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-500/5 border border-emerald-500/20 text-xs">
                  <span className="text-emerald-400/70 font-mono uppercase tracking-wider text-[10px]">Viewing</span>
                  <span className="text-gray-300">
                    {focus.asset_type && `${focus.asset_type}${focus.page != null ? ` · p.${focus.page}` : ''}`}
                    {!focus.asset_type && focus.concept && `Concept: ${focus.concept}`}
                  </span>
                  <button
                    onClick={() => setFocus(null)}
                    className="ml-auto text-gray-500 hover:text-gray-300 transition-colors text-[10px]"
                    aria-label="Clear context"
                  >✕</button>
                </div>
              )}
              <form onSubmit={handleSend} className="relative flex items-center">
                 <input
                   type="text"
                   value={inputValue}
                   onChange={(e) => setInputValue(e.target.value)}
                   disabled={isLoading}
                   placeholder={
                     loadingPhase === 'retrying'
                       ? 'Retrying connection...'
                       : loadingPhase === 'waking'
                         ? 'Waking up tutor server...'
                         : isLoading
                           ? 'Tutor is writing...'
                           : 'Ask your tutor a question...'
                   }
                   className="w-full bg-[#111] border border-white/10 rounded-xl py-3.5 pl-4 pr-12 text-gray-200 text-sm focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/20 transition-all duration-300 shadow-inner placeholder-gray-600 font-sans disabled:opacity-50 disabled:cursor-not-allowed"
                 />
                 <button
                   type="submit"
                   disabled={!inputValue.trim() || isLoading}
                   aria-label="Send question to tutor"
                   className={`absolute right-2 p-2 rounded-lg transition-all duration-300 flex items-center justify-center
                    ${inputValue.trim() && !isLoading
                      ? 'bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30 hover:scale-105'
                      : 'text-gray-600 opacity-50 cursor-not-allowed'}`}
                 >
                   <Send className="w-4 h-4" />
                 </button>
              </form>
              <div className="text-center mt-3">
                 <span className="text-[10px] text-gray-600/80 font-sans block max-w-[250px] mx-auto leading-tight">AI responses are contextual and may not be 100% accurate.</span>
              </div>
           </div>
         </div>
      </div>
    </div>
  );
};

export default InteractiveTutor;
