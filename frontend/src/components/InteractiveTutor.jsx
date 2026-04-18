import React, { useState } from 'react';
import { Send, FileText, Bot, User } from 'lucide-react';

const InteractiveTutor = () => {
  const [messages, setMessages] = useState([
    { id: 1, role: 'ai', text: 'Hello! I am your AI Physics Tutor. How can I help you with this topic?' }
  ]);
  const [inputValue, setInputValue] = useState('');

  const handleSend = (e) => {
    e.preventDefault();
    if (!inputValue.trim()) return;

    // Add user message
    const newUserMsg = { id: Date.now(), role: 'user', text: inputValue };
    setMessages((prev) => [...prev, newUserMsg]);
    setInputValue('');

    // Placeholder AI response simulation
    setTimeout(() => {
      setMessages((prev) => [
        ...prev,
        { id: Date.now() + 1, role: 'ai', text: 'This is a simulated response. In production, this will connect to the OpenKB/MinerU processed context.' }
      ]);
    }, 1000);
  };

  return (
    <div className="h-full w-full flex flex-col xl:flex-row gap-6 p-6">
      {/* Left Pane: Document Viewer (60-70% width on large screens) */}
      <div className="flex-[2] xl:flex-[2.5] bg-[#0A0A0A] border border-white/5 rounded-2xl flex flex-col overflow-hidden relative shadow-[0_8px_30px_rgb(0,0,0,0.5)]">
         {/* Glassmorphic Header */}
         <div className="p-4 border-b border-white/5 bg-[#050505]/80 backdrop-blur-md z-10 flex items-center justify-between">
           <div className="flex items-center gap-3">
             <div className="p-2 bg-blue-500/10 rounded-lg">
               <FileText className="w-5 h-5 text-blue-400" />
             </div>
             <div>
               <h3 className="text-gray-200 font-medium font-drama">Worksheet Preview</h3>
               <p className="text-xs text-gray-500">Awaiting OpenKB Extraction...</p>
             </div>
           </div>
         </div>

         {/* Document Placeholder Body */}
         <div className="flex-1 flex flex-col items-center justify-center p-8 relative">
            {/* Subtle Gradient background effect */}
            <div className="absolute inset-0 bg-gradient-to-b from-transparent to-[#050505]/80 pointer-events-none" />
            
            {/* Glass Box Placeholder */}
            <div className="flex flex-col items-center gap-6 p-10 rounded-2xl border border-white/5 bg-white/[0.02] text-center max-w-md w-full z-10 shadow-lg relative overflow-hidden group">
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
      </div>

      {/* Right Pane: AI Chat Interface */}
      <div className="flex-[1] xl:flex-[1.5] w-full max-w-2xl mx-auto xl:mx-0 xl:max-w-none bg-[#0A0A0A] border border-white/5 rounded-2xl flex flex-col overflow-hidden shadow-[0_8px_30px_rgb(0,0,0,0.5)]">
         {/* Chat Header */}
         <div className="p-4 border-b border-white/5 bg-[#050505]/80 backdrop-blur-md flex items-center gap-3 z-10">
            <div className="p-2 bg-emerald-500/10 rounded-lg shrink-0">
               <Bot className="w-5 h-5 text-emerald-400" />
            </div>
            <div>
               <h3 className="text-gray-200 font-medium font-drama">Interactive Tutor</h3>
               <div className="flex items-center gap-2 mt-0.5">
                  <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse hidden sm:block"></div>
                  <span className="text-[10px] uppercase tracking-wider text-emerald-500/80 font-medium">Session Active</span>
               </div>
            </div>
         </div>

         {/* Message History Container */}
         <div className="flex-1 overflow-y-auto p-4 space-y-6 styled-scrollbar relative">
            <div className="absolute inset-0 bg-[linear-gradient(to_right,#80808012_1px,transparent_1px),linear-gradient(to_bottom,#80808012_1px,transparent_1px)] bg-[size:24px_24px] pointer-events-none opacity-20"></div>
            
            <div className="relative z-10 space-y-6 flex flex-col">
              {messages.map((msg) => (
                <div key={msg.id} className={`flex gap-3 max-w-[90%] sm:max-w-[85%] ${msg.role === 'user' ? 'ml-auto flex-row-reverse' : 'mr-auto'}`}>
                  <div className={`w-8 h-8 rounded-full flex justify-center items-center shrink-0 ${msg.role === 'user' ? 'bg-blue-600/20 border border-blue-500/30 shadow-[0_0_15px_rgba(37,99,235,0.2)]' : 'bg-[#151515] border border-white/10'}`}>
                      {msg.role === 'user' ? <User className="w-4 h-4 text-blue-400" /> : <Bot className="w-4 h-4 text-emerald-400" />}
                  </div>
                  <div className={`p-4 text-sm leading-relaxed shadow-sm font-light tracking-wide
                    ${msg.role === 'user' 
                      ? 'bg-[#111]/80 backdrop-blur-sm border-blue-500/20 border text-blue-50/90 rounded-2xl rounded-tr-sm' 
                      : 'bg-white/[0.03] backdrop-blur-sm border border-white/10 text-gray-300 rounded-2xl rounded-tl-sm'}`}>
                      {msg.text}
                  </div>
                </div>
              ))}
            </div>
         </div>

         {/* Chat Input Area */}
         <div className="p-4 bg-[#050505]/80 backdrop-blur-md border-t border-white/5 z-10">
            <form onSubmit={handleSend} className="relative flex items-center">
               <input
                 type="text"
                 value={inputValue}
                 onChange={(e) => setInputValue(e.target.value)}
                 placeholder="Ask your tutor a question..."
                 className="w-full bg-[#111] border border-white/10 rounded-xl py-3.5 pl-4 pr-12 text-gray-200 text-sm focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/20 transition-all duration-300 shadow-inner placeholder-gray-600 font-sans"
               />
               <button
                 type="submit"
                 disabled={!inputValue.trim()}
                 className={`absolute right-2 p-2 rounded-lg transition-all duration-300 flex items-center justify-center 
                  ${inputValue.trim() 
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
  );
};

export default InteractiveTutor;
