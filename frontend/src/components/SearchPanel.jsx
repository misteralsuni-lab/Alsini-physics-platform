import React, { useState, useCallback } from 'react';
import { Search, Loader2, X, FileText, ArrowUpRight } from 'lucide-react';

/**
 * SearchPanel — Exposes hybrid retrieval to the learner.
 *
 * Calls FastAPI /api/search/hybrid and displays:
 *  - relevance indicators (similarity score)
 *  - source resource
 *  - page number (when source_refs.page is present)
 *  - chunk type
 *
 * Clicking a result triggers onNavigate so the parent can scroll
 * HybridDocumentViewer / the PDF to the relevant learning content.
 *
 * Props:
 *  - resourceId: scope the search to the current worksheet resource
 *  - onNavigate(result): callback when the student clicks a result
 */
const SearchPanel = ({ resourceId, onNavigate }) => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [hasSearched, setHasSearched] = useState(false);
  const [filterChunkType, setFilterChunkType] = useState(null); // null = all

  const chunkTypeFilters = [
    { label: 'All', value: null },
    { label: 'Concepts', value: 'concept' },
    { label: 'Formulas', value: 'formula' },
    { label: 'Relations', value: 'relation' },
    { label: 'Questions', value: 'question' },
  ];

  const handleSearch = useCallback(async (e) => {
    e?.preventDefault();
    if (!query.trim()) return;

    setIsLoading(true);
    setError(null);
    setHasSearched(true);

    try {
      const body = {
        query: query.trim(),
        match_count: 10,
      };
      if (resourceId) body.resource_id = resourceId;
      if (filterChunkType) body.chunk_type = filterChunkType;

      const resp = await fetch('http://localhost:8000/api/search/hybrid', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!resp.ok) {
        throw new Error(`Search failed (${resp.status})`);
      }

      const data = await resp.json();
      setResults(data.results || []);
    } catch (err) {
      console.error('[SearchPanel] Error:', err);
      setError(err.message || 'Search failed. Is the backend running?');
      setResults([]);
    } finally {
      setIsLoading(false);
    }
  }, [query, resourceId, filterChunkType]);

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSearch();
    }
  };

  return (
    <div className="flex flex-col h-full bg-[#0A0A0A]/40 border-l border-white/5">
      {/* Header */}
      <div className="p-4 border-b border-white/5">
        <div className="flex items-center gap-2 mb-3">
          <Search className="w-4 h-4 text-emerald-400" />
          <h3 className="text-sm font-drama text-emerald-400 uppercase tracking-wider">
            Knowledge Search
          </h3>
        </div>
        <p className="text-[11px] text-gray-600 mb-3">
          Semantic search across the worksheet's extracted knowledge.
        </p>

        {/* Search input */}
        <div className="relative">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Search concepts, formulas..."
            className="w-full bg-[#111] border border-white/10 rounded-lg py-2.5 pl-3 pr-9 text-gray-200 text-sm focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/20 transition-all placeholder-gray-600"
          />
          {query && (
            <button
              onClick={() => { setQuery(''); setResults([]); setHasSearched(false); }}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-600 hover:text-gray-400 transition-colors"
              aria-label="Clear search"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        {/* Chunk type filters */}
        <div className="flex flex-wrap gap-1.5 mt-2.5">
          {chunkTypeFilters.map((f) => (
            <button
              key={f.label}
              onClick={() => setFilterChunkType(f.value)}
              className={`text-[10px] px-2 py-1 rounded-full border transition-all ${
                filterChunkType === f.value
                  ? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-400'
                  : 'bg-white/5 border-white/10 text-gray-500 hover:border-white/20'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* Results */}
      <div className="flex-1 overflow-y-auto styled-scrollbar p-3 space-y-2">
        {isLoading && (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-5 h-5 text-emerald-500 animate-spin" />
          </div>
        )}

        {error && (
          <div className="p-3 rounded-lg bg-red-500/5 border border-red-500/20 text-red-400/80 text-xs">
            {error}
          </div>
        )}

        {!isLoading && !error && hasSearched && results.length === 0 && (
          <div className="text-center py-8 text-gray-600 text-sm">
            No results found. Try different keywords.
          </div>
        )}

        {!isLoading && !error && results.map((r, i) => {
          const sim = r.similarity || 0;
          const simPct = Math.round(sim * 100);
          const page = r.source_refs?.page || r.page_number;
          const concept = r.source_refs?.concept;
          const isBoosted = r.boosted;

          return (
            <button
              key={r.id || i}
              onClick={() => onNavigate && onNavigate(r)}
              className="w-full text-left p-3 rounded-xl border border-white/10 bg-[#0A0A0A]/60 hover:bg-white/5 hover:border-emerald-500/30 transition-all group"
            >
              {/* Top row: rank + chunk type + similarity bar */}
              <div className="flex items-center gap-2 mb-1.5">
                <span className="text-[10px] text-emerald-500/60 font-mono">#{i + 1}</span>
                <span className="text-[9px] uppercase tracking-widest text-emerald-400/70 font-mono bg-emerald-500/5 px-1.5 py-0.5 rounded">
                  {r.chunk_type}
                </span>
                {isBoosted && (
                  <span className="text-[9px] text-amber-400/70 font-mono">boosted</span>
                )}
                {/* Similarity indicator */}
                <div className="ml-auto flex items-center gap-1.5">
                  <div className="w-12 h-1 rounded-full bg-white/10 overflow-hidden">
                    <div
                      className={`h-full rounded-full ${simPct > 60 ? 'bg-emerald-500/60' : simPct > 40 ? 'bg-yellow-500/50' : 'bg-gray-600'}`}
                      style={{ width: `${Math.max(simPct, 5)}%` }}
                    />
                  </div>
                  <span className="text-[9px] text-gray-600 font-mono">{simPct}%</span>
                </div>
              </div>

              {/* Chunk text preview */}
              <p className="text-xs text-gray-300 font-light leading-relaxed line-clamp-2">
                {r.chunk_text}
              </p>

              {/* Source / page metadata */}
              <div className="mt-1.5 flex items-center gap-2 flex-wrap">
                {concept && (
                  <span className="text-[10px] text-gray-500 font-mono">
                    {concept}
                  </span>
                )}
                {page != null && (
                  <span className="text-[10px] text-gray-600 flex items-center gap-0.5">
                    <FileText className="w-2.5 h-2.5" /> p.{page}
                  </span>
                )}
                <span className="ml-auto opacity-0 group-hover:opacity-100 transition-opacity text-[10px] text-emerald-400 flex items-center gap-0.5">
                  Open <ArrowUpRight className="w-2.5 h-2.5" />
                </span>
              </div>
            </button>
          );
        })}

        {!isLoading && !error && !hasSearched && (
          <div className="text-center py-12 text-gray-600 text-sm">
            <Search className="w-8 h-8 mx-auto mb-3 opacity-30" />
            Search across concepts, formulas, and relationships extracted from the worksheet.
          </div>
        )}
      </div>
    </div>
  );
};

export default SearchPanel;
