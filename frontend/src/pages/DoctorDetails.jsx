import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getDoctorById, getDoctorAvailability } from '../services/api';
import {
  Stethoscope,
  Award,
  Calendar,
  Clock,
  ArrowLeft,
  Loader2,
  AlertCircle,
  ShieldCheck,
  MapPin,
  Phone,
  DollarSign,
  Star,
  Sparkles,
  MessageSquareQuote,
  Info,
} from 'lucide-react';

export const DoctorDetails = () => {
  const { doctorId } = useParams();

  const [doctor, setDoctor] = useState(null);
  const [availability, setAvailability] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchDetails = async () => {
      setLoading(true);
      setError('');

      const [docRes, availRes] = await Promise.all([
        getDoctorById(doctorId),
        getDoctorAvailability(doctorId),
      ]);

      if (docRes.success) {
        setDoctor(docRes.data);
      } else {
        setError(docRes.error || 'Failed to load doctor profile.');
      }

      if (availRes.success) {
        setAvailability(availRes.data);
      }

      setLoading(false);
    };

    if (doctorId) {
      fetchDetails();
    }
  }, [doctorId]);

  if (loading) {
    return (
      <div className="py-24 flex flex-col items-center justify-center space-y-3">
        <Loader2 className="w-8 h-8 text-purple-400 animate-spin" />
        <p className="text-xs text-slate-400">Loading doctor details...</p>
      </div>
    );
  }

  if (error || !doctor) {
    return (
      <div className="space-y-6">
        <Link
          to="/doctors"
          className="inline-flex items-center gap-2 text-xs font-semibold text-slate-400 hover:text-purple-300"
        >
          <ArrowLeft className="w-4 h-4" /> Back to Doctors
        </Link>
        <div className="p-6 rounded-3xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center gap-3">
          <AlertCircle className="w-5 h-5 shrink-0 text-rose-400" />
          <span>{error || 'Doctor profile not found'}</span>
        </div>
      </div>
    );
  }

  const demoReviews = doctor.demo_reviews || [];

  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      {/* Back button */}
      <Link
        to="/doctors"
        className="inline-flex items-center gap-2 text-xs font-semibold text-slate-400 hover:text-purple-300 transition-colors"
      >
        <ArrowLeft className="w-4 h-4" /> Back to All Specialists
      </Link>

      {/* Main Profile Header */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-[#6355d8] via-[#735df2] to-[#8c75ff] p-8 text-white shadow-xl shadow-purple-900/20">
        <div className="absolute top-0 right-0 w-80 h-80 bg-white/10 rounded-full blur-2xl pointer-events-none -mr-20 -mt-20" />
        
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="flex items-start gap-5">
            <div className="w-16 h-16 rounded-2xl bg-white/15 backdrop-blur-md flex items-center justify-center font-extrabold text-2xl text-white uppercase shadow-lg shrink-0">
              {doctor.full_name?.charAt(0) || 'D'}
            </div>
            <div className="space-y-1.5">
              <div className="flex items-center gap-2 flex-wrap">
                <h1 className="text-2xl sm:text-3xl font-extrabold text-white">
                  {doctor.full_name}
                </h1>
                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-white/20 text-white backdrop-blur-md flex items-center gap-1">
                  <ShieldCheck className="w-3 h-3" /> Active Specialist
                </span>
                {doctor.rating && (
                  <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-400/20 text-amber-200 border border-amber-400/30 flex items-center gap-1">
                    <Star className="w-3 h-3 fill-amber-400 text-amber-400" />
                    {doctor.rating.toFixed(1)} ({doctor.reviews_count || 0} reviews)
                  </span>
                )}
              </div>
              <p className="text-sm font-semibold text-purple-100">{doctor.specialty}</p>
              <p className="text-xs text-purple-100/80 flex items-center gap-1.5 pt-0.5">
                <Award className="w-4 h-4" />
                <span>{doctor.qualification}</span>
                {doctor.experience_years && (
                  <span>• {doctor.experience_years} years experience</span>
                )}
              </p>
            </div>
          </div>

          <div className="flex flex-col sm:flex-row gap-3 shrink-0">
            <Link
              to={`/book/${doctor.id}?mode=ai`}
              className="inline-flex items-center justify-center gap-2 px-5 py-3 rounded-2xl text-xs font-bold text-white bg-white/20 hover:bg-white/30 backdrop-blur-md transition-all shadow-md cursor-pointer"
            >
              <Sparkles className="w-4 h-4 text-purple-200" /> Book with AI Agent
            </Link>
            <Link
              to={`/book/${doctor.id}`}
              className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-2xl text-xs font-bold text-[#6355d8] bg-white hover:bg-purple-50 transition-all shadow-lg cursor-pointer"
            >
              <Calendar className="w-4 h-4" /> Book Manually
            </Link>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Bio & Details */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-[#181926] border border-white/[0.08] rounded-3xl p-6 sm:p-8 space-y-4 shadow-lg">
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <Award className="w-4 h-4 text-purple-400" />
              Physician Biography &amp; Background
            </h2>
            <p className="text-sm text-slate-300 leading-relaxed">
              {doctor.bio || 'Clinical practitioner with advanced specialization dedicated to evidence-based healthcare, compassionate patient consultations, and diagnostic accuracy.'}
            </p>

            <div className="pt-4 border-t border-white/[0.06] grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
              <div className="p-3.5 bg-[#12131d] rounded-2xl border border-white/[0.06] space-y-1">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                  <MapPin className="w-3.5 h-3.5 text-purple-400" /> Clinic Address
                </span>
                <p className="font-medium text-slate-200">{doctor.clinic_address || 'CareFlow Medical Centre, Main Campus'}</p>
              </div>
              <div className="p-3.5 bg-[#12131d] rounded-2xl border border-white/[0.06] space-y-1">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                  <Phone className="w-3.5 h-3.5 text-purple-400" /> Contact Phone
                </span>
                <p className="font-mono text-slate-200">{doctor.contact_phone || '+1-555-0100'}</p>
                <p className="text-[10px] text-slate-400 italic">Demonstration clinical contact</p>
              </div>
              <div className="p-3.5 bg-[#12131d] rounded-2xl border border-white/[0.06] space-y-1">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                  <DollarSign className="w-3.5 h-3.5 text-emerald-400" /> Consultation Fee
                </span>
                <p className="font-bold text-emerald-400 text-sm">
                  ${doctor.consultation_fee ? Number(doctor.consultation_fee).toFixed(2) : '100.00'}
                </p>
              </div>
              <div className="p-3.5 bg-[#12131d] rounded-2xl border border-white/[0.06] space-y-1">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                  <Award className="w-3.5 h-3.5 text-amber-400" /> Clinical Experience
                </span>
                <p className="font-bold text-slate-200 text-sm">
                  {doctor.experience_years || 5}+ Years Practice
                </p>
              </div>
            </div>
          </div>

          {/* Demonstration Reviews */}
          {demoReviews.length > 0 && (
            <div className="bg-[#181926] border border-white/[0.08] rounded-3xl p-6 sm:p-8 space-y-4 shadow-lg">
              <div className="flex items-center justify-between">
                <h2 className="text-base font-bold text-white flex items-center gap-2">
                  <MessageSquareQuote className="w-4 h-4 text-purple-400" />
                  Demonstration Patient Feedback
                </h2>
                <div className="flex items-center gap-1 text-amber-400 text-xs font-bold">
                  <Star className="w-3.5 h-3.5 fill-amber-400" />
                  <span>{doctor.rating ? doctor.rating.toFixed(1) : '5.0'}</span>
                </div>
              </div>

              <div className="space-y-3">
                {demoReviews.map((rev, idx) => (
                  <div
                    key={idx}
                    className="p-4 bg-[#12131d] rounded-2xl border border-white/[0.06] space-y-2"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-slate-200">{rev.reviewer_name}</span>
                      <div className="flex items-center gap-1">
                        {[...Array(rev.rating || 5)].map((_, i) => (
                          <Star key={i} className="w-3 h-3 fill-amber-400 text-amber-400" />
                        ))}
                      </div>
                    </div>
                    <p className="text-xs text-slate-300 italic">"{rev.comment}"</p>
                    <span className="text-[10px] text-slate-400 block">{rev.date}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right column: Weekly Availability schedule */}
        <div className="space-y-6">
          <div className="bg-[#181926] border border-white/[0.08] rounded-3xl p-6 space-y-4 shadow-lg">
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <Clock className="w-4 h-4 text-purple-400" />
              Weekly Consultation Hours
            </h2>
            <p className="text-xs text-slate-400">
              Deterministic 30-minute booking intervals are generated within these hours.
            </p>

            {availability.length === 0 ? (
              <div className="p-4 bg-[#12131d] rounded-2xl border border-white/[0.06] text-center text-xs text-slate-400">
                No active consultation hours found for this physician.
              </div>
            ) : (
              <div className="space-y-2">
                {availability.map((slot) => (
                  <div
                    key={slot.id}
                    className="p-3 bg-[#12131d] rounded-2xl border border-white/[0.06] flex items-center justify-between text-xs"
                  >
                    <span className="font-semibold text-slate-200">{slot.day_name}</span>
                    <span className="font-mono text-purple-300">
                      {slot.start_time} - {slot.end_time}
                    </span>
                  </div>
                ))}
              </div>
            )}

            <div className="pt-4 border-t border-white/[0.06] space-y-2">
              <Link
                to={`/book/${doctor.id}`}
                className="w-full inline-flex items-center justify-center gap-2 py-3 px-4 rounded-2xl text-xs font-bold text-white bg-[#6c5dd3] hover:bg-purple-600 transition-all shadow-md shadow-purple-600/20"
              >
                <Calendar className="w-4 h-4" /> Book Appointment
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
