import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate, useSearchParams, Link } from 'react-router-dom';
import {
  getDoctors,
  getDoctorAvailability,
  createAppointment,
  chatWithAppointmentAgent,
} from '../services/api';
import {
  Calendar,
  Clock,
  User,
  Stethoscope,
  FileText,
  AlertCircle,
  CheckCircle2,
  Loader2,
  ArrowLeft,
  ShieldCheck,
  Bot,
  Sparkles,
  Send,
  Wrench,
  DollarSign,
  MapPin,
  HelpCircle,
  RotateCcw,
  Check,
  X,
} from 'lucide-react';

// Helper to calculate day of week for a date string (YYYY-MM-DD)
// 0 = Sunday, 1 = Monday, ..., 6 = Saturday
const getDbDayOfWeek = (dateString) => {
  if (!dateString) return -1;
  const [year, month, day] = dateString.split('-').map(Number);
  const d = new Date(year, month - 1, day);
  return d.getDay();
};

// Generates 30-minute intervals between startTime (HH:MM) and endTime (HH:MM)
const generateSlots = (startTimeStr, endTimeStr) => {
  const [sH, sM] = startTimeStr.split(':').map(Number);
  const [eH, eM] = endTimeStr.split(':').map(Number);

  let currentMin = sH * 60 + sM;
  const endMin = eH * 60 + eM;
  const slots = [];

  while (currentMin + 30 <= endMin) {
    const startH = Math.floor(currentMin / 60);
    const startM = currentMin % 60;
    const nextMin = currentMin + 30;
    const endH = Math.floor(nextMin / 60);
    const endM = nextMin % 60;

    const startFormatted = `${String(startH).padStart(2, '0')}:${String(startM).padStart(2, '0')}`;
    const endFormatted = `${String(endH).padStart(2, '0')}:${String(endM).padStart(2, '0')}`;

    slots.push({
      start: startFormatted,
      end: endFormatted,
      label: `${startFormatted} - ${endFormatted}`,
    });

    currentMin += 30;
  }
  return slots;
};

export const BookAppointment = () => {
  const { doctorId: paramDoctorId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  // Mode: 'manual' | 'ai'
  const initialMode = searchParams.get('mode') === 'ai' ? 'ai' : 'manual';
  const [bookingMode, setBookingMode] = useState(initialMode);

  // ----------------------------------------------------
  // MANUAL BOOKING STATE
  // ----------------------------------------------------
  const [doctors, setDoctors] = useState([]);
  const [selectedDoctorId, setSelectedDoctorId] = useState(paramDoctorId || '');
  const [doctorAvailability, setDoctorAvailability] = useState([]);
  const [selectedDate, setSelectedDate] = useState('');
  const [availableSlots, setAvailableSlots] = useState([]);
  const [selectedSlot, setSelectedSlot] = useState(null);
  const [reason, setReason] = useState('');

  const [loadingDoctors, setLoadingDoctors] = useState(true);
  const [loadingSlots, setLoadingSlots] = useState(false);
  const [submittingManual, setSubmittingManual] = useState(false);
  const [manualError, setManualError] = useState('');
  const [manualSuccess, setManualSuccess] = useState('');

  // ----------------------------------------------------
  // AI AGENT STATE
  // ----------------------------------------------------
  const [aiMessages, setAiMessages] = useState([
    {
      role: 'assistant',
      content:
        "Hello! I am your CareFlow AI Appointment Agent. I can help you find specialists, compare consultation fees, inspect clinic locations, check real-time availability slots, and book your consultation.\n\nHow can I help you today?",
    },
  ]);
  const [aiInput, setAiInput] = useState('');
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState('');
  const [pendingConfirmation, setPendingConfirmation] = useState(null);
  const [bookingResult, setBookingResult] = useState(null);
  const [executedTools, setExecutedTools] = useState([]);
  const [agentMetadata, setAgentMetadata] = useState(null);

  const chatEndRef = useRef(null);

  // Sync mode changes with URL search params
  const handleModeSwitch = (mode) => {
    setBookingMode(mode);
    setSearchParams(mode === 'ai' ? { mode: 'ai' } : {});
  };

  // Scroll AI chat to bottom
  useEffect(() => {
    if (bookingMode === 'ai') {
      chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [aiMessages, aiLoading, pendingConfirmation, bookingResult, bookingMode]);

  // 1. Fetch doctor list for manual mode
  useEffect(() => {
    const loadDoctors = async () => {
      setLoadingDoctors(true);
      const res = await getDoctors();
      if (res.success && res.data.length > 0) {
        setDoctors(res.data);
        if (!selectedDoctorId) {
          setSelectedDoctorId(paramDoctorId || res.data[0].id);
        }
      }
      setLoadingDoctors(false);
    };
    loadDoctors();
  }, [paramDoctorId]);

  // 2. Fetch selected doctor's availability for manual mode
  useEffect(() => {
    if (!selectedDoctorId) return;

    const loadAvailability = async () => {
      setLoadingSlots(true);
      setManualError('');
      const res = await getDoctorAvailability(selectedDoctorId);
      if (res.success) {
        setDoctorAvailability(res.data);
      } else {
        setDoctorAvailability([]);
      }
      setLoadingSlots(false);
    };

    loadAvailability();
  }, [selectedDoctorId]);

  // 3. Compute available time slots for manual mode
  useEffect(() => {
    if (!selectedDate || doctorAvailability.length === 0) {
      setAvailableSlots([]);
      setSelectedSlot(null);
      return;
    }

    const dayOfWeek = getDbDayOfWeek(selectedDate);
    const daySchedule = doctorAvailability.filter((slot) => slot.day_of_week === dayOfWeek && slot.is_active);

    if (daySchedule.length === 0) {
      setAvailableSlots([]);
      setSelectedSlot(null);
      setManualError('The selected specialist is not scheduled to consult on this day of the week. Please pick another date.');
      return;
    }

    setManualError('');
    const allGenerated = [];
    daySchedule.forEach((sched) => {
      const slots = generateSlots(sched.start_time, sched.end_time);
      allGenerated.push(...slots);
    });

    setAvailableSlots(allGenerated);
    setSelectedSlot(allGenerated.length > 0 ? allGenerated[0] : null);
  }, [selectedDate, doctorAvailability]);

  const todayStr = new Date().toISOString().split('T')[0];
  const selectedDoctor = doctors.find((d) => d.id === selectedDoctorId);

  // Manual Form Submission
  const handleManualSubmit = async (e) => {
    e.preventDefault();
    setManualError('');
    setManualSuccess('');

    if (!selectedDoctorId) {
      setManualError('Please select a physician.');
      return;
    }
    if (!selectedDate) {
      setManualError('Please choose an appointment date.');
      return;
    }
    if (!selectedSlot) {
      setManualError('Please choose an available time slot.');
      return;
    }

    try {
      setSubmittingManual(true);
      const res = await createAppointment({
        doctor_id: selectedDoctorId,
        appointment_date: selectedDate,
        start_time: selectedSlot.start,
        end_time: selectedSlot.end,
        reason: reason.trim() || 'General Medical Consultation',
      });

      if (res.success) {
        setManualSuccess('Appointment successfully confirmed! Redirecting to your schedule...');
        setTimeout(() => navigate('/appointments'), 1800);
      } else {
        setManualError(res.error || 'Failed to book appointment. Please check time slot and try again.');
      }
    } catch (err) {
      setManualError(err.message || 'An unexpected error occurred while booking.');
    } finally {
      setSubmittingManual(false);
    }
  };

  // ----------------------------------------------------
  // AI AGENT HANDLERS
  // ----------------------------------------------------
  const handleSendAiMessage = async (overrideText) => {
    const textToSend = (overrideText || aiInput).trim();
    if (!textToSend || aiLoading) return;

    const newMessages = [...aiMessages, { role: 'user', content: textToSend }];
    setAiMessages(newMessages);
    setAiInput('');
    setAiLoading(true);
    setAiError('');

    try {
      const res = await chatWithAppointmentAgent(newMessages);

      if (res.success && res.data) {
        const agentData = res.data;
        setAiMessages([
          ...newMessages,
          { role: 'assistant', content: agentData.content },
        ]);

        if (agentData.tool_calls_executed?.length > 0) {
          setExecutedTools(agentData.tool_calls_executed);
        }
        if (agentData.pending_confirmation) {
          setPendingConfirmation(agentData.pending_confirmation);
        } else {
          setPendingConfirmation(null);
        }
        if (agentData.booking_result) {
          setBookingResult(agentData.booking_result);
          setPendingConfirmation(null);
        }
        if (agentData.metadata) {
          setAgentMetadata(agentData.metadata);
        }
      } else {
        const errorMsg = res.error || 'Failed to get response from Appointment Agent.';
        setAiError(errorMsg);
        setAiMessages([
          ...newMessages,
          {
            role: 'assistant',
            content: `⚠️ I encountered an issue connecting to the AI booking engine (${errorMsg}). You can switch to the **Book Manually** tab at any time to schedule your appointment directly.`,
          },
        ]);
      }
    } catch (err) {
      setAiError(err.message || 'Unexpected network error with AI agent.');
    } finally {
      setAiLoading(false);
    }
  };

  const handleConfirmBooking = () => {
    if (!pendingConfirmation) return;
    handleSendAiMessage(
      `Yes, please confirm and book my appointment with ${pendingConfirmation.doctor_name} on ${pendingConfirmation.appointment_date} at ${pendingConfirmation.appointment_time}.`
    );
  };

  const handleCancelBookingPrompt = () => {
    setPendingConfirmation(null);
    handleSendAiMessage('I would like to look for a different time or doctor.');
  };

  const suggestionChips = [
    'Find a specialist in Cardiology',
    'Who is available for Neurology?',
    'Show Dr. Sarah Jenkins availability this week',
    'What are the consultation fees for available doctors?',
  ];

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Back Link */}
      <Link
        to="/doctors"
        className="inline-flex items-center gap-2 text-xs font-semibold text-slate-400 hover:text-purple-300 transition-colors"
      >
        <ArrowLeft className="w-4 h-4" /> Back to Specialists
      </Link>

      {/* Header Banner */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-[#6355d8] via-[#735df2] to-[#8c75ff] p-8 text-white shadow-xl shadow-purple-900/20">
        <div className="absolute top-0 right-0 w-80 h-80 bg-white/10 rounded-full blur-2xl pointer-events-none -mr-20 -mt-20" />
        
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-1.5">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-white/20 text-white backdrop-blur-md">
              <Sparkles className="w-3.5 h-3.5" /> CareFlow AI Dual-Booking Engine
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              Schedule Your Consultation
            </h1>
            <p className="text-xs sm:text-sm text-purple-100/90">
              Choose between traditional manual calendar booking or natural-language conversational AI scheduling.
            </p>
          </div>

          {/* Mode Switcher Tabs */}
          <div className="inline-flex p-1.5 bg-[#12131d] rounded-2xl border border-white/[0.08] shrink-0">
            <button
              type="button"
              onClick={() => handleModeSwitch('manual')}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                bookingMode === 'manual'
                  ? 'bg-[#6c5dd3] text-white shadow-md shadow-purple-600/30'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Calendar className="w-4 h-4" /> Book Manually
            </button>
            <button
              type="button"
              onClick={() => handleModeSwitch('ai')}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                bookingMode === 'ai'
                  ? 'bg-[#6c5dd3] text-white shadow-md shadow-purple-600/30'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Bot className="w-4 h-4" /> Book with AI Agent
            </button>
          </div>
        </div>
      </div>

      {/* ======================================================== */}
      {/* MODE 1: BOOK WITH AI AGENT (GROQ TOOL CALLING) */}
      {/* ======================================================== */}
      {bookingMode === 'ai' && (
        <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-6 backdrop-blur-md">
          {/* Agent Banner info */}
          <div className="flex items-center justify-between p-3.5 bg-slate-950/70 border border-slate-800 rounded-xl text-xs text-slate-300">
            <div className="flex items-center gap-2">
              <Bot className="w-4 h-4 text-teal-400" />
              <span>
                <strong>Groq Llama-3.3-70b Agent</strong> with live calendar tool execution & explicit patient confirmation.
              </span>
            </div>
            {agentMetadata?.model_used && (
              <span className="hidden sm:inline-block px-2.5 py-0.5 rounded-md font-mono text-[10px] bg-slate-900 text-slate-400 border border-slate-800">
                {agentMetadata.model_used}
              </span>
            )}
          </div>

          {/* Suggestion Chips */}
          <div className="space-y-1.5">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Quick Suggestions:</span>
            <div className="flex flex-wrap gap-2">
              {suggestionChips.map((chip, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => handleSendAiMessage(chip)}
                  disabled={aiLoading}
                  className="px-3 py-1.5 rounded-lg text-xs bg-slate-950 border border-slate-800 text-slate-300 hover:text-sky-300 hover:border-sky-500/40 hover:bg-slate-900 transition-all text-left cursor-pointer disabled:opacity-50"
                >
                  {chip}
                </button>
              ))}
            </div>
          </div>

          {/* Chat Stream Window */}
          <div className="space-y-4 max-h-[480px] overflow-y-auto p-4 bg-slate-950/80 rounded-2xl border border-slate-800/80">
            {aiMessages.map((msg, idx) => {
              const isUser = msg.role === 'user';
              return (
                <div
                  key={idx}
                  className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}
                >
                  {!isUser && (
                    <div className="p-2 rounded-xl bg-teal-500/10 border border-teal-500/20 text-teal-400 shrink-0 h-fit">
                      <Bot className="w-4 h-4" />
                    </div>
                  )}

                  <div
                    className={`max-w-[85%] sm:max-w-[75%] rounded-2xl p-4 text-xs sm:text-sm leading-relaxed ${
                      isUser
                        ? 'bg-gradient-to-r from-sky-500 to-sky-600 text-white shadow-md'
                        : 'bg-slate-900 border border-slate-800 text-slate-200 shadow-md whitespace-pre-wrap'
                    }`}
                  >
                    {msg.content}
                  </div>

                  {isUser && (
                    <div className="p-2 rounded-xl bg-sky-500/10 border border-sky-500/20 text-sky-400 shrink-0 h-fit">
                      <User className="w-4 h-4" />
                    </div>
                  )}
                </div>
              );
            })}

            {/* Live Tool Activity Badge */}
            {aiLoading && (
              <div className="flex items-center gap-3 p-3 bg-slate-900/90 border border-slate-800 rounded-xl text-xs text-sky-400 animate-pulse">
                <Loader2 className="w-4 h-4 animate-spin text-sky-400" />
                <span>AI Agent is inspecting schedules and evaluating appointment availability...</span>
              </div>
            )}

            {/* Interactive Confirmation Card */}
            {pendingConfirmation && !bookingResult && (
              <div className="p-5 rounded-2xl bg-gradient-to-br from-slate-900 to-slate-950 border-2 border-sky-500/40 shadow-xl space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-sky-400 font-bold text-sm">
                    <ShieldCheck className="w-5 h-5" />
                    <span>Appointment Confirmation Required</span>
                  </div>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-sky-500/10 text-sky-400 border border-sky-500/20">
                    Step 7 Server Validation
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs bg-slate-950/80 p-4 rounded-xl border border-slate-800">
                  <div>
                    <span className="text-slate-400">Specialist:</span>
                    <p className="font-bold text-slate-100">{pendingConfirmation.doctor_name}</p>
                    <p className="text-teal-400 text-[11px]">{pendingConfirmation.specialty}</p>
                  </div>
                  <div>
                    <span className="text-slate-400">Consultation Date & Slot:</span>
                    <p className="font-bold text-sky-300">
                      {pendingConfirmation.appointment_date} @ {pendingConfirmation.appointment_time}
                    </p>
                  </div>
                  <div>
                    <span className="text-slate-400">Clinic Address:</span>
                    <p className="text-slate-200 text-[11px]">{pendingConfirmation.clinic_address || 'CareFlow Medical Centre'}</p>
                  </div>
                  <div>
                    <span className="text-slate-400">Estimated Consultation Fee:</span>
                    <p className="font-bold text-emerald-400 text-sm">
                      ${pendingConfirmation.consultation_fee ? Number(pendingConfirmation.consultation_fee).toFixed(2) : '100.00'}
                    </p>
                  </div>
                </div>

                <div className="flex flex-col sm:flex-row gap-3 pt-1">
                  <button
                    type="button"
                    onClick={handleConfirmBooking}
                    disabled={aiLoading}
                    className="flex-1 inline-flex items-center justify-center gap-2 py-3 px-4 rounded-xl text-xs font-bold text-slate-950 bg-gradient-to-r from-emerald-400 to-teal-400 hover:from-emerald-300 hover:to-teal-300 transition-all shadow-md shadow-emerald-500/20 cursor-pointer disabled:opacity-50"
                  >
                    <Check className="w-4 h-4" /> Confirm & Book Appointment
                  </button>
                  <button
                    type="button"
                    onClick={handleCancelBookingPrompt}
                    disabled={aiLoading}
                    className="inline-flex items-center justify-center gap-2 py-3 px-4 rounded-xl text-xs font-semibold text-slate-400 bg-slate-950 border border-slate-800 hover:bg-slate-900 transition-all cursor-pointer"
                  >
                    <X className="w-4 h-4" /> Pick Different Slot
                  </button>
                </div>
              </div>
            )}

            {/* Booking Success Card */}
            {bookingResult && (
              <div className="p-5 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 space-y-3">
                <div className="flex items-center gap-2 text-sm font-bold text-emerald-400">
                  <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
                  <span>{bookingResult.message || 'Appointment Confirmed!'}</span>
                </div>
                <div className="text-xs text-slate-300 bg-slate-950/80 p-3.5 rounded-xl border border-emerald-500/20 space-y-1">
                  <p>
                    <strong>Appointment ID:</strong>{' '}
                    <span className="font-mono text-emerald-400">{bookingResult.appointment?.id}</span>
                  </p>
                  <p>
                    <strong>Date & Time:</strong> {bookingResult.appointment?.appointment_date} from{' '}
                    {bookingResult.appointment?.start_time} to {bookingResult.appointment?.end_time}
                  </p>
                  <p>
                    <strong>Specialist:</strong> {bookingResult.doctor?.full_name || 'CareFlow Physician'}
                  </p>
                </div>
                <div className="flex gap-3 pt-1">
                  <Link
                    to="/appointments"
                    className="inline-flex items-center gap-2 py-2 px-4 rounded-xl text-xs font-bold text-slate-950 bg-emerald-400 hover:bg-emerald-300 transition-all cursor-pointer shadow-md"
                  >
                    View in My Appointments
                  </Link>
                  <button
                    type="button"
                    onClick={() => {
                      setBookingResult(null);
                      setPendingConfirmation(null);
                      setAiMessages([
                        ...aiMessages,
                        {
                          role: 'assistant',
                          content: 'Is there anything else I can help you with today? (e.g. check doctor details, reschedule, or find another specialist).',
                        },
                      ]);
                    }}
                    className="px-3 py-2 rounded-xl text-xs font-semibold text-slate-400 bg-slate-950 border border-slate-800 hover:text-slate-200 cursor-pointer"
                  >
                    Book Another Slot
                  </button>
                </div>
              </div>
            )}

            <div ref={chatEndRef} />
          </div>

          {/* Chat Input Bar */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSendAiMessage();
            }}
            className="flex gap-2"
          >
            <input
              type="text"
              value={aiInput}
              onChange={(e) => setAiInput(e.target.value)}
              placeholder="Ask a question or request booking (e.g., 'Book with Dr. Sarah Jenkins on Monday at 10:00 AM')..."
              disabled={aiLoading}
              className="flex-1 px-4 py-3.5 bg-slate-950 border border-slate-800 rounded-xl text-slate-100 placeholder-slate-500 text-xs sm:text-sm focus:outline-none focus:ring-2 focus:ring-sky-500 transition-all disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={aiLoading || !aiInput.trim()}
              className="px-5 py-3.5 rounded-xl text-xs sm:text-sm font-bold text-slate-950 bg-gradient-to-r from-sky-400 to-teal-400 hover:from-sky-300 hover:to-teal-300 disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-md shadow-sky-500/20 cursor-pointer flex items-center gap-2"
            >
              {aiLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              <span className="hidden sm:inline">Send</span>
            </button>
          </form>

          {/* AI Footer Note */}
          <div className="flex items-center justify-between text-[11px] text-slate-500 pt-1">
            <span>Powered by Groq API (`llama-3.3-70b-versatile`) with multi-turn tool verification</span>
            <button
              type="button"
              onClick={() => handleModeSwitch('manual')}
              className="text-sky-400 hover:underline cursor-pointer"
            >
              Switch to Manual Booking
            </button>
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* MODE 2: MANUAL BOOKING (PRESERVED AND FULLY INDEPENDENT) */}
      {/* ======================================================== */}
      {bookingMode === 'manual' && (
        <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 sm:p-8 shadow-xl space-y-6 backdrop-blur-md">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800/80">
            <div className="flex items-center gap-2 text-xs font-semibold text-slate-300">
              <Calendar className="w-4 h-4 text-sky-400" />
              <span>Standard Manual Calendar Selection</span>
            </div>
            <button
              type="button"
              onClick={() => handleModeSwitch('ai')}
              className="inline-flex items-center gap-1.5 text-xs text-teal-400 hover:underline cursor-pointer"
            >
              <Sparkles className="w-3.5 h-3.5" /> Try Booking with AI Agent instead
            </button>
          </div>

          {manualError && (
            <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center gap-2.5">
              <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
              <span>{manualError}</span>
            </div>
          )}

          {manualSuccess && (
            <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs flex items-center gap-2.5">
              <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400" />
              <span>{manualSuccess}</span>
            </div>
          )}

          <form onSubmit={handleManualSubmit} className="space-y-6">
            {/* Doctor Selection */}
            <div className="space-y-2">
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider">
                1. Select Specialist
              </label>
              {loadingDoctors ? (
                <div className="p-3 bg-slate-950 rounded-xl border border-slate-800 text-xs text-slate-500 flex items-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin text-sky-400" /> Loading specialists...
                </div>
              ) : (
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500">
                    <Stethoscope className="w-4 h-4" />
                  </div>
                  <select
                    value={selectedDoctorId}
                    onChange={(e) => {
                      setSelectedDoctorId(e.target.value);
                      setSelectedSlot(null);
                    }}
                    className="block w-full pl-10 pr-4 py-3 bg-slate-950 border border-slate-800 rounded-xl text-slate-100 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500 transition-all cursor-pointer"
                  >
                    {doctors.map((doc) => (
                      <option key={doc.id} value={doc.id}>
                        {doc.full_name} — {doc.specialty} ({doc.qualification})
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {selectedDoctor && (
                <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800/80 flex flex-wrap items-center justify-between gap-2 text-xs">
                  <span className="text-slate-400">
                    Specialty: <strong className="text-teal-400">{selectedDoctor.specialty}</strong>
                  </span>
                  <span className="text-slate-400">
                    Fee: <strong className="text-emerald-400">${selectedDoctor.consultation_fee ? Number(selectedDoctor.consultation_fee).toFixed(2) : '100.00'}</strong>
                  </span>
                  <span className="text-slate-400">
                    Credentials: <strong className="text-slate-200">{selectedDoctor.qualification}</strong>
                  </span>
                </div>
              )}
            </div>

            {/* Date Picker */}
            <div className="space-y-2">
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider">
                2. Select Consultation Date
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500">
                  <Calendar className="w-4 h-4" />
                </div>
                <input
                  type="date"
                  min={todayStr}
                  required
                  value={selectedDate}
                  onChange={(e) => setSelectedDate(e.target.value)}
                  className="block w-full pl-10 pr-4 py-3 bg-slate-950 border border-slate-800 rounded-xl text-slate-100 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500 transition-all cursor-pointer"
                />
              </div>
            </div>

            {/* Time Slot Picker */}
            <div className="space-y-2">
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider">
                3. Available 30-Minute Slots
              </label>
              {!selectedDate ? (
                <div className="p-4 bg-slate-950/60 border border-slate-800/80 rounded-xl text-xs text-slate-500 text-center">
                  Please pick an appointment date above to view available time slots.
                </div>
              ) : loadingSlots ? (
                <div className="p-4 bg-slate-950 rounded-xl border border-slate-800 text-xs text-slate-400 flex items-center justify-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin text-sky-400" /> Fetching available consultation slots...
                </div>
              ) : availableSlots.length === 0 ? (
                <div className="p-4 bg-slate-950/60 border border-slate-800/80 rounded-xl text-xs text-amber-400/80 text-center">
                  No active consultation slots scheduled on this date. Please choose a different date.
                </div>
              ) : (
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2.5 max-h-56 overflow-y-auto p-1">
                  {availableSlots.map((slot) => {
                    const isSelected = selectedSlot?.start === slot.start && selectedSlot?.end === slot.end;
                    return (
                      <button
                        type="button"
                        key={`${slot.start}-${slot.end}`}
                        onClick={() => setSelectedSlot(slot)}
                        className={`p-2.5 rounded-xl text-xs font-mono font-medium border text-center transition-all cursor-pointer ${
                          isSelected
                            ? 'bg-sky-500 text-slate-950 font-bold border-sky-400 shadow-md shadow-sky-500/20'
                            : 'bg-slate-950 text-slate-300 border-slate-800 hover:border-slate-700 hover:bg-slate-900'
                        }`}
                      >
                        <Clock className="w-3 h-3 mx-auto mb-1 opacity-70" />
                        {slot.label}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Reason for Consultation */}
            <div className="space-y-2">
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider">
                4. Reason for Consultation
              </label>
              <div className="relative">
                <div className="absolute top-3.5 left-3.5 flex items-start pointer-events-none text-slate-500">
                  <FileText className="w-4 h-4" />
                </div>
                <textarea
                  rows={3}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="e.g. Routine follow-up, persistent migraine symptoms, chest tightness check..."
                  className="block w-full pl-10 pr-4 py-3 bg-slate-950 border border-slate-800 rounded-xl text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500 transition-all"
                />
              </div>
            </div>

            {/* Submit Button */}
            <div className="pt-4 border-t border-slate-800">
              <button
                type="submit"
                disabled={submittingManual || !selectedSlot || !selectedDate}
                className="w-full inline-flex items-center justify-center gap-2 py-3.5 px-6 rounded-xl text-sm font-bold text-slate-950 bg-gradient-to-r from-sky-400 to-teal-400 hover:from-sky-300 hover:to-teal-300 disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-lg shadow-sky-500/20 cursor-pointer"
              >
                {submittingManual ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" /> Confirming Appointment...
                  </>
                ) : (
                  <>
                    <Calendar className="w-4 h-4" /> Book Appointment
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
};
