import React from 'react';
import { CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';

export const StatusBadge = ({ type, title, status, details, onRetry }) => {
  const isRunning = status === 'running' || status === 'connected';
  const isChecking = status === 'checking';
  const isError = status === 'error';

  return (
    <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-lg backdrop-blur-sm transition-all hover:border-slate-700">
      <div className="flex items-start justify-between">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            {type} Component
          </span>
          <h3 className="text-lg font-bold text-slate-100 mt-1">{title}</h3>
        </div>

        <div className="flex items-center">
          {isRunning && (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <CheckCircle2 className="w-3.5 h-3.5" />
              Connected / Running
            </span>
          )}
          {isChecking && (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-sky-500/10 text-sky-400 border border-sky-500/20 animate-pulse">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              Checking...
            </span>
          )}
          {isError && (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-rose-500/10 text-rose-400 border border-rose-500/20">
              <AlertCircle className="w-3.5 h-3.5" />
              Not Connected
            </span>
          )}
        </div>
      </div>

      <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-400">
        <div className="truncate max-w-[280px]">
          {details ? (
            <span className="font-mono text-slate-300">{details}</span>
          ) : (
            <span>Status verified locally</span>
          )}
        </div>
        {isError && onRetry && (
          <button
            onClick={onRetry}
            className="text-xs text-sky-400 hover:text-sky-300 underline font-medium cursor-pointer ml-2 shrink-0"
          >
            Retry Connection
          </button>
        )}
      </div>
    </div>
  );
};
