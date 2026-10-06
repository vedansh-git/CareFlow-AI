import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  getAppointments,
  getDoctors,
  getDoctorMeAvailability,
  getClinicalNotes,
} from '../services/api';
import {
  Calendar,
  Clock,
  User,
  Users,
  Briefcase,
  FileText,
  Sparkles,
  ArrowRight,
  CheckCircle2,
  Bookmark,
  Stethoscope,
  FolderOpen,
  ChevronRight,
  Plus,
  HeartPulse,
  Brain,
  Eye,
  ShieldCheck,
  CalendarCheck,
  Bot,
  Layers,
} from 'lucide-react';

export const Home = () => {
  const { user, profile } = useAuth();
  const navigate = useNavigate();

  const isDoctor = profile?.role === 'doctor';
  const displayName = profile?.full_name || user?.email?.split('@')[0] || 'CareFlow User';

  const [appointments, setAppointments] = useState([]);
  const [doctors, setDoctors] = useState([]);
  const [doctorAvailability, setDoctorAvailability] = useState([]);
  const [clinicalNotes, setClinicalNotes] = useState([]);
  const [loading, setLoading] = useState(true);

  // Load real data for dashboard widgets
  useEffect(() => {
    let isMounted = true;

    const loadDashboardData = async () => {
      setLoading(true);
      try {
        const apptPromise = getAppointments();
        const docPromise = getDoctors();

        if (isDoctor) {
          const [apptsRes, docsRes, availRes, notesRes] = await Promise.all([
            apptPromise,
            docPromise,
            getDoctorMeAvailability(),
            getClinicalNotes().catch(() => ({ success: false, data: [] })),
          ]);

          if (isMounted) {
            if (apptsRes.success) setAppointments(apptsRes.data || []);
            if (docsRes.success) setDoctors(docsRes.data || []);
            if (availRes.success) setDoctorAvailability(availRes.data || []);
            if (notesRes.success) setClinicalNotes(notesRes.data || []);
          }
        } else {
          const [apptsRes, docsRes] = await Promise.all([apptPromise, docPromise]);
          if (isMounted) {
            if (apptsRes.success) setAppointments(apptsRes.data || []);
            if (docsRes.success) setDoctors(docsRes.data || []);
          }
        }
      } catch (err) {
        console.error('Error loading dashboard data:', err);
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    loadDashboardData();
    return () => {
      isMounted = false;
    };
  }, [isDoctor]);

  // Derived real appointment metrics sorted chronologically
  const activeAppointments = appointments
    .filter((a) => a.status === 'scheduled' || a.status === 'confirmed')
    .sort((a, b) => {
      const timeA = `${a.appointment_date || '9999-99-99'}T${a.start_time || '00:00:00'}`;
      const timeB = `${b.appointment_date || '9999-99-99'}T${b.start_time || '00:00:00'}`;
      return timeA.localeCompare(timeB);
    });

  const todayStr = new Date().toISOString().split('T')[0];
  const todayAppointments = activeAppointments.filter((a) => a.appointment_date === todayStr);

  // Next scheduled consultation (earliest active appointment)
  const nextAppointment = activeAppointments.length > 0 ? activeAppointments[0] : null;

  const upcomingList = activeAppointments.slice(0, 5);

  // Month days for mini calendar widget
  const currentDate = new Date();
  const currentMonthName = currentDate.toLocaleString('default', { month: 'long' });
  const currentYear = currentDate.getFullYear();
  const currentDay = currentDate.getDate();

  // Generate days in month
  const daysInMonth = new Date(currentYear, currentDate.getMonth() + 1, 0).getDate();
  const firstDayIndex = (new Date(currentYear, currentDate.getMonth(), 1).getDay() + 6) % 7; // Mon=0
  const calendarDays = [];
  for (let i = 0; i < firstDayIndex; i++) {
    calendarDays.push({ day: null });
  }
  for (let i = 1; i <= daysInMonth; i++) {
    const isToday = i === currentDay;
    const hasAppt = appointments.some((a) => {
      if (!a.appointment_date) return false;
      const d = new Date(a.appointment_date);
      return (
        d.getDate() === i &&
        d.getMonth() === currentDate.getMonth() &&
        d.getFullYear() === currentYear
      );
    });
    calendarDays.push({ day: i, isToday, hasAppt });
  }

  // Specialty highlights for patient discovery
  const specialtyHighlights = [
    {
      title: 'Cardiology',
      icon: HeartPulse,
      desc: 'Heart & vascular care',
      color: 'from-rose-500 to-pink-600',
    },
    {
      title: 'Neurology',
      icon: Brain,
      desc: 'Brain & nervous system',
      color: 'from-purple-500 to-indigo-600',
    },
    {
      title: 'Ophthalmology',
      icon: Eye,
      desc: 'Eye & vision health',
      color: 'from-cyan-500 to-blue-600',
    },
    {
      title: 'General Medicine',
      icon: Stethoscope,
      desc: 'Primary clinical care',
      color: 'from-emerald-500 to-teal-600',
    },
  ];

  return (
    <div className="space-y-8">
      {/* 1. WELCOME HERO BANNER */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-[#6355d8] via-[#735df2] to-[#8c75ff] p-6 sm:p-8 text-white shadow-xl shadow-purple-900/20">
        {/* Ambient glow */}
        <div className="absolute top-0 right-0 w-80 h-80 bg-white/10 rounded-full blur-2xl pointer-events-none -mr-20 -mt-20" />
        <div className="absolute bottom-0 left-1/3 w-60 h-60 bg-purple-900/30 rounded-full blur-xl pointer-events-none" />

        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-2.5">
              <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
                Welcome back, {isDoctor ? `Dr. ${displayName.replace(/^Dr\.?\s*/i, '')}` : displayName}
              </h1>
              <span className="text-2xl sm:text-3xl animate-wave">👋</span>
            </div>
            <p className="text-sm text-purple-100/95 font-medium max-w-2xl">
              {isDoctor ? (
                <>
                  You have{' '}
                  <span className="font-bold text-white underline decoration-purple-300 underline-offset-2">
                    {activeAppointments.length} active consultation{activeAppointments.length === 1 ? '' : 's'}
                  </span>{' '}
                  assigned and clinical documentation ready for review.
                </>
              ) : (
                <>
                  {activeAppointments.length > 0 ? (
                    <>
                      You have{' '}
                      <span className="font-bold text-white underline decoration-purple-300 underline-offset-2">
                        {activeAppointments.length} upcoming appointment{activeAppointments.length === 1 ? '' : 's'}
                      </span>
                      . Review your schedule or consult our clinical AI assistant.
                    </>
                  ) : (
                    'No consultations scheduled today. Browse verified doctors or schedule an appointment with our AI booking agent.'
                  )}
                </>
              )}
            </p>
          </div>

          <div className="flex items-center gap-3 shrink-0">
            {isDoctor ? (
              <Link
                to="/clinical-notes"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-2xl bg-white text-[#6355d8] hover:bg-purple-50 font-bold text-xs sm:text-sm shadow-md transition-all group"
              >
                <FileText className="w-4 h-4" />
                <span>New SOAP Note</span>
                <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
              </Link>
            ) : (
              <div className="flex items-center gap-2.5">
                <Link
                  to="/book"
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-2xl bg-white text-[#6355d8] hover:bg-purple-50 font-bold text-xs sm:text-sm shadow-md transition-all group"
                >
                  <Plus className="w-4 h-4" />
                  <span>Book Consultation</span>
                  <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
                </Link>
                <Link
                  to="/assistant"
                  className="hidden sm:inline-flex items-center gap-2 px-4 py-2.5 rounded-2xl bg-white/15 hover:bg-white/25 text-white font-semibold text-xs sm:text-sm border border-white/20 backdrop-blur-sm transition-all"
                >
                  <Sparkles className="w-4 h-4 text-purple-200" />
                  <span>AI Assistant</span>
                </Link>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 2. MAIN 2-COLUMN PATIENT WORKSPACE (Clean hierarchy without Analytics) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* LEFT COLUMN (7 or 8 cols): Next Appointment Highlight & Quick Actions */}
        <div className="lg:col-span-7 space-y-6">
          {/* PRIMARY CARD: NEXT UPCOMING CONSULTATION / APPOINTMENT HIGHLIGHT */}
          {nextAppointment ? (
            <div className="rounded-3xl bg-[#181926] border border-white/[0.08] p-6 sm:p-7 shadow-lg relative overflow-hidden group hover:border-purple-500/30 transition-all">
              <div className="flex items-center justify-between pb-4 border-b border-white/[0.06]">
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-xl bg-purple-500/15 border border-purple-500/30 flex items-center justify-center text-purple-400">
                    <CalendarCheck className="w-4 h-4" />
                  </div>
                  <div>
                    <h2 className="text-sm font-bold text-white uppercase tracking-wider">
                      {isDoctor ? 'Next Scheduled Patient' : 'Next Upcoming Consultation'}
                    </h2>
                  </div>
                </div>
                <span className="px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  {nextAppointment.status || 'Scheduled'}
                </span>
              </div>

              <div className="pt-5 space-y-4">
                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-purple-500 to-indigo-600 flex items-center justify-center font-bold text-base text-white uppercase shadow-md shrink-0">
                    {isDoctor
                      ? (nextAppointment.patient_name || 'P').charAt(0)
                      : (nextAppointment.doctor_name || 'D').charAt(0)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <h3 className="text-base sm:text-lg font-bold text-white truncate">
                      {isDoctor
                        ? (nextAppointment.patient_name || 'Patient Consultation')
                        : (nextAppointment.doctor_name || 'CareFlow Specialist')}
                    </h3>
                    <p className="text-xs font-semibold text-purple-300">
                      {isDoctor
                        ? (nextAppointment.reason ? `Reason: ${nextAppointment.reason}` : 'General Consultation')
                        : (nextAppointment.doctor_specialty || 'General Practitioner')}
                    </p>
                    {!isDoctor && nextAppointment.reason && (
                      <p className="text-xs text-slate-300 mt-1 line-clamp-1">
                        <span className="text-slate-400">Reason:</span> {nextAppointment.reason}
                      </p>
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
                  <div className="p-3 bg-[#12131d] rounded-2xl border border-white/[0.06] flex items-center gap-2.5 text-xs text-slate-300">
                    <Calendar className="w-4 h-4 text-purple-400 shrink-0" />
                    <div>
                      <span className="text-[10px] uppercase tracking-wider text-slate-400 block font-semibold">
                        Date
                      </span>
                      <strong className="text-slate-100">{nextAppointment.appointment_date}</strong>
                    </div>
                  </div>

                  <div className="p-3 bg-[#12131d] rounded-2xl border border-white/[0.06] flex items-center gap-2.5 text-xs text-slate-300">
                    <Clock className="w-4 h-4 text-purple-400 shrink-0" />
                    <div>
                      <span className="text-[10px] uppercase tracking-wider text-slate-400 block font-semibold">
                        Time Slot
                      </span>
                      <span className="font-mono text-purple-300 font-semibold">
                        {nextAppointment.start_time?.substring(0, 5)} - {nextAppointment.end_time?.substring(0, 5)}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center justify-between pt-3 border-t border-white/[0.06]">
                  {isDoctor ? (
                    <>
                      <Link
                        to="/doctor/appointments"
                        className="text-xs font-bold text-purple-400 hover:text-purple-300 flex items-center gap-1 transition-colors"
                      >
                        <span>Manage schedule</span>
                        <ChevronRight className="w-3.5 h-3.5" />
                      </Link>

                      <Link
                        to={`/clinical-notes/${nextAppointment.id}`}
                        className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#6c5dd3] hover:bg-purple-600 text-white text-xs font-semibold shadow-md transition-all"
                      >
                        <FileText className="w-3.5 h-3.5" />
                        <span>Start SOAP Note</span>
                      </Link>
                    </>
                  ) : (
                    <>
                      <Link
                        to="/appointments"
                        className="text-xs font-bold text-purple-400 hover:text-purple-300 flex items-center gap-1 transition-colors"
                      >
                        <span>Manage all appointments</span>
                        <ChevronRight className="w-3.5 h-3.5" />
                      </Link>

                      <Link
                        to="/book"
                        className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-purple-500/10 hover:bg-purple-500/20 text-purple-300 border border-purple-500/20 text-xs font-semibold transition-all"
                      >
                        <span>Book Another</span>
                        <Plus className="w-3.5 h-3.5" />
                      </Link>
                    </>
                  )}
                </div>
              </div>
            </div>
          ) : (
            /* Empty state when no upcoming appointments */
            <div className="rounded-3xl bg-[#181926] border border-white/[0.08] p-6 sm:p-7 shadow-lg flex flex-col justify-between">
              <div className="flex items-center justify-between pb-4 border-b border-white/[0.06]">
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-xl bg-purple-500/15 border border-purple-500/30 flex items-center justify-center text-purple-400">
                    <Calendar className="w-4 h-4" />
                  </div>
                  <h2 className="text-sm font-bold text-white uppercase tracking-wider">
                    Consultation Status
                  </h2>
                </div>
                <span className="px-3 py-1 rounded-full text-xs font-semibold bg-white/[0.05] text-slate-400 border border-white/[0.08]">
                  No Active Booking
                </span>
              </div>

              <div className="py-6 text-center space-y-3">
                <div className="w-12 h-12 rounded-2xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center mx-auto text-purple-400">
                  <Stethoscope className="w-6 h-6" />
                </div>
                <div className="space-y-1">
                  <h3 className="text-base font-bold text-white">
                    {isDoctor ? 'No upcoming patient appointments' : 'Need to see a doctor?'}
                  </h3>
                  <p className="text-xs text-slate-400 max-w-md mx-auto">
                    {isDoctor
                      ? 'You have no active consultations scheduled on your calendar. You can configure your weekly availability or review clinical documentation.'
                      : 'Schedule a 30-minute consultation with a verified medical specialist or let our conversational AI find the best appointment slot.'}
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-3 border-t border-white/[0.06]">
                {isDoctor ? (
                  <>
                    <Link
                      to="/doctor/appointments"
                      className="flex items-center justify-center gap-2 p-3 rounded-2xl bg-[#6c5dd3] hover:bg-[#5e4fc4] text-white text-xs font-bold shadow-md shadow-purple-600/20 transition-all"
                    >
                      <Briefcase className="w-4 h-4" />
                      <span>Manage Availability</span>
                    </Link>
                    <Link
                      to="/clinical-notes"
                      className="flex items-center justify-center gap-2 p-3 rounded-2xl bg-purple-500/10 hover:bg-purple-500/20 text-purple-300 border border-purple-500/20 text-xs font-bold transition-all"
                    >
                      <FileText className="w-4 h-4 text-purple-400" />
                      <span>Clinical SOAP Notes</span>
                    </Link>
                  </>
                ) : (
                  <>
                    <Link
                      to="/book"
                      className="flex items-center justify-center gap-2 p-3 rounded-2xl bg-[#6c5dd3] hover:bg-[#5e4fc4] text-white text-xs font-bold shadow-md shadow-purple-600/20 transition-all"
                    >
                      <Calendar className="w-4 h-4" />
                      <span>Book Consultation</span>
                    </Link>
                    <Link
                      to="/book?mode=ai"
                      className="flex items-center justify-center gap-2 p-3 rounded-2xl bg-purple-500/10 hover:bg-purple-500/20 text-purple-300 border border-purple-500/20 text-xs font-bold transition-all"
                    >
                      <Sparkles className="w-4 h-4 text-purple-400" />
                      <span>Book with AI Agent</span>
                    </Link>
                  </>
                )}
              </div>
            </div>
          )}

          {/* SECONDARY SECTION: 4 KEY PATIENT MODULES */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
                <Bookmark className="w-4 h-4 text-purple-400" />
                <span>Care &amp; Clinical Services</span>
              </h2>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {/* Module 1: Find Specialists */}
              <Link
                to="/doctors"
                className="p-5 rounded-3xl bg-[#181926] hover:bg-[#1e2030] border border-white/[0.08] hover:border-purple-500/40 transition-all flex flex-col justify-between group shadow-md"
              >
                <div className="space-y-3">
                  <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-teal-500 to-emerald-600 flex items-center justify-center text-white shadow-md group-hover:scale-105 transition-transform">
                    <Users className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-white group-hover:text-teal-300 transition-colors">
                      Specialist Directory
                    </h3>
                    <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                      Explore verified physicians, qualifications, consultation fees, and weekly schedule hours.
                    </p>
                  </div>
                </div>
                <div className="mt-4 flex items-center gap-1.5 text-xs font-bold text-teal-400">
                  <span>Browse Doctors</span>
                  <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
                </div>
              </Link>

              {/* Module 2: AI Assistant */}
              <Link
                to="/assistant"
                className="p-5 rounded-3xl bg-[#181926] hover:bg-[#1e2030] border border-white/[0.08] hover:border-purple-500/40 transition-all flex flex-col justify-between group shadow-md"
              >
                <div className="space-y-3">
                  <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-purple-500 to-indigo-600 flex items-center justify-center text-white shadow-md group-hover:scale-105 transition-transform">
                    <Sparkles className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-white group-hover:text-purple-300 transition-colors">
                      AI Clinical Assistant
                    </h3>
                    <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                      Ask medical and care questions securely grounded in indexed clinical reference literature.
                    </p>
                  </div>
                </div>
                <div className="mt-4 flex items-center gap-1.5 text-xs font-bold text-purple-400">
                  <span>Open Assistant</span>
                  <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
                </div>
              </Link>

              {/* Module 3: My Appointments */}
              <Link
                to="/appointments"
                className="p-5 rounded-3xl bg-[#181926] hover:bg-[#1e2030] border border-white/[0.08] hover:border-purple-500/40 transition-all flex flex-col justify-between group shadow-md"
              >
                <div className="space-y-3">
                  <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-sky-500 to-blue-600 flex items-center justify-center text-white shadow-md group-hover:scale-105 transition-transform">
                    <Calendar className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-white group-hover:text-sky-300 transition-colors">
                      My Appointments
                    </h3>
                    <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                      Review upcoming visits, manage cancellation requests, and view consultation histories.
                    </p>
                  </div>
                </div>
                <div className="mt-4 flex items-center gap-1.5 text-xs font-bold text-sky-400">
                  <span>View Appointments</span>
                  <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
                </div>
              </Link>

              {/* Module 4: My Documents */}
              <Link
                to="/documents"
                className="p-5 rounded-3xl bg-[#181926] hover:bg-[#1e2030] border border-white/[0.08] hover:border-purple-500/40 transition-all flex flex-col justify-between group shadow-md"
              >
                <div className="space-y-3">
                  <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-amber-500 to-orange-600 flex items-center justify-center text-white shadow-md group-hover:scale-105 transition-transform">
                    <FolderOpen className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-white group-hover:text-amber-300 transition-colors">
                      My Medical Documents
                    </h3>
                    <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                      Upload lab results, medical records, and reference PDFs for instant clinical vector retrieval.
                    </p>
                  </div>
                </div>
                <div className="mt-4 flex items-center gap-1.5 text-xs font-bold text-amber-400">
                  <span>Manage Documents</span>
                  <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
                </div>
              </Link>
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN (5 cols): Mini Calendar & Upcoming Schedule */}
        <div className="lg:col-span-5 space-y-6">
          <div className="rounded-3xl bg-[#181926] border border-white/[0.08] p-6 shadow-lg space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-base font-bold text-white">Upcoming Schedule</h2>
                <p className="text-xs text-slate-400">
                  {currentMonthName} {currentYear}
                </p>
              </div>
              <div className="p-2.5 rounded-2xl bg-purple-500/10 text-purple-400 border border-purple-500/20">
                <Calendar className="w-4 h-4" />
              </div>
            </div>

            {/* Mini Calendar Month Grid */}
            <div className="space-y-2 bg-[#12131d] p-4 rounded-2xl border border-white/[0.06]">
              <div className="grid grid-cols-7 text-center text-[10px] font-semibold uppercase text-slate-400 pb-1">
                <span>Mon</span>
                <span>Tue</span>
                <span>Wed</span>
                <span>Thu</span>
                <span>Fri</span>
                <span>Sat</span>
                <span>Sun</span>
              </div>
              <div className="grid grid-cols-7 text-center gap-1">
                {calendarDays.map((item, idx) => (
                  <div
                    key={idx}
                    className={`h-7 flex items-center justify-center rounded-xl text-xs font-medium transition-all ${
                      !item.day
                        ? 'text-transparent pointer-events-none'
                        : item.isToday
                        ? 'bg-[#6c5dd3] text-white font-bold shadow-md shadow-purple-600/30 ring-1 ring-purple-300'
                        : item.hasAppt
                        ? 'bg-purple-500/20 text-purple-300 font-bold'
                        : 'text-slate-400 hover:bg-white/[0.04]'
                    }`}
                  >
                    {item.day}
                  </div>
                ))}
              </div>
            </div>

            {/* Upcoming Appointments List */}
            <div className="space-y-3 pt-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-300">Scheduled Consultations</span>
                <Link
                  to={isDoctor ? '/doctor/appointments' : '/appointments'}
                  className="text-[11px] font-semibold text-purple-400 hover:text-purple-300"
                >
                  View all ({activeAppointments.length})
                </Link>
              </div>

              {loading ? (
                <div className="py-8 text-center text-xs text-slate-400 animate-pulse">
                  Loading schedule...
                </div>
              ) : upcomingList.length === 0 ? (
                <div className="py-8 text-center bg-[#12131d] rounded-2xl border border-white/[0.06] space-y-3 p-4">
                  <div className="w-10 h-10 mx-auto rounded-2xl bg-white/[0.03] border border-white/[0.06] flex items-center justify-center text-slate-400">
                    <Calendar className="w-5 h-5 text-purple-400/60" />
                  </div>
                  <p className="text-xs text-slate-400">No scheduled appointments</p>
                  <Link
                    to={isDoctor ? '/doctor/appointments' : '/book'}
                    className="inline-flex items-center gap-1.5 text-xs font-bold text-purple-400 hover:underline"
                  >
                    <span>{isDoctor ? 'Configure availability' : 'Book first consultation'}</span>
                    <ArrowRight className="w-3 h-3" />
                  </Link>
                </div>
              ) : (
                <div className="space-y-2.5">
                  {upcomingList.map((appt) => {
                    const docName = appt.doctor_name || 'Physician Specialist';
                    const patName = appt.patient_name || 'Patient Consultation';
                    const targetName = isDoctor ? patName : docName;

                    return (
                      <div
                        key={appt.id}
                        className="flex items-center justify-between p-3 rounded-2xl bg-[#12131d] hover:bg-white/[0.04] border border-white/[0.06] transition-all group"
                      >
                        <div className="flex items-center gap-3 min-w-0">
                          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-purple-500 to-indigo-600 flex items-center justify-center text-xs font-bold text-white uppercase shrink-0">
                            {targetName.charAt(0)}
                          </div>
                          <div className="min-w-0">
                            <p className="text-xs font-bold text-slate-100 truncate">
                              {targetName}
                            </p>
                            <p className="text-[10px] text-slate-400 flex items-center gap-1">
                              <Clock className="w-3 h-3 text-purple-400" />
                              <span>
                                {appt.appointment_date} &bull; {appt.start_time?.substring(0, 5)}
                              </span>
                            </p>
                          </div>
                        </div>

                        <Link
                          to={isDoctor ? `/clinical-notes/${appt.id}` : `/appointments`}
                          className="p-2 rounded-xl bg-purple-500/10 text-purple-300 hover:bg-purple-500/20 transition-all shrink-0"
                          title={isDoctor ? 'Open SOAP Note' : 'View Details'}
                        >
                          <ChevronRight className="w-4 h-4" />
                        </Link>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* 3. DISCOVERY SECTION: CLINICAL SPECIALTIES (Patient) or DOCTOR WORKSPACE (Doctor) */}
      {isDoctor ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Quick Doctor Availability Manager */}
          <div className="rounded-3xl bg-[#181926] border border-white/[0.08] p-6 shadow-lg space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-teal-500/10 text-teal-400">
                  <Briefcase className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-white">Your Availability Schedule</h3>
                  <p className="text-xs text-slate-400">Configured slots for patient bookings</p>
                </div>
              </div>
              <Link
                to="/doctor/appointments"
                className="text-xs font-bold text-purple-400 hover:underline flex items-center gap-1"
              >
                <span>Edit Schedule</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </Link>
            </div>

            {doctorAvailability.length === 0 ? (
              <div className="p-4 rounded-2xl bg-white/[0.02] border border-white/[0.04] text-center text-xs text-slate-400">
                No active schedule hours configured. Add weekly availability in the Doctor Portal.
              </div>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
                {doctorAvailability.slice(0, 6).map((slot) => {
                  const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
                  return (
                    <div
                      key={slot.id}
                      className="p-2.5 rounded-xl bg-[#12131d] border border-white/[0.05] text-xs space-y-0.5"
                    >
                      <span className="font-bold text-purple-300">
                        {dayNames[slot.day_of_week] || 'Day'}
                      </span>
                      <p className="text-[11px] text-slate-300">
                        {slot.start_time?.substring(0, 5)} - {slot.end_time?.substring(0, 5)}
                      </p>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Quick SOAP Documentation Launcher */}
          <div className="rounded-3xl bg-[#181926] border border-white/[0.08] p-6 shadow-lg space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-purple-500/10 text-purple-400">
                  <FileText className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-white">Clinical SOAP Documentation</h3>
                  <p className="text-xs text-slate-400">AI audio transcription &amp; prescription approvals</p>
                </div>
              </div>
              <Link
                to="/clinical-notes"
                className="text-xs font-bold text-purple-400 hover:underline flex items-center gap-1"
              >
                <span>All Notes</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </Link>
            </div>

            <div className="p-4 rounded-2xl bg-gradient-to-r from-purple-900/20 to-indigo-900/20 border border-purple-500/20 flex items-center justify-between gap-4">
              <div className="space-y-1">
                <p className="text-xs font-bold text-white">Record or Upload Consultation Audio</p>
                <p className="text-[11px] text-slate-300">
                  Extracts Subjective, Objective, Assessment, Plan &amp; generates PDF prescriptions.
                </p>
              </div>
              <Link
                to="/clinical-notes"
                className="px-4 py-2 rounded-xl bg-[#6c5dd3] hover:bg-purple-600 text-white font-bold text-xs shrink-0 shadow-md transition-colors"
              >
                Launch
              </Link>
            </div>
          </div>
        </div>
      ) : (
        /* Patient Discovery: Clinical Specialties */
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Stethoscope className="w-4 h-4 text-purple-400" />
              <h2 className="text-sm font-bold text-white uppercase tracking-wider">
                Explore Clinical Specialties
              </h2>
            </div>
            <Link
              to="/doctors"
              className="text-xs font-bold text-purple-400 hover:underline flex items-center gap-1"
            >
              <span>View all doctors</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {specialtyHighlights.map((spec, idx) => {
              const Icon = spec.icon;
              return (
                <Link
                  key={idx}
                  to="/doctors"
                  className="p-5 rounded-3xl bg-[#181926] hover:bg-[#1e2030] border border-white/[0.08] hover:border-purple-500/40 transition-all flex flex-col justify-between group shadow-md"
                >
                  <div className="space-y-3">
                    <div
                      className={`w-10 h-10 rounded-2xl bg-gradient-to-tr ${spec.color} flex items-center justify-center text-white shadow-md group-hover:scale-105 transition-transform`}
                    >
                      <Icon className="w-5 h-5" />
                    </div>
                    <div>
                      <h3 className="text-sm font-bold text-white group-hover:text-purple-300 transition-colors">
                        {spec.title}
                      </h3>
                      <p className="text-[11px] text-slate-400 mt-0.5">{spec.desc}</p>
                    </div>
                  </div>
                  <div className="mt-4 flex items-center gap-1 text-[11px] font-bold text-purple-400">
                    <span>Consult Specialists</span>
                    <ArrowRight className="w-3 h-3 group-hover:translate-x-1 transition-transform" />
                  </div>
                </Link>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
