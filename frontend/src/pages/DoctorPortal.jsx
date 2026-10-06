import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  getDoctorMe,
  getDoctorMeAvailability,
  addDoctorMeAvailability,
  deleteDoctorMeAvailability,
  getAppointments,
} from '../services/api';
import {
  Stethoscope,
  Calendar,
  Clock,
  User,
  Plus,
  Trash2,
  AlertCircle,
  CheckCircle2,
  Loader2,
  ShieldCheck,
  RefreshCw,
  FileText,
} from 'lucide-react';

const DAYS = [
  { val: 0, label: 'Sunday' },
  { val: 1, label: 'Monday' },
  { val: 2, label: 'Tuesday' },
  { val: 3, label: 'Wednesday' },
  { val: 4, label: 'Thursday' },
  { val: 5, label: 'Friday' },
  { val: 6, label: 'Saturday' },
];

export const DoctorPortal = () => {
  const { profile } = useAuth();
  const isDoctor = profile?.role === 'doctor';

  const [doctorProfile, setDoctorProfile] = useState(null);
  const [availability, setAvailability] = useState([]);
  const [appointments, setAppointments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionSuccess, setActionSuccess] = useState('');

  // New slot form state
  const [newDay, setNewDay] = useState(1);
  const [newStart, setNewStart] = useState('09:00');
  const [newEnd, setNewEnd] = useState('17:00');
  const [addingSlot, setAddingSlot] = useState(false);

  const loadDoctorData = async () => {
    setLoading(true);
    setError('');
    const [docRes, availRes, apptRes] = await Promise.all([
      getDoctorMe(),
      getDoctorMeAvailability(),
      getAppointments(),
    ]);

    if (docRes.success) {
      setDoctorProfile(docRes.data);
    }

    if (availRes.success) {
      setAvailability(availRes.data);
    } else {
      setError(availRes.error || 'Failed to load availability schedules.');
    }

    if (apptRes.success) {
      setAppointments(apptRes.data);
    }

    setLoading(false);
  };

  useEffect(() => {
    if (isDoctor) {
      loadDoctorData();
    } else {
      setLoading(false);
    }
  }, [isDoctor]);

  const handleAddSlot = async (e) => {
    e.preventDefault();
    setActionSuccess('');
    setError('');
    setAddingSlot(true);

    const res = await addDoctorMeAvailability({
      day_of_week: Number(newDay),
      start_time: newStart,
      end_time: newEnd,
      is_active: true,
    });

    if (res.success) {
      setActionSuccess('New consultation hours added to your weekly schedule.');
      setAvailability((prev) => [...prev, res.data].sort((a, b) => a.day_of_week - b.day_of_week));
    } else {
      setError(res.error || 'Failed to add schedule slot.');
    }
    setAddingSlot(false);
  };

  const handleDeleteSlot = async (slotId) => {
    if (!window.confirm('Remove this availability slot from your weekly schedule?')) return;
    setError('');
    setActionSuccess('');

    const res = await deleteDoctorMeAvailability(slotId);
    if (res.success) {
      setActionSuccess('Availability slot removed.');
      setAvailability((prev) => prev.filter((s) => s.id !== slotId));
    } else {
      setError(res.error || 'Failed to remove slot.');
    }
  };

  if (!isDoctor) {
    return (
      <div className="max-w-2xl mx-auto py-16 text-center space-y-4">
        <div className="w-16 h-16 rounded-3xl bg-rose-500/10 text-rose-400 border border-rose-500/20 flex items-center justify-center mx-auto">
          <ShieldCheck className="w-8 h-8" />
        </div>
        <h2 className="text-xl font-bold text-white">Physician Clinical Portal Access Required</h2>
        <p className="text-xs text-slate-400 max-w-md mx-auto">
          The doctor appointment portal and weekly scheduling hub are restricted to registered healthcare professionals.
        </p>
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 px-5 py-2.5 rounded-2xl text-xs font-semibold bg-[#6c5dd3] text-white hover:bg-purple-600 transition-colors shadow-lg shadow-purple-600/20"
        >
          Return to Patient Dashboard
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-8 max-w-6xl mx-auto">
      {/* Header Banner */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-[#6355d8] via-[#735df2] to-[#8c75ff] p-8 text-white shadow-xl shadow-purple-900/20">
        <div className="absolute top-0 right-0 w-80 h-80 bg-white/10 rounded-full blur-2xl pointer-events-none -mr-20 -mt-20" />
        <div className="relative z-10 flex flex-col sm:flex-row sm:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-white/20 text-white backdrop-blur-md">
              <Stethoscope className="w-3.5 h-3.5" /> Physician Clinical Hub
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
              Doctor Consultation Workspace
            </h1>
            <p className="text-xs sm:text-sm text-purple-100/90">
              Manage your weekly patient appointment queues, consultation hours, and schedule availability.
            </p>
          </div>

          <button
            onClick={loadDoctorData}
            disabled={loading}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-2xl text-xs font-semibold bg-[#12131d] border border-white/[0.08] text-slate-300 hover:text-white transition-colors cursor-pointer shrink-0"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} /> Refresh Workspace
          </button>
        </div>
      </div>

      {/* Notifications */}
      {error && (
        <div className="p-4 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center gap-2.5">
          <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
          <span>{error}</span>
        </div>
      )}

      {actionSuccess && (
        <div className="p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs flex items-center gap-2.5">
          <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400" />
          <span>{actionSuccess}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column: Assigned Upcoming Appointments */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-[#181926] border border-white/[0.08] rounded-3xl p-6 sm:p-8 space-y-6 shadow-xl">
            <div className="flex items-center justify-between border-b border-white/[0.06] pb-4">
              <div>
                <h2 className="text-base font-bold text-white flex items-center gap-2">
                  <Calendar className="w-5 h-5 text-purple-400" /> Assigned Patient Consultations
                </h2>
                <p className="text-xs text-slate-400 mt-0.5">
                  Showing all active and historical bookings assigned to your profile.
                </p>
              </div>
              <span className="px-3 py-1 rounded-full text-xs font-bold bg-purple-500/15 text-purple-300 border border-purple-500/20">
                {appointments.length} Total
              </span>
            </div>

            {loading ? (
              <div className="py-16 flex flex-col items-center justify-center space-y-3">
                <Loader2 className="w-7 h-7 text-purple-400 animate-spin" />
                <p className="text-xs text-slate-400">Loading assigned consultations...</p>
              </div>
            ) : appointments.length === 0 ? (
              <div className="p-8 text-center bg-[#12131d] rounded-2xl border border-white/[0.06] space-y-2">
                <Calendar className="w-8 h-8 text-slate-500 mx-auto" />
                <p className="text-xs text-slate-300 font-semibold">No appointments assigned yet</p>
                <p className="text-[11px] text-slate-400 max-w-xs mx-auto">
                  When patients schedule consultations matching your working schedule, they will appear here.
                </p>
              </div>
            ) : (
              <div className="space-y-3.5">
                {appointments.map((appt) => (
                  <div
                    key={appt.id}
                    className="p-4 bg-[#12131d] rounded-2xl border border-white/[0.06] hover:border-purple-500/30 transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-slate-100 text-sm flex items-center gap-1.5">
                          <User className="w-3.5 h-3.5 text-purple-400" />
                          {appt.patient_name || 'Patient'}
                        </span>
                        <span
                          className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                            appt.status === 'scheduled'
                              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                              : appt.status === 'completed'
                              ? 'bg-purple-500/10 text-purple-300 border border-purple-500/20'
                              : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                          }`}
                        >
                          {appt.status}
                        </span>
                      </div>

                      <div className="flex items-center gap-3 text-xs text-slate-400">
                        <span>{appt.appointment_date}</span>
                        <span>&bull;</span>
                        <span className="font-mono text-purple-300">
                          {appt.start_time} - {appt.end_time}
                        </span>
                      </div>

                      {appt.reason && (
                        <p className="text-xs text-slate-300 pt-1">
                          <strong className="text-slate-400">Reason:</strong> {appt.reason}
                        </p>
                      )}
                    </div>

                    <div className="flex items-center gap-2">
                      <Link
                        to={`/clinical-notes?appointmentId=${appt.id}`}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-purple-500/10 text-purple-300 border border-purple-500/20 hover:bg-purple-500/20 transition-all"
                      >
                        <FileText className="w-3.5 h-3.5" />
                        <span>Document Visit</span>
                      </Link>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Weekly Availability Hours */}
        <div className="space-y-6">
          <div className="bg-[#181926] border border-white/[0.08] rounded-3xl p-6 space-y-6 shadow-xl">
            <div>
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                <Clock className="w-4 h-4 text-purple-400" /> Weekly Availability Schedule
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Configure your active consultation hours.
              </p>
            </div>

            {/* Availability Slots List */}
            <div className="space-y-2.5">
              {availability.length === 0 ? (
                <p className="text-xs text-slate-400">No availability configured.</p>
              ) : (
                availability.map((slot) => (
                  <div
                    key={slot.id}
                    className="p-3 bg-[#12131d] rounded-2xl border border-white/[0.06] flex items-center justify-between text-xs"
                  >
                    <div>
                      <span className="font-semibold text-slate-200 block">{slot.day_name}</span>
                      <span className="font-mono text-[11px] text-purple-300">
                        {slot.start_time} - {slot.end_time}
                      </span>
                    </div>
                    <button
                      onClick={() => handleDeleteSlot(slot.id)}
                      className="p-1.5 rounded-xl text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors cursor-pointer"
                      title="Delete slot"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))
              )}
            </div>

            {/* Add New Slot Form */}
            <form onSubmit={handleAddSlot} className="pt-4 border-t border-white/[0.06] space-y-3">
              <span className="block text-xs font-semibold text-slate-300 uppercase tracking-wider">
                Add Working Hours
              </span>

              <div>
                <label className="block text-[11px] text-slate-400 mb-1">Day of Week</label>
                <select
                  value={newDay}
                  onChange={(e) => setNewDay(e.target.value)}
                  className="w-full py-2 px-3 bg-[#12131d] border border-white/[0.08] rounded-2xl text-xs text-slate-100 focus:outline-none focus:ring-1 focus:ring-purple-500 cursor-pointer"
                >
                  {DAYS.map((d) => (
                    <option key={d.val} value={d.val}>
                      {d.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-[11px] text-slate-400 mb-1">Start Time</label>
                  <input
                    type="time"
                    required
                    value={newStart}
                    onChange={(e) => setNewStart(e.target.value)}
                    className="w-full py-2 px-3 bg-[#12131d] border border-white/[0.08] rounded-2xl text-xs text-slate-100 font-mono focus:outline-none focus:ring-1 focus:ring-purple-500"
                  />
                </div>
                <div>
                  <label className="block text-[11px] text-slate-400 mb-1">End Time</label>
                  <input
                    type="time"
                    required
                    value={newEnd}
                    onChange={(e) => setNewEnd(e.target.value)}
                    className="w-full py-2 px-3 bg-[#12131d] border border-white/[0.08] rounded-2xl text-xs text-slate-100 font-mono focus:outline-none focus:ring-1 focus:ring-purple-500"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={addingSlot}
                className="w-full inline-flex items-center justify-center gap-1.5 py-2.5 px-4 rounded-2xl text-xs font-bold text-white bg-[#6c5dd3] hover:bg-purple-600 transition-all cursor-pointer shadow-md shadow-purple-600/20 disabled:opacity-50"
              >
                {addingSlot ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Plus className="w-3.5 h-3.5" />
                )}
                Save Working Hours
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
};
