import React, { useState, useEffect } from 'react';
import { supabase } from '../lib/supabaseClient';
import { motion, AnimatePresence } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import { FileText, Network, Loader2, Maximize2, AlertCircle } from 'lucide-react';

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

// --- Interactive Node Renderer ---
const KnowledgeNode = ({ label, value, delay = 0 }) => {
  const isObject = typeof value === 'object' && value !== null;
  const [expanded, setExpanded] = useState(false);

  return (
    <motion.div 
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.4, delay: delay * 0.05 }}
      className="mb-4"
    >
      <div 
        className={`p-4 rounded-xl border border-white/10 bg-[#0A0A0A]/60 backdrop-blur-md shadow-lg
          ${isObject ? 'cursor-pointer hover:bg-white/5 hover:border-emerald-500/30' : ''} 
          transition-all duration-300 group`}
        onClick={() => isObject && setExpanded(!expanded)}
      >
        <div className="flex items-center justify-between">
          <span className="text-emerald-400/90 font-mono text-sm font-medium tracking-wider uppercase">
            {label}
          </span>
          {isObject && (
            <motion.div
              animate={{ rotate: expanded ? 180 : 0 }}
              className="w-5 h-5 flex items-center justify-center rounded-full bg-white/5 text-gray-400 group-hover:text-emerald-400"
            >
              ↓
            </motion.div>
          )}
        </div>
        
        {!isObject && (
          <div className="mt-2 text-gray-300 font-light text-sm leading-relaxed">
            {String(value)}
          </div>
        )}
      </div>

      <AnimatePresence>
        {isObject && expanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden ml-6 mt-2 pl-4 border-l-2 border-emerald-500/20"
          >
            {Object.entries(value).map(([k, v], i) => (
              <KnowledgeNode key={k} label={k} value={v} delay={i} />
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
};

const HybridDocumentViewer = () => {
  const [viewMode, setViewMode] = useState('document'); // 'document' | 'interactive'
  const [data, setData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchResourceData = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const { data: resourceData, error: fetchError } = await supabase
          .from('resources')
          .select('content, content_markdown, title')
          .eq('id', '5729d034-a6c7-4f35-b81c-fcac447289c7')
          .single();

        if (fetchError) throw fetchError;
        setData(resourceData);
      } catch (err) {
        console.error("Error fetching OpenKB data:", err);
        setError("Failed to fetch knowledge graph data. Please verify the resource ID.");
      } finally {
        setIsLoading(false);
      }
    };

    fetchResourceData();
  }, []);

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
            <p className="text-xs text-gray-500 uppercase tracking-widest mt-1">Hybrid Architecture Viewer</p>
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
                className="max-w-4xl mx-auto"
              >
                <div className="prose prose-invert prose-emerald max-w-none">
                  {data?.content_markdown ? (
                    <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                      {data.content_markdown}
                    </ReactMarkdown>
                  ) : (
                    <div className="p-8 border border-dashed border-white/10 rounded-2xl text-center bg-[#0A0A0A]/50">
                      <FileText className="w-12 h-12 text-gray-600 mx-auto mb-4" />
                      <h3 className="text-gray-300 text-lg mb-2">Markdown Unvailable</h3>
                      <p className="text-gray-500 text-sm">Switch to the Interactive view to explore the raw JSON data.</p>
                    </div>
                  )}
                </div>
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
                    Interact with the deeply nested OpenKB structure. Click on nodes to expand and collapse relationships.
                  </p>
                </motion.div>
                
                <div className="pl-2">
                  {data?.content ? (
                    <KnowledgeNode label="Root" value={data.content} />
                  ) : (
                    <div className="text-gray-500 italic p-4 bg-white/5 rounded-xl border border-white/5">
                      No JSON content mapped to this resource.
                    </div>
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        )}
      </div>
    </div>
  );
};

export default HybridDocumentViewer;
