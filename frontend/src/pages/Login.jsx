import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Stethoscope, Lock, Mail, AlertCircle, Loader2 } from 'lucide-react';

export const Login = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const { signIn, isConfigured } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from?.pathname || '/';

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!email || !password) {
      setError('Please enter both email and password.');
      return;
    }

    try {
      setLoading(true);
      const result = await signIn({ email, password });
      const userRole = result?.profile?.role;

      if (from === '/' || !from) {
        if (userRole === 'doctor') {
          navigate('/doctor/appointments', { replace: true });
        } else {
          navigate('/', { replace: true });
        }
      } else {
        navigate(from, { replace: true });
      }
    } catch (err) {
      console.error('Login error:', err);
      setError(err.message || 'Invalid email or password. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0c0d14] flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center space-y-3">
        <div className="inline-flex p-3 rounded-2xl bg-gradient-to-tr from-violet-600 via-purple-600 to-indigo-500 text-white font-bold shadow-lg shadow-purple-600/30">
          <Stethoscope className="w-8 h-8" />
        </div>
        <h2 className="text-3xl font-extrabold text-white tracking-tight">
          CareFlow<span className="text-purple-400">.AI</span>
        </h2>
        <p className="text-sm text-slate-400">
          Sign in to access your clinical healthcare workspace
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-[#181926] border border-white/[0.08] py-8 px-4 shadow-2xl rounded-3xl sm:px-10">
          {!isConfigured && (
            <div className="mb-6 p-4 rounded-2xl bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs flex items-start gap-2.5">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-amber-400" />
              <div>
                <strong className="font-semibold block">Supabase Keys Required</strong>
                Please configure <code className="bg-[#12131d] px-1 py-0.5 rounded text-amber-200">VITE_SUPABASE_URL</code> and <code className="bg-[#12131d] px-1 py-0.5 rounded text-amber-200">VITE_SUPABASE_PUBLISHABLE_KEY</code> in <code className="bg-[#12131d] px-1 py-0.5 rounded text-amber-200">frontend/.env</code> to connect live authentication.
              </div>
            </div>
          )}

          {error && (
            <div className="mb-6 p-4 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center gap-2.5">
              <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
              <span>{error}</span>
            </div>
          )}

          <form className="space-y-6" onSubmit={handleSubmit}>
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                Email Address
              </label>
              <div className="relative rounded-2xl shadow-sm">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                  <Mail className="w-4 h-4" />
                </div>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="doctor@hospital.org or patient@example.com"
                  className="block w-full pl-10 pr-4 py-3 bg-[#12131d] border border-white/[0.08] rounded-2xl text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/30 focus:border-purple-500/50 transition-all"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                Password
              </label>
              <div className="relative rounded-2xl shadow-sm">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                  <Lock className="w-4 h-4" />
                </div>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="block w-full pl-10 pr-4 py-3 bg-[#12131d] border border-white/[0.08] rounded-2xl text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/30 focus:border-purple-500/50 transition-all"
                />
              </div>
            </div>

            <div>
              <button
                type="submit"
                disabled={loading}
                className="w-full flex justify-center items-center gap-2 py-3.5 px-4 rounded-2xl shadow-lg shadow-purple-600/30 text-sm font-bold text-white bg-[#6c5dd3] hover:bg-[#5d4ec9] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-purple-500 disabled:opacity-50 transition-all cursor-pointer"
              >
                {loading && <Loader2 className="w-4 h-4 animate-spin" />}
                {loading ? 'Authenticating...' : 'Sign In'}
              </button>
            </div>
          </form>

          <div className="mt-6 text-center text-xs text-slate-400">
            Don't have an account?{' '}
            <Link
              to="/register"
              className="font-bold text-purple-400 hover:text-purple-300 transition-colors"
            >
              Register here
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};
