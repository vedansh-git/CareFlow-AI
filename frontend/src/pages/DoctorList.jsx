import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getDoctors } from '../services/api';
import {
  Stethoscope,
  Award,
  Calendar,
  Search,
  ArrowRight,
  Loader2,
  AlertCircle,
  ShieldCheck,
  Star,
  Sparkles,
} from 'lucide-react';

export const DoctorList = () => {
  const [doctors, setDoctors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [specialtyFilter, setSpecialtyFilter] = useState('all');

  useEffect(() => {
    const fetchDoctors = async () => {
      setLoading(true);
      setError('');
      const res = await getDoctors();
      if (res.success) {
        setDoctors(res.data);
      } else {
        setError(res.error || 'Unable to load doctors.');
      }
      setLoading(false);
    };

    fetchDoctors();
  }, []);

  const specialties = ['all', ...Array.from(new Set(doctors.map((d) => d.specialty).filter(Boolean)))];

  const filteredDoctors = doctors.filter((doc) => {
    const matchesQuery =
      doc.full_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      doc.specialty?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      doc.bio?.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesSpecialty = specialtyFilter === 'all' || doc.specialty === specialtyFilter;
    return matchesQuery && matchesSpecialty;
  });

  return (
    <div className="space-y-8">
      {/* Header Banner */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-[#6355d8] via-[#735df2] to-[#8c75ff] p-8 text-white shadow-xl shadow-purple-900/20">
        <div className="absolute top-0 right-0 w-80 h-80 bg-white/10 rounded-full blur-2xl pointer-events-none -mr-20 -mt-20" />
        <div className="relative z-10 space-y-2">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-white/20 text-white backdrop-blur-md">
            <Stethoscope className="w-3.5 h-3.5" /> CareFlow Clinical Specialists
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
            Consult with Medical Specialists
          </h1>
          <p className="text-sm text-purple-100/90 max-w-2xl">
            Browse verified physicians, explore weekly availability schedules, and directly book appointments manually or with our conversational AI agent.
          </p>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-[#181926] border border-white/[0.08] p-4 rounded-3xl flex flex-col md:flex-row gap-3 items-center justify-between shadow-lg">
        <div className="relative w-full md:w-96">
          <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
          <input
            type="text"
            placeholder="Search by doctor name or specialty..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 bg-[#12131d] border border-white/[0.08] focus:border-purple-500/50 rounded-2xl text-xs sm:text-sm text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-purple-500/20 transition-all"
          />
        </div>

        <div className="flex items-center gap-2 w-full md:w-auto overflow-x-auto pb-1 md:pb-0">
          <span className="text-xs text-slate-400 font-semibold shrink-0">Specialty:</span>
          {specialties.map((spec) => (
            <button
              key={spec}
              onClick={() => setSpecialtyFilter(spec)}
              className={`px-3.5 py-1.5 rounded-2xl text-xs font-medium capitalize shrink-0 transition-all cursor-pointer ${
                specialtyFilter === spec
                  ? 'bg-[#6c5dd3] text-white font-bold shadow-md shadow-purple-600/30'
                  : 'bg-[#12131d] text-slate-400 hover:text-slate-200 border border-white/[0.06]'
              }`}
            >
              {spec === 'all' ? 'All Specialties' : spec}
            </button>
          ))}
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="p-4 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center gap-2.5">
          <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
          <span>{error}</span>
        </div>
      )}

      {/* Loading state */}
      {loading ? (
        <div className="py-20 flex flex-col items-center justify-center space-y-3">
          <Loader2 className="w-8 h-8 text-purple-400 animate-spin" />
          <p className="text-xs text-slate-400">Loading specialist profiles...</p>
        </div>
      ) : filteredDoctors.length === 0 ? (
        <div className="bg-[#181926] border border-white/[0.08] rounded-3xl p-12 text-center space-y-3 shadow-lg">
          <Stethoscope className="w-10 h-10 text-slate-500 mx-auto" />
          <h3 className="text-base font-semibold text-slate-200">No doctors found</h3>
          <p className="text-xs text-slate-400 max-w-sm mx-auto">
            No doctors matched your search criteria. Try adjusting your search query or specialty filter.
          </p>
        </div>
      ) : (
        /* Doctor Cards Grid */
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredDoctors.map((doc) => (
            <div
              key={doc.id}
              className="bg-[#181926] border border-white/[0.08] rounded-3xl p-6 flex flex-col justify-between hover:border-purple-500/40 transition-all shadow-lg group hover:shadow-purple-500/5"
            >
              <div className="space-y-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-purple-500 to-indigo-600 flex items-center justify-center font-bold text-white uppercase text-base shadow-md shadow-purple-600/20 group-hover:scale-105 transition-transform">
                    {doc.full_name?.charAt(0) || 'D'}
                  </div>
                  <div className="flex items-center gap-1.5 flex-wrap justify-end">
                    {doc.rating && (
                      <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/10 text-amber-300 border border-amber-500/20 flex items-center gap-0.5">
                        <Star className="w-3 h-3 fill-amber-400 text-amber-400" />
                        {Number(doc.rating).toFixed(1)}
                      </span>
                    )}
                    <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1">
                      <ShieldCheck className="w-3 h-3" /> Active
                    </span>
                  </div>
                </div>

                <div>
                  <h3 className="text-lg font-bold text-white group-hover:text-purple-300 transition-colors">
                    {doc.full_name}
                  </h3>
                  <div className="flex items-center justify-between gap-2 mt-0.5">
                    <p className="text-xs font-semibold text-purple-300">{doc.specialty}</p>
                    {doc.consultation_fee && (
                      <span className="text-xs font-bold text-emerald-400">
                        ${Number(doc.consultation_fee).toFixed(2)}
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-slate-400 mt-1 flex items-center gap-1">
                    <Award className="w-3.5 h-3.5 text-slate-400" />
                    <span>{doc.qualification}</span>
                    {doc.experience_years && <span>• {doc.experience_years}y exp</span>}
                  </p>
                </div>

                <p className="text-xs text-slate-300 line-clamp-2 leading-relaxed">
                  {doc.bio || 'Clinical practitioner dedicated to exceptional patient care and diagnostic excellence.'}
                </p>
              </div>

              <div className="mt-6 pt-5 border-t border-white/[0.06] space-y-2">
                <div className="flex items-center gap-2">
                  <Link
                    to={`/doctors/${doc.id}`}
                    className="flex-1 text-center py-2 px-3 rounded-2xl text-xs font-semibold bg-[#12131d] hover:bg-white/[0.06] text-slate-300 border border-white/[0.06] transition-all"
                  >
                    View Details
                  </Link>
                  <Link
                    to={`/book/${doc.id}`}
                    className="flex-1 inline-flex items-center justify-center gap-1.5 py-2 px-3 rounded-2xl text-xs font-bold text-white bg-[#6c5dd3] hover:bg-[#5e4fc4] transition-all shadow-md shadow-purple-600/25 cursor-pointer"
                  >
                    <Calendar className="w-3.5 h-3.5" /> Book
                  </Link>
                </div>
                <Link
                  to={`/book/${doc.id}?mode=ai`}
                  className="w-full inline-flex items-center justify-center gap-1.5 py-1.5 px-3 rounded-2xl text-[11px] font-semibold text-purple-300 bg-purple-500/10 hover:bg-purple-500/20 border border-purple-500/20 transition-all"
                >
                  <Sparkles className="w-3 h-3 text-purple-400" /> Book with AI Agent
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
