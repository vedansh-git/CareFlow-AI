import React, { useState, useRef, useEffect } from 'react';
import { Send, Loader2, FileText, Info, AlertCircle, Bot, User, Sparkles } from 'lucide-react';
import { chatWithAssistant } from '../services/api';

export const Assistant = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  
  const messagesEndRef = useRef(null);
  
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };
  
  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setInput('');
    setError(null);
    
    // Add user message to UI immediately
    const newMessages = [...messages, { role: 'user', content: userMessage }];
    setMessages(newMessages);
    setIsLoading(true);

    // Prepare history for API (only keep user/assistant roles, exclude system/sources if any)
    const history = messages.map(m => ({
      role: m.role,
      content: m.content
    }));

    try {
      const response = await chatWithAssistant(userMessage, history);
      
      if (response.success) {
        setMessages([
          ...newMessages,
          { 
            role: 'assistant', 
            content: response.data.answer,
            sources: response.data.sources,
            model_attribution: response.data.model_attribution
          }
        ]);
      } else {
        if (response.status === 401) {
           setError("Your session has expired or you are unauthorized. Please log in again.");
        } else {
           setError(response.error || "Failed to get a response from the assistant.");
        }
      }
    } catch (err) {
      setError("An unexpected error occurred.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-10rem)] max-h-[820px] bg-[#181926] border border-white/[0.08] rounded-3xl shadow-2xl overflow-hidden relative">
      
      {/* Header */}
      <div className="p-4 sm:p-5 border-b border-white/[0.06] bg-[#141520]/80 flex items-center justify-between z-10 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-violet-600 via-purple-600 to-indigo-500 flex items-center justify-center shadow-md shadow-purple-600/30 shrink-0">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-slate-100 flex items-center gap-2">
              CareFlow AI Clinical Assistant
              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-purple-500/15 text-purple-300 border border-purple-500/20">
                RAG Grounded
              </span>
            </h2>
            <p className="text-xs text-slate-400">Contextual answers grounded in indexed clinical references</p>
          </div>
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6">
        {messages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-center space-y-4 opacity-75">
            <div className="w-16 h-16 rounded-3xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
              <Bot className="w-8 h-8" />
            </div>
            <div className="space-y-1">
              <p className="text-base font-bold text-slate-200">How can I assist you today?</p>
              <p className="text-xs text-slate-400 max-w-sm">
                Ask clinical and health questions grounded securely in your uploaded documents and medical knowledge base.
              </p>
            </div>
          </div>
        )}
        
        {messages.map((msg, index) => (
          <div key={index} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`flex gap-3 max-w-[85%] sm:max-w-[75%] ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
              
              <div className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 mt-1 ${
                msg.role === 'user' 
                  ? 'bg-purple-600 text-white shadow-md shadow-purple-600/20' 
                  : 'bg-[#232438] text-purple-300 border border-white/[0.08]'
              }`}>
                {msg.role === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
              </div>

              <div className={`space-y-2 ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                <div className={`p-4 rounded-2xl text-sm ${
                  msg.role === 'user' 
                    ? 'bg-[#6c5dd3] text-white rounded-tr-sm shadow-md shadow-purple-600/25' 
                    : 'bg-[#12131d] text-slate-200 border border-white/[0.08] rounded-tl-sm'
                }`}>
                  <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                </div>
                
                {msg.sources && msg.sources.length > 0 && (
                  <div className="bg-[#12131d]/90 border border-white/[0.06] rounded-2xl p-3.5 space-y-2 mt-2 w-full">
                    <div className="flex items-center gap-1.5 text-xs font-semibold text-purple-300">
                      <FileText className="w-3.5 h-3.5" /> Reference Sources Grounded
                    </div>
                    <ul className="space-y-2">
                      {msg.sources.map((source, idx) => (
                        <li key={idx} className="text-xs text-slate-400 bg-[#181926] p-2.5 rounded-xl border border-white/[0.04] line-clamp-2" title={source.content}>
                          <span className="font-semibold text-purple-200">[{source.metadata?.filename || `Doc ${idx+1}`}]</span>: {source.content}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                
                {msg.sources && msg.sources.length === 0 && msg.role === 'assistant' && (
                  <div className="flex items-center gap-1.5 text-xs text-slate-400 pl-1">
                    <Info className="w-3.5 h-3.5" /> No specific documents matched this query.
                  </div>
                )}

                {msg.model_attribution && msg.role === 'assistant' && (
                  <div className="flex items-center gap-1.5 text-[10px] text-slate-400 pl-1 pt-0.5">
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-lg bg-[#12131d] border border-white/[0.06] font-mono text-[10px] text-slate-300">
                      <Bot className="w-3 h-3 text-purple-400" />
                      {msg.model_attribution.provider}: {msg.model_attribution.model}
                      {msg.model_attribution.fallback_used && (
                        <span className="ml-1 text-amber-400 font-sans font-medium">(Fallback active)</span>
                      )}
                    </span>
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
        
        {isLoading && (
          <div className="flex justify-start">
            <div className="flex gap-3 max-w-[85%]">
              <div className="w-8 h-8 rounded-xl bg-[#232438] text-purple-400 border border-white/[0.08] flex items-center justify-center shrink-0 mt-1">
                <Bot className="w-4 h-4" />
              </div>
              <div className="p-4 rounded-2xl bg-[#12131d] border border-white/[0.08] rounded-tl-sm flex items-center gap-2">
                <Loader2 className="w-4 h-4 text-purple-400 animate-spin" />
                <span className="text-xs text-slate-400 font-medium animate-pulse">Consulting clinical references...</span>
              </div>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {/* Error Banner */}
      {error && (
        <div className="px-4 py-2 bg-rose-500/10 border-t border-rose-500/20">
          <div className="flex items-center gap-2 text-xs text-rose-400">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <p>{error}</p>
          </div>
        </div>
      )}

      {/* Input Area */}
      <div className="p-4 border-t border-white/[0.06] bg-[#141520]/80 backdrop-blur-md">
        <form onSubmit={handleSubmit} className="relative">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a medical question based on documents... (Shift+Enter for new line)"
            className="w-full bg-[#12131d] border border-white/[0.08] rounded-2xl pl-4 pr-12 py-3 text-sm text-slate-200 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-purple-500/30 focus:border-purple-500/50 resize-none min-h-[56px] max-h-32"
            rows="1"
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="absolute right-2 bottom-2 p-2 rounded-xl bg-[#6c5dd3] text-white hover:bg-purple-600 disabled:opacity-50 disabled:hover:bg-[#6c5dd3] transition-colors shadow-md shadow-purple-600/20 cursor-pointer"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
        <div className="mt-2 text-center">
          <span className="text-[10px] text-slate-400">CareFlow AI provides answers grounded in uploaded documents. Do not use for actual emergency medical decisions.</span>
        </div>
      </div>
    </div>
  );
};
