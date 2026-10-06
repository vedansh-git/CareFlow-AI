import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Stethoscope, User, Mail, Lock, AlertCircle, Loader2, CheckCircle2, ShieldCheck } from 'lucide-react';

export const Register = () => {
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [role, setRole] = useState('patient'); // 'patient' | 'doctor'
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  const [loading, setLoading] = useState(false);

  const { signUp, isConfigured } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccessMsg('');

    if (!fullName.trim() || !email.trim() || !password || !confirmPassword) {
      setError('Please fill in all required fields.');
      return;
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    if (password.length < 6) {
      setError('Password must be at least 6 characters long.');
      return;
    }

    try {
      setLoading(true);
      const data = await signUp({
        email,
        password,
        fullName: fullName.trim(),
        role,
      });

      if (data?.session) {
        if (role === 'doctor') {
          navigate('/doctor/appointments', { replace: true });
        } else {
          navigate('/', { replace: true });
        }
      } else {
        setSuccessMsg(
          `Registration successful as ${role === 'doctor' ? 'Doctor' : 'Patient'}! If confirmation is required, please check your email, or sign in below.`
        );
        setTimeout(() => navigate('/login'), 2500);
      }
    } catch (err) {
      console.error('Registration error:', err);
      setError(err.message || 'Registration failed. Please check your details and try again.');
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
          Create CareFlow<span className="text-purple-400">.AI</span> Account
        </h2>
        <p className="text-sm text-slate-400">
          Select your account type to access personalized healthcare workflows
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-lg">
        <div className="bg-[#181926] border border-white/[0.08] py-8 px-4 shadow-2xl rounded-3xl sm:px-10">
          {!isConfigured && (
            <div className="mb-6 p-4 rounded-2xl bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs flex items-start gap-2.5">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-amber-400" />
              <div>
                <strong className="font-semibold block">Supabase Keys Required</strong>
                Please configure <code className="bg-[#12131d] px-1 py-0.5 rounded text-amber-200">VITE_SUPABASE_URL</code> and <code className="bg-[#12131d] px-1 py-0.5 rounded text-amber-200">VITE_SUPABASE_PUBLISHABLE_KEY</code> in <code className="bg-[#12131d] px-1 py-0.5 rounded text-amber-200">frontend/.env</code> to connect live registration.
              </div>
            </div>
          )}

          {error && (
            <div className="mb-6 p-4 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center gap-2.5">
              <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
              <span>{error}</span>
            </div>
          )}

          {successMsg && (
            <div className="mb-6 p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs flex items-center gap-2.5">
              <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400" />
              <span>{successMsg}</span>
            </div>
          )}

          <form className="space-y-5" onSubmit={handleSubmit}>
            {/* Account Role Selection */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                I am registering as:
              </label>
              <div className="grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => setRole('patient')}
                  className={`flex flex-col items-center gap-2 p-3.5 rounded-2xl border transition-all text-left cursor-pointer ${
                    role === 'patient'
                      ? 'bg-purple-500/15 border-purple-500/50 text-white shadow-lg shadow-purple-600/20 ring-1 ring-purple-500'
                      : 'bg-[#12131d] border-white/[0.08] text-slate-400 hover:border-slate-600 hover:text-slate-300'
                  }`}
                >
                  <div
                    className={`p-2 rounded-xl ${
                      role === 'patient'
                        ? 'bg-[#6c5dd3] text-white'
                        : 'bg-white/[0.05] text-slate-400'
                    }`}
                  >
                    <User className="w-5 h-5" />
                  </div>
                  <div className="text-center">
                    <span className="font-bold text-sm block">Patient</span>
                    <span className="text-[11px] text-slate-400 block leading-tight mt-0.5">
                      Book consults &amp; AI care
                    </span>
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => setRole('doctor')}
                  className={`flex flex-col items-center gap-2 p-3.5 rounded-2xl border transition-all text-left cursor-pointer ${
                    role === 'doctor'
                      ? 'bg-purple-500/15 border-purple-500/50 text-white shadow-lg shadow-purple-600/20 ring-1 ring-purple-500'
                      : 'bg-[#12131d] border-white/[0.08] text-slate-400 hover:border-slate-600 hover:text-slate-300'
                  }`}
                >
                  <div
                    className={`p-2 rounded-xl ${
                      role === 'doctor'
                        ? 'bg-[#6c5dd3] text-white'
                        : 'bg-white/[0.05] text-slate-400'
                    }`}
                  >
                    <Stethoscope className="w-5 h-5" />
                  </div>
                  <div className="text-center">
                    <span className="font-bold text-sm block">Doctor</span>
                    <span className="text-[11px] text-slate-400 block leading-tight mt-0.5">
                      Doctor Portal &amp; SOAP Notes
                    </span>
                  </div>
                </button>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                Full Name
              </label>
              <div className="relative rounded-2xl shadow-sm">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                  <User className="w-4 h-4" />
                </div>
                <input
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder={role === 'doctor' ? 'e.g. Dr. Eleanor Vance' : 'e.g. Eleanor Vance'}
                  className="block w-full pl-10 pr-4 py-3 bg-[#12131d] border border-white/[0.08] rounded-2xl text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/30 focus:border-purple-500/50 transition-all"
                />
              </div>
            </div>

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
                  placeholder={role === 'doctor' ? 'doctor@hospital.org' : 'patient@example.com'}
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
                  placeholder="Minimum 6 characters"
                  className="block w-full pl-10 pr-4 py-3 bg-[#12131d] border border-white/[0.08] rounded-2xl text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/30 focus:border-purple-500/50 transition-all"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                Confirm Password
              </label>
              <div className="relative rounded-2xl shadow-sm">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                  <Lock className="w-4 h-4" />
                </div>
                <input
                  type="password"
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Re-enter password"
                  className="block w-full pl-10 pr-4 py-3 bg-[#12131d] border border-white/[0.08] rounded-2xl text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/30 focus:border-purple-500/50 transition-all"
                />
              </div>
            </div>

            <div className="p-3.5 bg-[#12131d] rounded-2xl border border-white/[0.06] text-[11px] text-slate-400 flex items-start gap-2">
              <ShieldCheck className="w-4 h-4 text-purple-400 shrink-0 mt-0.5" />
              <span>
                Registering as a <strong className="text-slate-200">{role === 'doctor' ? 'Doctor' : 'Patient'}</strong>. 
                {role === 'doctor' 
                  ? ' You will have immediate access to the Doctor Portal and Clinical Documentation workspace.' 
                  : ' You will be able to find doctors and book consultations.'}
              </span>
            </div>

            <div>
              <button
                type="submit"
                disabled={loading}
                className="w-full flex justify-center items-center gap-2 py-3.5 px-4 rounded-2xl text-sm font-bold text-white bg-[#6c5dd3] hover:bg-[#5d4ec9] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-purple-500 shadow-lg shadow-purple-600/30 disabled:opacity-50 disabled:cursor-not-allowed transition-all cursor-pointer"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Registering Account...
                  </>
                ) : (
                  `Register as ${role === 'doctor' ? 'Doctor' : 'Patient'}`
                )}
              </button>
            </div>
          </form>

          <div className="mt-6 pt-6 border-t border-white/[0.06] text-center">
            <p className="text-xs text-slate-400">
              Already have an account?{' '}
              <Link to="/login" className="font-semibold text-purple-400 hover:text-purple-300 underline">
                Sign in here
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
