import React, { useState, useRef, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { supabase } from '../lib/supabaseClient';
import { Send, FileText, Bot, User, X, ChevronLeft, Loader2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import HybridDocumentViewer from './HybridDocumentViewer';
import QuizEngine from './QuizEngine';

const InteractiveTutor = ({ activeTab = 'Lesson', setActiveTab }) => {
  const { chapterId } = useParams();
  const [messages, setMessages] = useState([
    { id: 1, role: 'ai', text: 'Hello! I am your AI Physics Tutor. How can I help you with this topic?' }
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isTutorOpen, setIsTutorOpen] = useState(false);
  
  // Data Fetching States
  const [specPoints, setSpecPoints] = useState([]);
  const [activeSpecPointId, setActiveSpecPointId] = useState(null);
  const [worksheetResource, setWorksheetResource] = useState(null);
  const [isFetchingResource, setIsFetchingResource] = useState(false);

  const messagesEndRef = useRef(null);

  // Auto-scroll to the bottom when new messages or loading state appears
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  // Fetch Specification Points for the Chapter
  useEffect(() => {
    const fetchSpecPoints = async () => {
      if (!chapterId) return;
      try {
        const { data, error } = await supabase
          .from('specification_points')
          .select('*')
          .eq('chapter_id', chapterId)
          .order('created_at', { ascending: true });
        
        if (error) throw error;
        setSpecPoints(data || []);
        if (data && data.length > 0) {
          setActiveSpecPointId(data[0].id);
        }
      } catch (error) {
        console.error("Failed to fetch specification points:", error);
      }
    };
    fetchSpecPoints();
  }, [chapterId]);

  // Fetch Resource when Worksheet Tab is active
  useEffect(() => {
    const fetchResource = async () => {
      if (activeTab === 'Worksheet' && activeSpecPointId) {
        setIsFetchingResource(true);
        try {
          const { data, error } = await supabase
            .from('resources')
            .select('*')
            .eq('specification_point_id', activeSpecPointId)
            .limit(1);

          if (error) throw error;
          
          if (data && data.length > 0) {
            setWorksheetResource(data[0]);
          } else {
            setWorksheetResource(null);
          }
        } catch (error) {
          console.error("Failed to fetch worksheet resource:", error);
          setWorksheetResource(null);
        } finally {
          setIsFetchingResource(false);
        }
      }
    };
    
    fetchResource();
  }, [activeTab, activeSpecPointId]);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!inputValue.trim() || isLoading) return;

    const userMessageText = inputValue;
    
    // 1. Add user message to UI
    const newUserMsg = { id: Date.now(), role: 'user', text: userMessageText };
    setMessages((prev) => [...prev, newUserMsg]);
    setInputValue('');
    setIsLoading(true);

    // 2. Format history for Backend
    // Backend API requires history with role and content.
    // We filter out the initial local ai greeting (id: 1) before sending.
    const formattedHistory = messages
      .filter(msg => msg.id !== 1)
      .map(msg => ({
        role: msg.role === 'ai' ? 'model' : 'user',
        content: msg.text
      }));

    try {
      // 3. Make real fetch call to the new FastAPI backend
      const response = await fetch('http://localhost:8000/api/tutor', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          history: formattedHistory,
          student_prompt: userMessageText
        })
      });

      if (!response.ok) {
        throw new Error('Network response was not ok');
      }

      const data = await response.json();

      let aiText = data.response || '';
      const modelUsed = data.model_used || 'Unknown Model';
      
      console.log(`[Semantic Router] Routed to: ${modelUsed}`);
      
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

      // Append successfully received message
      setMessages((prev) => [
        ...prev,
        { id: Date.now() + 1, role: 'ai', text: aiText, modelUsed: modelUsed }
      ]);
      
    } catch (error) {
      console.error('Failed to fetch from backend:', error);
      // 4. Error Handling: add a styled error message
      setMessages((prev) => [
        ...prev,
        { 
          id: Date.now() + 1, 
          role: 'ai', 
          text: 'Connection error: I am currently unable to reach the neural network. Please try again.', 
          isError: true 
        }
      ]);
    } finally {
      setIsLoading(false);
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
           
           {/* Tab Row */}
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
         </div>

         {/* Document Body Area */}
         <div className="flex-1 flex flex-col relative overflow-hidden bg-gradient-to-b from-transparent to-[#050505]/50">
            <div className="flex-1 overflow-y-auto z-10 styled-scrollbar relative">
              {activeTab === 'Worksheet' ? (
                // --- HYBRID DOCUMENT VIEWER INTEGRATION ---
                <div className="w-full h-full">
                  <HybridDocumentViewer />
                </div>
              ) : activeTab === 'Quiz' ? (
                <div className="w-full h-full">
                  <QuizEngine resourceId={worksheetResource?.id} activeSpecPointId={activeSpecPointId} />
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
                         {isLoading ? 'Processing...' : 'Session Active'}
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
                         <div className="prose prose-invert prose-emerald max-w-none prose-p:my-0 prose-pre:my-2 prose-sm font-light">
                           <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                             {msg.text}
                           </ReactMarkdown>
                         </div>
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
                      <div className="p-4 bg-white/[0.03] backdrop-blur-sm border border-white/10 rounded-2xl rounded-tl-sm flex items-center h-[52px]">
                          <div className="flex gap-1.5 items-center">
                              <div className="w-1.5 h-1.5 bg-emerald-500/60 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
                              <div className="w-1.5 h-1.5 bg-emerald-500/60 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
                              <div className="w-1.5 h-1.5 bg-emerald-500/60 rounded-full animate-bounce"></div>
                          </div>
                      </div>
                   </div>
                )}
                <div ref={messagesEndRef} />
              </div>
           </div>

           {/* Chat Input Area */}
           <div className="p-4 bg-[#050505]/80 backdrop-blur-md border-t border-white/5 z-10">
              <form onSubmit={handleSend} className="relative flex items-center">
                 <input
                   type="text"
                   value={inputValue}
                   onChange={(e) => setInputValue(e.target.value)}
                   disabled={isLoading}
                   placeholder={isLoading ? "Tutor is writing..." : "Ask your tutor a question..."}
                   className="w-full bg-[#111] border border-white/10 rounded-xl py-3.5 pl-4 pr-12 text-gray-200 text-sm focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/20 transition-all duration-300 shadow-inner placeholder-gray-600 font-sans disabled:opacity-50 disabled:cursor-not-allowed"
                 />
                 <button
                   type="submit"
                   disabled={!inputValue.trim() || isLoading}
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

