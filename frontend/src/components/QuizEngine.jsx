import React, { useState, useEffect } from 'react';
import { supabase } from '../lib/supabaseClient';
import { Send, Lightbulb, CheckCircle, AlertTriangle, Bot, Loader2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
const QuizEngine = ({ resourceId, activeSpecPointId }) => {
  const [questionIndex, setQuestionIndex] = useState(1);
  const [questionText, setQuestionText] = useState("");
  const [maxScore, setMaxScore] = useState(3);
  const [examinerHint, setExaminerHint] = useState("");
  const [isLoadingQuestion, setIsLoadingQuestion] = useState(true);
  
  const [studentAnswer, setStudentAnswer] = useState('');
  const [isGrading, setIsGrading] = useState(false);
  const [correction, setCorrection] = useState(null);
  const [hintVisible, setHintVisible] = useState(false);

  useEffect(() => {
    const fetchQuestion = async () => {
      setIsLoadingQuestion(true);
      try {
        const response = await fetch(`http://localhost:8000/api/question?resource_id=${resourceId || ''}`);
        if (!response.ok) throw new Error('Failed to fetch question');
        const data = await response.json();
        setQuestionIndex(data.question_index);
        setQuestionText(data.question_text);
        setMaxScore(data.max_score);
        setExaminerHint(data.examiner_hint);
      } catch (err) {
        console.error(err);
      } finally {
        setIsLoadingQuestion(false);
      }
    };
    fetchQuestion();
  }, [resourceId]);
  
  const handleHint = () => {
    setHintVisible(true);
  };
  
  const handleSubmit = async () => {
    if (!studentAnswer.trim()) return;
    
    setIsGrading(true);
    setCorrection(null);
    setHintVisible(false);
    
    try {
      // Get current user session
      const { data: { session } } = await supabase.auth.getSession();
      const studentId = session?.user?.id || '00000000-0000-0000-0000-000000000000'; // Fallback if not logged in
      
      const payload = {
        student_id: studentId,
        resource_id: resourceId || "5729d034-a6c7-4f35-b81c-fcac447289c7", // Fallback forces resource
        question_index: questionIndex,
        student_answer: studentAnswer,
        max_score: maxScore,
        question_text: questionText
      };
      
      const response = await fetch('http://localhost:8000/api/grade', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      
      if (!response.ok) {
        throw new Error('Grading failed');
      }
      
      const result = await response.json();
      setCorrection(result);
      
      // Save to database
      if (session?.user?.id) {
        await supabase.from('quiz_attempts').insert([
          {
            student_id: studentId,
            resource_id: payload.resource_id,
            question_index: questionIndex,
            student_answer: studentAnswer,
            score: result.marks_awarded,
            max_score: result.total_marks,
            ai_feedback: result.explanation,
            last_question_index: questionIndex
          }
        ]);
      }
      
    } catch (error) {
      console.error("Error submitting quiz:", error);
      setCorrection({
        marks_awarded: 0,
        total_marks: maxScore,
        explanation: "Error contacting the grading engine. Please try again."
      });
    } finally {
      setIsGrading(false);
    }
  };

  if (isLoadingQuestion) {
    return (
      <div className="flex flex-col items-center justify-center h-full w-full">
        <Loader2 className="w-8 h-8 text-emerald-500 animate-spin mb-4" />
        <p className="text-gray-400 font-light">Loading Examiner Questions...</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full w-full max-w-3xl mx-auto p-4 sm:p-6 text-gray-200">
      <div className="bg-[#111] border border-white/10 rounded-2xl p-6 shadow-lg mb-6 relative overflow-hidden">
        {/* Glow effect */}
        <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-blue-500 via-emerald-500 to-purple-500"></div>
        
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-medium font-drama text-white">Question {questionIndex}</h2>
          <span className="text-xs font-mono bg-white/5 border border-white/10 px-3 py-1 rounded-full text-gray-400">
            [{maxScore} Marks]
          </span>
        </div>
        
        <div className="text-gray-300 mb-6 leading-relaxed text-sm md:text-base markdown-body-custom">
          <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
            {questionText}
          </ReactMarkdown>
        </div>
        
        {hintVisible && examinerHint && (
          <div className="mb-6 p-4 bg-amber-500/10 border border-amber-500/20 rounded-xl flex gap-3 text-amber-200/90 text-sm">
            <Lightbulb className="w-5 h-5 shrink-0 text-amber-400 mt-1" />
            <div className="markdown-body-custom w-full">
              <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                {examinerHint}
              </ReactMarkdown>
            </div>
          </div>
        )}
        
        <div className="space-y-4">
          <label className="block text-sm font-medium text-gray-400">Your Answer</label>
          <textarea
            value={studentAnswer}
            onChange={(e) => setStudentAnswer(e.target.value)}
            disabled={isGrading || correction !== null}
            placeholder="Type your answer or paste GraphDraw JSON coordinates here..."
            className="w-full bg-[#0A0A0A] border border-white/10 rounded-xl p-4 text-gray-200 min-h-[120px] focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/20 transition-all font-mono text-sm disabled:opacity-50"
          />
          
          {!correction && (
            <div className="flex items-center justify-between mt-4">
              <button 
                onClick={handleHint}
                disabled={isGrading}
                className="flex items-center gap-2 text-sm text-gray-400 hover:text-amber-400 transition-colors px-3 py-2"
              >
                <Lightbulb className="w-4 h-4" /> Ask the Examiner (Hint)
              </button>
              
              <button
                onClick={handleSubmit}
                disabled={!studentAnswer.trim() || isGrading}
                className={`flex items-center gap-2 px-6 py-2.5 rounded-xl font-medium transition-all
                  ${!studentAnswer.trim() || isGrading 
                    ? 'bg-emerald-500/10 text-emerald-500/50 cursor-not-allowed' 
                    : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/30 hover:scale-[1.02] shadow-[0_0_15px_rgba(16,185,129,0.15)]'}`}
              >
                {isGrading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" /> 
                    <span>The Examiner is reviewing...</span>
                  </>
                ) : (
                  <>
                    <Send className="w-4 h-4" />
                    <span>Submit for Marking</span>
                  </>
                )}
              </button>
            </div>
          )}
        </div>
      </div>
      
      {/* Correction Card */}
      {correction && (
        <div className="bg-[#111] border border-white/10 rounded-2xl overflow-hidden shadow-[0_8px_30px_rgba(0,0,0,0.5)] animate-in slide-in-from-bottom-4 duration-500">
          <div className="bg-[#050505] p-4 border-b border-white/5 flex items-center justify-between">
            <div className="flex items-center gap-3">
              {correction.marks_awarded === maxScore ? (
                <div className="p-1.5 bg-emerald-500/20 rounded-full">
                  <CheckCircle className="w-5 h-5 text-emerald-400" />
                </div>
              ) : (
                <div className="p-1.5 bg-amber-500/20 rounded-full">
                  <AlertTriangle className="w-5 h-5 text-amber-400" />
                </div>
              )}
              <h3 className="font-medium font-drama text-white">Examiner's Feedback</h3>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xl font-bold font-mono">
                <span className={correction.marks_awarded === maxScore ? "text-emerald-400" : "text-amber-400"}>
                  {correction.marks_awarded}
                </span>
                <span className="text-gray-500">/{correction.total_marks}</span>
              </span>
            </div>
          </div>
          
          <div className="p-6">
            <div className="text-gray-300 leading-relaxed text-sm md:text-base font-light markdown-body-custom">
              <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                {correction.explanation}
              </ReactMarkdown>
            </div>
            
            <div className="mt-6 pt-4 border-t border-white/5 flex justify-between items-center">
              <div className="bg-[#1a1a1a] border border-white/10 px-3 py-1.5 rounded-full text-[11px] text-gray-400 font-mono flex items-center gap-2 w-max cursor-default hover:bg-[#222] transition-colors">
                <Bot className="w-3.5 h-3.5 text-blue-400" />
                <span>Graded by Llama-3.3-70b-instruct</span>
              </div>
              
              <button 
                onClick={() => {
                  setStudentAnswer('');
                  setCorrection(null);
                  setHintVisible(false);
                }}
                className="text-xs font-medium text-emerald-400/80 hover:text-emerald-400 transition-colors"
              >
                Try Again
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default QuizEngine;
