import React, { useState, useEffect } from 'react';
import { supabase } from '../lib/supabaseClient';
import { motion, AnimatePresence } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import { FileText, Network, Loader2, Maximize2, AlertCircle, X, ArrowUpRight, ImageIcon, ZoomIn } from 'lucide-react';

// --- Premium UI Tokens & Variants ---
const containerVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: { 
    opacity: 1, 
    y: 0,
    transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1], staggerChildren: 0.1 } 
  },
  exit: { opacity: 0, y: -20, transition: { duration: 0.4 } }
};

const itemVariants = {
  hidden: { opacity: 0, y: 15 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: 'easeOut' } }
};

// --- Visual Asset Card ---
const AssetCard = ({ asset, onZoom, onFocus }) => {
  const [isLoaded, setIsLoaded] = useState(false);
  const [hasError, setHasError] = useState(false);
  const [retryCount, setRetryCount] = useState(0);

  const handleRetry = () => {
    setHasError(false);
    setIsLoaded(false);
    setRetryCount((c) => c + 1);
  };

  return (
    <motion.div
      variants={itemVariants}
      className="group relative rounded-2xl border border-white/10 bg-[#0A0A0A]/60 overflow-hidden"
    >
      {/* Asset image */}
      <div
        className="relative flex items-center justify-center bg-white/95 min-h-[200px] cursor-pointer"
        onClick={() => onFocus && onFocus({ type: 'asset', asset_id: asset.id, asset_type: asset.asset_type, page: asset.page_number })}
      >
        {!isLoaded && !hasError && (
          <div className="absolute inset-0 flex items-center justify-center bg-[#0A0A0A]/80">
            <Loader2 className="w-6 h-6 text-emerald-500 animate-spin" />
          </div>
        )}
        {hasError ? (
          <div className="flex flex-col items-center gap-3 p-8 text-gray-500">
            <AlertCircle className="w-6 h-6 text-red-500/60" />
            <span className="text-xs">Failed to load asset</span>
            <button
              onClick={(e) => { e.stopPropagation(); handleRetry(); }}
              className="text-[10px] px-3 py-1 rounded-full bg-white/5 border border-white/10 text-gray-400 hover:border-emerald-500/30 hover:text-emerald-400 transition-colors"
            >
              Retry
            </button>
          </div>
        ) : (
          <img
            key={retryCount}
            src={asset.storage_url}
            alt={asset.caption || `${asset.asset_type} on page ${asset.page_number}`}
            className={`max-w-full h-auto transition-opacity duration-500 ${isLoaded ? 'opacity-100' : 'opacity-0'}`}
            onLoad={() => setIsLoaded(true)}
            onError={() => { setHasError(true); setIsLoaded(true); }}
            loading="lazy"
          />
        )}
      </div>

      {/* Caption bar */}
      <div className="p-4 border-t border-white/5">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <span className="text-[10px] uppercase tracking-widest text-emerald-400/70 font-mono">
              {asset.asset_type}
            </span>
            {asset.linked_question_id && (
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400/80 font-mono">
                {asset.linked_question_id}
              </span>
            )}
            <span className="text-[10px] text-gray-600 font-mono">
              page {asset.page_number}
            </span>
          </div>
          <button
            onClick={() => onZoom(asset)}
            className="opacity-0 group-hover:opacity-100 transition-opacity p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/5 border border-transparent hover:border-white/10"
            aria-label="Zoom asset"
          >
            <ZoomIn className="w-4 h-4" />
          </button>
        </div>
        {asset.caption && (
          <p className="text-sm text-gray-300 font-light leading-relaxed">
            {asset.caption}
          </p>
        )}
        {asset.content_verified && (
          <div className="mt-2 flex items-center gap-1 text-[10px] text-emerald-500/60">
            <div className="w-1.5 h-1.5 rounded-full bg-emerald-500/60" />
            <span>Content verified</span>
          </div>
        )}
      </div>
    </motion.div>
  );
};

// --- Asset Full-screen Zoom Modal ---
const AssetZoomModal = ({ asset, onClose }) => (
  <motion.div
    className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-8 bg-black/80 backdrop-blur-sm"
    initial={{ opacity: 0 }}
    animate={{ opacity: 1 }}
    exit={{ opacity: 0 }}
    onClick={onClose}
  >
    <motion.div
      className="relative max-w-5xl max-h-full flex flex-col bg-[#0A0A0A] border border-white/10 rounded-2xl overflow-hidden shadow-[0_0_50px_rgba(16,185,129,0.15)]"
      initial={{ scale: 0.9, y: 20 }}
      animate={{ scale: 1, y: 0 }}
      exit={{ scale: 0.9, y: 20 }}
      transition={{ type: 'spring', stiffness: 300, damping: 28 }}
      onClick={(e) => e.stopPropagation()}
    >
      <button
        onClick={onClose}
        className="absolute top-4 right-4 z-10 p-1.5 text-gray-500 hover:text-white hover:bg-white/5 rounded-lg transition-colors border border-transparent hover:border-white/10 bg-[#050505]/80"
        aria-label="Close zoom"
      >
        <X className="w-5 h-5" />
      </button>
      <div className="flex-1 flex items-center justify-center bg-white/95 overflow-auto">
        <img
          src={asset.storage_url}
          alt={asset.caption || `${asset.asset_type} on page ${asset.page_number}`}
          className="max-w-full max-h-full h-auto"
        />
      </div>
      {asset.caption && (
        <div className="p-4 border-t border-white/5">
          <p className="text-sm text-gray-300 font-light">{asset.caption}</p>
        </div>
      )}
    </motion.div>
  </motion.div>
);

// --- Concept Pop-up Box ---
const ConceptPopup = ({ block, onClose, onSelectRelated }) => (
  <motion.div
    className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
    initial={{ opacity: 0 }}
    animate={{ opacity: 1 }}
    exit={{ opacity: 0 }}
    onClick={onClose}
  >
    <motion.div
      className="relative w-full max-w-lg max-h-[85vh] overflow-y-auto styled-scrollbar bg-[#0A0A0A] border border-emerald-500/30 rounded-2xl shadow-[0_0_50px_rgba(16,185,129,0.15)] p-6"
      initial={{ scale: 0.9, y: 20 }}
      animate={{ scale: 1, y: 0 }}
      exit={{ scale: 0.9, y: 20 }}
      transition={{ type: 'spring', stiffness: 300, damping: 28 }}
      onClick={(e) => e.stopPropagation()}
    >
      <button
        onClick={onClose}
        className="absolute top-4 right-4 p-1.5 text-gray-500 hover:text-white hover:bg-white/5 rounded-lg transition-colors border border-transparent hover:border-white/10"
        aria-label="Close"
      >
        <X className="w-5 h-5" />
      </button>

      <div className="text-[10px] uppercase tracking-widest text-emerald-400/70 mb-1">Concept</div>
      <h2 className="text-2xl font-drama text-white mb-4 pr-8">{block.concept}</h2>

      {block.formula && (
        <div className="mb-5 p-4 rounded-xl bg-white/[0.03] border border-white/10">
          <div className="text-[10px] uppercase tracking-widest text-gray-500 mb-2">Formula</div>
          <div className="text-gray-100 text-lg leading-relaxed prose prose-invert prose-emerald max-w-none">
            <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
              {block.formula}
            </ReactMarkdown>
          </div>
        </div>
      )}

      <div className="mb-5">
        <div className="text-[10px] uppercase tracking-widest text-gray-500 mb-2">Definition</div>
        <p className="text-gray-300 font-light leading-relaxed">{block.definition}</p>
      </div>

      {block.related_concepts && block.related_concepts.length > 0 && (
        <div>
          <div className="text-[10px] uppercase tracking-widest text-gray-500 mb-2">Related Concepts</div>
          <div className="flex flex-wrap gap-2">
            {block.related_concepts.map((rc) => (
              <button
                key={rc}
                onClick={() => onSelectRelated(rc)}
                className="flex items-center gap-1 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-sm hover:bg-emerald-500/20 hover:border-emerald-500/50 transition-colors"
              >
                {rc} <ArrowUpRight className="w-3.5 h-3.5" />
              </button>
            ))}
          </div>
        </div>
      )}
    </motion.div>
  </motion.div>
);

const HybridDocumentViewer = ({ resourceId, focus, onFocus }) => {
  const [viewMode, setViewMode] = useState('document'); // 'document' | 'interactive'
  const [data, setData] = useState(null);
  const [assets, setAssets] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedIdx, setSelectedIdx] = useState(null);
  const [zoomAsset, setZoomAsset] = useState(null);
  const [pdfUrl, setPdfUrl] = useState(null);

  // Derive the original PDF public URL from the resource ID + Supabase project URL.
  // The bucket 'resource-assets' is public; the PDF was uploaded during Session 3
  // at {resource_id}/original.pdf.
  useEffect(() => {
    if (!resourceId) return;
    const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || 'https://miezybwngeqdyqvvqcrl.supabase.co';
    setPdfUrl(`${supabaseUrl}/storage/v1/object/public/resource-assets/${resourceId}/original.pdf`);
  }, [resourceId]);

  const blocks = React.useMemo(() => {
    const c = data?.content;
    if (!c) return [];
    const arr = Array.isArray(c) ? c : Object.values(c);
    return arr.filter((b) => b && typeof b === 'object' && b.concept);
  }, [data]);

  const conceptToIdx = React.useMemo(() => {
    const m = new Map();
    blocks.forEach((b, i) => m.set(b.concept, i));
    return m;
  }, [blocks]);

  const selectConcept = (name) => {
    const i = conceptToIdx.get(name);
    if (i !== undefined) setSelectedIdx(i);
  };

  useEffect(() => {
    if (!resourceId) {
      setError("No resource selected.");
      setIsLoading(false);
      return;
    }

    const fetchResourceData = async () => {
      setIsLoading(true);
      setError(null);
      try {
        // Fetch resource content AND visual assets in parallel
        const [resourceRes, assetsRes] = await Promise.all([
          supabase
            .from('resources')
            .select('content, title, content_markdown')
            .eq('id', resourceId)
            .single(),
          supabase
            .from('resource_assets')
            .select('id,page_number,asset_type,storage_url,mime_type,width,height,bounding_box,caption,linked_question_id,content_verified,metadata')
            .eq('resource_id', resourceId)
            .order('page_number', { ascending: true }),
        ]);

        if (resourceRes.error) throw resourceRes.error;
        setData(resourceRes.data);

        // Assets may be empty or error if RLS blocks — handle gracefully
        if (assetsRes.error) {
          console.warn("Could not fetch resource_assets:", assetsRes.error.message);
          setAssets([]);
        } else {
          setAssets(assetsRes.data || []);
        }
      } catch (err) {
        console.error("Error fetching resource data:", err);
        setError("Failed to fetch knowledge graph data. Please verify the resource ID.");
      } finally {
        setIsLoading(false);
      }
    };

    fetchResourceData();
  }, [resourceId]);

  return (
    <div className="w-full h-full flex flex-col bg-[#050505] text-gray-100 overflow-hidden relative font-sans">
      {/* Background ambient glow */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-3/4 h-64 bg-emerald-500/5 blur-[120px] pointer-events-none rounded-full" />
      
      {/* Header & Toggle */}
      <div className="flex-none p-6 border-b border-white/5 bg-[#050505]/80 backdrop-blur-xl z-20 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500/20 to-blue-500/20 border border-white/10 flex items-center justify-center shadow-lg">
            <Maximize2 className="w-5 h-5 text-emerald-400" />
          </div>
          <div>
            <h2 className="text-xl font-drama tracking-wide text-gray-100">
              {data?.title || 'OpenKB Interactive Resource'}
            </h2>
            <p className="text-xs text-gray-500 uppercase tracking-widest mt-1">
              Hybrid Architecture Viewer
              {assets.length > 0 && (
                <span className="ml-2 text-emerald-400/50">
                  · {assets.length} visual {assets.length === 1 ? 'asset' : 'assets'}
                </span>
              )}
            </p>
          </div>
        </div>

        {/* Premium Animated Toggle */}
        <div className="relative flex items-center bg-[#0A0A0A] p-1 rounded-full border border-white/10 shadow-inner">
          <button
            onClick={() => setViewMode('document')}
            className={`relative z-10 flex items-center gap-2 px-6 py-2.5 text-sm font-medium rounded-full transition-colors duration-300 ${
              viewMode === 'document' ? 'text-white' : 'text-gray-500 hover:text-gray-300'
            }`}
          >
            <FileText className="w-4 h-4" />
            <span>Document</span>
          </button>
          
          <button
            onClick={() => setViewMode('interactive')}
            className={`relative z-10 flex items-center gap-2 px-6 py-2.5 text-sm font-medium rounded-full transition-colors duration-300 ${
              viewMode === 'interactive' ? 'text-white' : 'text-gray-500 hover:text-gray-300'
            }`}
          >
            <Network className="w-4 h-4" />
            <span>Interactive Tutor</span>
          </button>

          {/* Sliding Pill Background */}
          <motion.div
            layoutId="activeTab"
            className="absolute top-1 bottom-1 w-[calc(50%-4px)] bg-[#1A1A1A] rounded-full border border-white/5 shadow-[0_2px_10px_rgba(0,0,0,0.5)] z-0"
            initial={false}
            animate={{ 
              left: viewMode === 'document' ? '4px' : 'calc(50%)'
            }}
            transition={{ type: "spring", stiffness: 400, damping: 30 }}
          />
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto styled-scrollbar relative p-6 sm:p-10 z-10">
        {isLoading ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-4">
            <Loader2 className="w-10 h-10 text-emerald-500 animate-spin" />
            <p className="text-gray-400 tracking-wider text-sm animate-pulse">Initializing Neural Link...</p>
          </div>
        ) : error ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-center p-6">
            <AlertCircle className="w-12 h-12 text-red-500/80 mb-4" />
            <h3 className="text-xl text-gray-200 mb-2">Connection Error</h3>
            <p className="text-gray-500 max-w-md">{error}</p>
          </div>
        ) : (
          <AnimatePresence mode="wait">
            {viewMode === 'document' ? (
              <motion.div
                key="document"
                variants={containerVariants}
                initial="hidden"
                animate="visible"
                exit="exit"
                className="max-w-5xl mx-auto"
              >
                {/* Mode A: Original PDF (authoritative visual source) */}
                {pdfUrl && (
                  <motion.div variants={itemVariants} className="mb-8">
                    <div className="flex items-center gap-2 mb-4">
                      <FileText className="w-5 h-5 text-emerald-400" />
                      <h3 className="text-lg font-drama text-emerald-400">Original Worksheet</h3>
                      <span className="text-xs text-gray-500 ml-2">authentic PDF</span>
                    </div>
                    <div className="rounded-2xl border border-white/10 overflow-hidden bg-white shadow-[0_4px_30px_rgba(0,0,0,0.6)]">
                      <iframe
                        src={pdfUrl}
                        className="w-full h-[70vh] min-h-[500px] max-h-[900px]"
                        title="Original worksheet PDF"
                        sandbox="allow-scripts allow-same-origin"
                      />
                    </div>
                    {!data?.content_markdown && !data?.content && (
                      <p className="text-xs text-gray-600 mt-2 text-center">
                        Switch to Interactive Knowledge view to explore concepts, formulas, and assets extracted from this document.
                      </p>
                    )}
                  </motion.div>
                )}

                {/* Visual Assets Section (rendered below the PDF, URL-driven from Supabase Storage) */}
                {assets.length > 0 && (
                  <motion.div variants={itemVariants} className="mb-8">
                    <div className="flex items-center gap-2 mb-4">
                      <ImageIcon className="w-5 h-5 text-emerald-400" />
                      <h3 className="text-lg font-drama text-emerald-400">
                        Extracted Assets
                      </h3>
                      <span className="text-xs text-gray-500 ml-2">
                        {assets.length} figures from source PDF
                      </span>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {assets.map((asset) => (
                        <AssetCard
                          key={asset.id}
                          asset={asset}
                          onZoom={setZoomAsset}
                          onFocus={onFocus}
                        />
                      ))}
                    </div>
                  </motion.div>
                )}

                {/* Markdown content (secondary, as a text-rendered interpretation) */}
                {data?.content_markdown && (
                  <div className="prose prose-invert prose-emerald max-w-none mt-6 p-6 rounded-2xl bg-[#0A0A0A]/50 border border-white/5">
                    <div className="text-xs text-gray-500 uppercase tracking-widest mb-4">Text Interpretation</div>
                    <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                      {data.content_markdown}
                    </ReactMarkdown>
                  </div>
                )}

                {/* Gentle fallback if no PDF and no content */}
                {!pdfUrl && !data?.content_markdown && assets.length === 0 && (
                  <div className="p-8 border border-dashed border-white/10 rounded-2xl text-center bg-[#0A0A0A]/50">
                    <FileText className="w-12 h-12 text-gray-600 mx-auto mb-4" />
                    <h3 className="text-gray-300 text-lg mb-2">No content available</h3>
                    <p className="text-gray-500 text-sm">
                      Switch to the Interactive Knowledge view to explore what has been extracted.
                    </p>
                  </div>
                )}
              </motion.div>
            ) : (
              <motion.div
                key="interactive"
                variants={containerVariants}
                initial="hidden"
                animate="visible"
                exit="exit"
                className="max-w-5xl mx-auto"
              >
                <motion.div variants={itemVariants} className="mb-8 p-6 bg-gradient-to-r from-emerald-500/10 to-transparent border-l-2 border-emerald-500 rounded-r-xl">
                  <h3 className="text-lg font-drama text-emerald-400 mb-2 flex items-center gap-2">
                    <Network className="w-5 h-5" />
                    Knowledge Graph Explorer
                  </h3>
                  <p className="text-sm text-gray-400 font-light">
                    Click a concept node to open its equation and properties. Related concepts link to each other.
                  </p>
                </motion.div>

                {/* Linked visual assets (shown in interactive mode too) */}
                {assets.length > 0 && (
                  <motion.div variants={itemVariants} className="mb-8">
                    <div className="flex items-center gap-2 mb-4">
                      <ImageIcon className="w-4 h-4 text-emerald-400/70" />
                      <h4 className="text-sm font-medium text-gray-300 uppercase tracking-wider">
                        Linked Visual Assets
                      </h4>
                    </div>
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                      {assets.map((asset) => (
                        <button
                          key={asset.id}
                          onClick={() => setZoomAsset(asset)}
                          className="group relative rounded-xl border border-white/10 bg-[#0A0A0A]/60 overflow-hidden hover:border-emerald-500/40 transition-all"
                        >
                          <div className="aspect-video flex items-center justify-center bg-white/95">
                            <img
                              src={asset.storage_url}
                              alt={asset.caption || asset.asset_type}
                              className="max-w-full max-h-full h-auto"
                              loading="lazy"
                            />
                          </div>
                          <div className="p-2">
                            <div className="flex items-center gap-1.5">
                              <span className="text-[9px] uppercase text-emerald-400/70 font-mono">
                                {asset.asset_type}
                              </span>
                              {asset.linked_question_id && (
                                <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400/80 font-mono">
                                  {asset.linked_question_id}
                                </span>
                              )}
                            </div>
                          </div>
                        </button>
                      ))}
                    </div>
                  </motion.div>
                )}

                {blocks.length > 0 ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {blocks.map((b, i) => {
                      const isFocused = focus && focus.concept === b.concept;
                      return (
                      <motion.button
                        key={i}
                        variants={itemVariants}
                        onClick={() => {
                          setSelectedIdx(i);
                          if (onFocus) onFocus({ concept: b.concept, block_index: i, type: 'concept' });
                        }}
                        className={`text-left p-5 rounded-2xl border backdrop-blur-md shadow-lg hover:bg-white/5 transition-all group ${
                          isFocused
                            ? 'border-emerald-500/60 bg-emerald-500/5 ring-1 ring-emerald-500/30'
                            : 'border-white/10 bg-[#0A0A0A]/60 hover:border-emerald-500/40'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-emerald-400 font-mono text-sm font-medium tracking-wider uppercase">
                            {b.concept}
                          </span>
                          <ArrowUpRight className="w-4 h-4 text-gray-600 group-hover:text-emerald-400 transition-colors" />
                        </div>
                        <p className="mt-2 text-gray-300 font-light text-sm leading-relaxed line-clamp-2">
                          {b.definition}
                        </p>
                        <div className="mt-3 flex flex-wrap gap-1.5">
                          {(b.related_concepts || []).map((rc) => (
                            <span
                              key={rc}
                              onClick={(e) => {
                                e.stopPropagation();
                                if (onFocus) onFocus({ concept: rc, type: 'concept' });
                              }}
                              className="cursor-pointer text-[10px] px-2 py-0.5 rounded-full bg-white/5 border border-white/10 text-gray-400 hover:border-emerald-500/30 hover:text-emerald-400 transition-colors"
                            >
                              {rc}
                            </span>
                          ))}
                        </div>
                      </motion.button>
                      );
                    })}
                  </div>
                ) : (
                  <div className="text-gray-500 italic p-4 bg-white/5 rounded-xl border border-white/5">
                    No concept data mapped to this resource.
                  </div>
                )}

                <AnimatePresence>
                  {selectedIdx !== null && blocks[selectedIdx] && (
                    <ConceptPopup
                      block={blocks[selectedIdx]}
                      onClose={() => setSelectedIdx(null)}
                      onSelectRelated={selectConcept}
                    />
                  )}
                </AnimatePresence>
              </motion.div>
            )}
          </AnimatePresence>
        )}
      </div>

      {/* Asset Zoom Modal */}
      <AnimatePresence>
        {zoomAsset && (
          <AssetZoomModal asset={zoomAsset} onClose={() => setZoomAsset(null)} />
        )}
      </AnimatePresence>
    </div>
  );
};

export default HybridDocumentViewer;
