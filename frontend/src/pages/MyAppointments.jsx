import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getAppointments, cancelAppointment } from '../services/api';
import {
  Calendar,
  Clock,
  User,
  Stethoscope,
  XCircle,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Plus,
  RefreshCw,
} from 'lucide-react';

export const MyAppointments = () => {
  const [appointments, setAppointments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionSuccess, setActionSuccess] = useState('');
  const [cancellingId, setCancellingId] = useState(null);
  const [filterTab, setFilterTab] = useState('all');

  const fetchAppts = async () => {
    setLoading(true);
    setError('');
    const res = await getAppointments();
    if (res.success) {
      setAppointments(res.data);
    } else {
      setError(res.error || 'Failed to load appointments.');
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchAppts();
  }, []);

  const handleCancel = async (apptId) => {
    if (!window.confirm('Are you sure you want to cancel this scheduled consultation?')) {
      return;
    }

    try {
      setCancellingId(apptId);
      setActionSuccess('');
      setError('');
      const res = await cancelAppointment(apptId);
      if (res.success) {
        setActionSuccess('Appointment successfully cancelled.');
        // Refresh appointment list
        setAppointments((prev) =>
          prev.map((a) => (a.id === apptId ? { ...a, status: 'cancelled' } : a))
        );
      } else {
        setError(res.error || 'Unable to cancel appointment.');
      }
    } catch (err) {
      setError(err.message || 'Error cancelling appointment.');
    } finally {
      setCancellingId(null);
    }
  };

  const filtered = appointments.filter((a) => {
    if (filterTab === 'scheduled') return a.status === 'scheduled';
    if (filterTab === 'cancelled') return a.status === 'cancelled';
    if (filterTab === 'completed') return a.status === 'completed';
    return true;
  });

  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      {/* Header Banner */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-[#6355d8] via-[#735df2] to-[#8c75ff] p-8 text-white shadow-xl shadow-purple-900/20">
        <div className="absolute top-0 right-0 w-80 h-80 bg-white/10 rounded-full blur-2xl pointer-events-none -mr-20 -mt-20" />
        <div className="relative z-10 flex flex-col sm:flex-row sm:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-white/20 text-white backdrop-blur-md">
              <Calendar className="w-3.5 h-3.5" /> Patient Consultations
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
              My Scheduled Appointments
            </h1>
            <p className="text-xs sm:text-sm text-purple-100/90">
              Review your upcoming clinical sessions, check physician assignments, and manage bookings.
            </p>
          </div>

          <div className="flex items-center gap-3 shrink-0">
            <button
              onClick={fetchAppts}
              disabled={loading}
              className="p-3 rounded-2xl bg-[#12131d] border border-white/[0.08] text-slate-300 hover:text-white transition-colors cursor-pointer"
              title="Refresh Appointments"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
            <Link
              to="/book"
              className="inline-flex items-center gap-2 px-5 py-3 rounded-2xl text-xs font-bold text-[#6355d8] bg-white hover:bg-purple-50 transition-all shadow-lg cursor-pointer"
            >
              <Plus className="w-4 h-4" /> Book New Appointment
            </Link>
          </div>
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

      {/* Filter Tabs */}
      <div className="flex items-center gap-2 border-b border-white/[0.06] pb-3 overflow-x-auto">
        {[
          { id: 'all', label: `All (${appointments.length})` },
          { id: 'scheduled', label: `Upcoming (${appointments.filter((a) => a.status === 'scheduled').length})` },
          { id: 'completed', label: `Completed (${appointments.filter((a) => a.status === 'completed').length})` },
          { id: 'cancelled', label: `Cancelled (${appointments.filter((a) => a.status === 'cancelled').length})` },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setFilterTab(tab.id)}
            className={`px-4 py-2 rounded-2xl text-xs font-semibold transition-all cursor-pointer ${
              filterTab === tab.id
                ? 'bg-[#6c5dd3] text-white shadow-md shadow-purple-600/30'
                : 'text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Appointments List */}
      {loading ? (
        <div className="py-20 flex flex-col items-center justify-center space-y-3">
          <Loader2 className="w-8 h-8 text-purple-400 animate-spin" />
          <p className="text-xs text-slate-400">Loading your appointments...</p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="bg-[#181926] border border-white/[0.08] rounded-3xl p-12 text-center space-y-4 shadow-lg">
          <Calendar className="w-12 h-12 text-slate-500 mx-auto" />
          <h3 className="text-base font-semibold text-slate-200">No appointments found</h3>
          <p className="text-xs text-slate-400 max-w-sm mx-auto">
            {filterTab === 'all'
              ? 'You have not scheduled any clinical appointments yet.'
              : `You have no appointments with status "${filterTab}".`}
          </p>
          <div className="pt-2">
            <Link
              to="/book"
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-2xl text-xs font-bold text-white bg-[#6c5dd3] hover:bg-purple-600 transition-all cursor-pointer shadow-md shadow-purple-600/20"
            >
              <Plus className="w-4 h-4" /> Book First Consultation
            </Link>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {filtered.map((appt) => {
            const isScheduled = appt.status === 'scheduled';
            const isCancelled = appt.status === 'cancelled';
            const isCompleted = appt.status === 'completed';

            return (
              <div
                key={appt.id}
                className="bg-[#181926] border border-white/[0.08] rounded-3xl p-6 flex flex-col md:flex-row md:items-center justify-between gap-6 hover:border-purple-500/40 transition-all shadow-lg"
              >
                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-purple-500 to-indigo-600 flex items-center justify-center font-bold text-white uppercase text-base shadow-md shadow-purple-600/20 shrink-0">
                    {(appt.doctor_name || 'D').charAt(0)}
                  </div>

                  <div className="space-y-1.5">
                    <div className="flex items-center gap-3">
                      <h3 className="text-base font-bold text-white">
                        {appt.doctor_name || 'CareFlow Physician'}
                      </h3>
                      {isScheduled && (
                        <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                          Scheduled
                        </span>
                      )}
                      {isCancelled && (
                        <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-rose-500/10 text-rose-400 border border-rose-500/20">
                          Cancelled
                        </span>
                      )}
                      {isCompleted && (
                        <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-purple-500/10 text-purple-300 border border-purple-500/20">
                          Completed
                        </span>
                      )}
                    </div>

                    <p className="text-xs font-semibold text-purple-300">{appt.doctor_specialty}</p>

                    <div className="flex flex-wrap items-center gap-4 text-xs text-slate-300 pt-1">
                      <span className="flex items-center gap-1.5">
                        <Calendar className="w-3.5 h-3.5 text-slate-400" />
                        <strong className="font-semibold text-slate-100">{appt.appointment_date}</strong>
                      </span>
                      <span className="flex items-center gap-1.5 font-mono text-purple-300 bg-[#12131d] px-2.5 py-0.5 rounded-xl border border-white/[0.06]">
                        <Clock className="w-3 h-3 text-purple-400" />
                        {appt.start_time} - {appt.end_time}
                      </span>
                    </div>

                    {appt.reason && (
                      <p className="text-xs text-slate-400 pt-1">
                        <span className="text-slate-400 font-medium">Reason:</span> {appt.reason}
                      </p>
                    )}
                  </div>
                </div>

                {/* Actions */}
                {isScheduled && (
                  <div className="flex items-center gap-3 shrink-0 pt-3 md:pt-0 border-t md:border-t-0 border-white/[0.06]">
                    <button
                      onClick={() => handleCancel(appt.id)}
                      disabled={cancellingId === appt.id}
                      className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-2xl text-xs font-semibold bg-rose-500/10 text-rose-300 border border-rose-500/20 hover:bg-rose-500/20 transition-all cursor-pointer disabled:opacity-50"
                    >
                      {cancellingId === appt.id ? (
                        <>
                          <Loader2 className="w-3.5 h-3.5 animate-spin" /> Cancelling...
                        </>
                      ) : (
                        <>
                          <XCircle className="w-3.5 h-3.5" /> Cancel Appointment
                        </>
                      )}
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
