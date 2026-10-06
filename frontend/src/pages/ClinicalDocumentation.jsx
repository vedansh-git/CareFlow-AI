import React, { useState, useEffect, useRef } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  getAppointments,
  transcribeAudio,
  generateSoapNote,
  createClinicalNote,
  getClinicalNotes,
  updateClinicalNote,
  approveClinicalNote,
  downloadPrescriptionPdf,
  getPrescriptionData
} from '../services/api';
import {
  FileText,
  Mic,
  Square,
  UploadCloud,
  Sparkles,
  Save,
  CheckCircle2,
  AlertCircle,
  Clock,
  User,
  Calendar,
  Loader2,
  Stethoscope,
  RefreshCw,
  ShieldCheck,
  Check,
  AlertTriangle,
  ChevronRight,
  FolderOpen,
  FileDown,
  Printer,
  Download
} from 'lucide-react';

export const ClinicalDocumentation = () => {
  const { profile } = useAuth();
  const isDoctor = profile?.role === 'doctor';
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  // Consultation & Patient context
  const [appointments, setAppointments] = useState([]);
  const [selectedAppointmentId, setSelectedAppointmentId] = useState('');
  const [selectedAppointment, setSelectedAppointment] = useState(null);

  // Audio Recording State
  const [isRecording, setIsRecording] = useState(false);
  const [recordingDuration, setRecordingDuration] = useState(0);
  const [audioBlob, setAudioBlob] = useState(null);
  const [audioUrl, setAudioUrl] = useState(null);
  const [micPermissionError, setMicPermissionError] = useState('');
  const [isTranscribing, setIsTranscribing] = useState(false);

  // Transcript & SOAP State
  const [transcript, setTranscript] = useState('');
  const [soapSections, setSoapSections] = useState({
    subjective: '',
    objective: '',
    assessment: '',
    plan: ''
  });
  const [currentNoteId, setCurrentNoteId] = useState(null);
  const [noteStatus, setNoteStatus] = useState('new'); // 'new' | 'draft' | 'approved'
  const [reviewedAt, setReviewedAt] = useState(null);
  const [soapModelAttribution, setSoapModelAttribution] = useState(null);

  // UI state
  const [isGeneratingSoap, setIsGeneratingSoap] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isApproving, setIsApproving] = useState(false);
  const [showApprovalModal, setShowApprovalModal] = useState(false);
  const [feedback, setFeedback] = useState({ type: '', message: '' });
  const [previousNotes, setPreviousNotes] = useState([]);
  const [loadingNotes, setLoadingNotes] = useState(false);
  const [isDownloadingPdf, setIsDownloadingPdf] = useState(false);
  const [downloadingNoteId, setDownloadingNoteId] = useState(null);

  // Refs for media recording
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const timerIntervalRef = useRef(null);

  // 1. Initial Data Loading: Appointments and Previous Notes
  useEffect(() => {
    if (!isDoctor) return;

    const loadInitialData = async () => {
      const apptRes = await getAppointments();
      if (apptRes.success && Array.isArray(apptRes.data)) {
        setAppointments(apptRes.data);
        const paramId = searchParams.get('appointmentId');
        if (paramId) {
          const match = apptRes.data.find(a => a.id === paramId);
          if (match) {
            setSelectedAppointmentId(paramId);
            setSelectedAppointment(match);
          }
        }
      }
      loadNotesHistory();
    };

    loadInitialData();
  }, [isDoctor, searchParams]);


  // Update selected appointment when dropdown changes
  useEffect(() => {
    if (selectedAppointmentId && appointments.length > 0) {
      const match = appointments.find(a => a.id === selectedAppointmentId);
      setSelectedAppointment(match || null);
    } else {
      setSelectedAppointment(null);
    }
  }, [selectedAppointmentId, appointments]);

  const loadNotesHistory = async () => {
    setLoadingNotes(true);
    const res = await getClinicalNotes();
    if (res.success) {
      setPreviousNotes(res.data);
    }
    setLoadingNotes(false);
  };

  // 2. Microphone Recording Controls
  const startRecording = async () => {
    setMicPermissionError('');
    setFeedback({ type: '', message: '' });

    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error('Microphone recording is not supported in this browser.');
      }

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioChunksRef.current = [];

      let mimeType = 'audio/webm';
      if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
        mimeType = 'audio/webm;codecs=opus';
      } else if (MediaRecorder.isTypeSupported('audio/ogg')) {
        mimeType = 'audio/ogg';
      }

      const mediaRecorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        const recordedBlob = new Blob(audioChunksRef.current, { type: mimeType });
        setAudioBlob(recordedBlob);
        setAudioUrl(URL.createObjectURL(recordedBlob));
        // Stop all audio tracks to release the mic hardware
        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorder.start(250); // Slice data every 250ms
      setIsRecording(true);
      setRecordingDuration(0);

      // Start duration timer
      timerIntervalRef.current = setInterval(() => {
        setRecordingDuration(prev => prev + 1);
      }, 1000);

    } catch (err) {
      console.error('Microphone access error:', err);
      setMicPermissionError(
        err.name === 'NotAllowedError'
          ? 'Microphone permission was denied. Please allow microphone access in your browser settings to record.'
          : err.message || 'Unable to access microphone device.'
      );
      setIsRecording(false);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current);
      }
    }
  };

  // Format seconds to MM:SS
  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  // 3. Transcribe Audio (Recorded or Uploaded)
  const handleTranscribeAudio = async (blobToTranscribe = audioBlob) => {
    if (!blobToTranscribe) return;

    setIsTranscribing(true);
    setFeedback({ type: '', message: '' });

    const formData = new FormData();
    const filename = `consultation_${Date.now()}.webm`;
    formData.append('file', blobToTranscribe, filename);

    const res = await transcribeAudio(formData);
    setIsTranscribing(false);

    if (res.success) {
      setTranscript(prev => (prev ? `${prev}\n\n${res.data.transcript}` : res.data.transcript));
      setFeedback({
        type: 'success',
        message: 'Audio transcribed successfully. You can review and edit the text below.'
      });
    } else {
      setFeedback({
        type: 'error',
        message: res.error || 'Failed to transcribe audio recording.'
      });
    }
  };

  // Handle manual file upload
  const handleFileUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setAudioBlob(file);
    setAudioUrl(URL.createObjectURL(file));
    handleTranscribeAudio(file);
  };

  // 4. Generate SOAP Note Draft using Gemini LLM
  const handleGenerateSoap = async () => {
    if (!transcript.trim()) {
      setFeedback({ type: 'error', message: 'Please provide or transcribe a consultation transcript first.' });
      return;
    }

    setIsGeneratingSoap(true);
    setFeedback({ type: '', message: '' });

    const patientContext = selectedAppointment
      ? `Patient: ${selectedAppointment.patient_name || 'Patient'}, Date: ${selectedAppointment.appointment_date}, Reason: ${selectedAppointment.reason || 'General consultation'}`
      : 'General Consultation';

    const res = await generateSoapNote({
      transcript: transcript.trim(),
      patient_context: patientContext
    });

    setIsGeneratingSoap(false);

    if (res.success) {
      setSoapSections({
        subjective: res.data.subjective || 'Not documented',
        objective: res.data.objective || 'Not documented',
        assessment: res.data.assessment || 'Not documented',
        plan: res.data.plan || 'Not documented',
      });
      setSoapModelAttribution(res.data.model_attribution || null);
      setFeedback({
        type: 'success',
        message: 'SOAP note draft generated. Please review each section carefully before saving or approving.'
      });
    } else {
      setFeedback({
        type: 'error',
        message: res.error || 'Failed to generate SOAP note draft from transcript.'
      });
    }
  };

  // 5. Save Note Draft
  const handleSaveDraft = async () => {
    if (!transcript.trim()) {
      setFeedback({ type: 'error', message: 'Transcript cannot be empty.' });
      return;
    }

    const patientId = selectedAppointment?.patient_id || '00000000-0000-0000-0000-000000000000';

    setIsSaving(true);
    setFeedback({ type: '', message: '' });

    const payload = {
      patient_id: patientId,
      appointment_id: selectedAppointmentId || null,
      transcript: transcript.trim(),
      subjective: soapSections.subjective || 'Not documented',
      objective: soapSections.objective || 'Not documented',
      assessment: soapSections.assessment || 'Not documented',
      plan: soapSections.plan || 'Not documented',
      status: 'draft'
    };

    let res;
    if (currentNoteId) {
      res = await updateClinicalNote(currentNoteId, payload);
    } else {
      res = await createClinicalNote(payload);
    }

    setIsSaving(false);

    if (res.success) {
      setCurrentNoteId(res.data.id);
      setNoteStatus('draft');
      setFeedback({ type: 'success', message: 'Clinical note draft saved successfully.' });
      loadNotesHistory();
    } else {
      setFeedback({ type: 'error', message: res.error || 'Failed to save clinical note draft.' });
    }
  };

  // 6. Approve and Finalize Note
  const handleApproveNote = async () => {
    if (!currentNoteId) {
      // If note hasn't been saved yet, save first then approve
      const patientId = selectedAppointment?.patient_id || '00000000-0000-0000-0000-000000000000';
      const payload = {
        patient_id: patientId,
        appointment_id: selectedAppointmentId || null,
        transcript: transcript.trim(),
        subjective: soapSections.subjective || 'Not documented',
        objective: soapSections.objective || 'Not documented',
        assessment: soapSections.assessment || 'Not documented',
        plan: soapSections.plan || 'Not documented',
        status: 'approved'
      };
      setIsApproving(true);
      const createRes = await createClinicalNote(payload);
      if (createRes.success) {
        setCurrentNoteId(createRes.data.id);
        setNoteStatus('approved');
        setReviewedAt(createRes.data.reviewed_at || new Date().toISOString());
        setFeedback({ type: 'success', message: 'Clinical note reviewed and officially approved.' });
        setShowApprovalModal(false);
        loadNotesHistory();
      } else {
        setFeedback({ type: 'error', message: createRes.error || 'Failed to approve clinical note.' });
      }
      setIsApproving(false);
      return;
    }

    setIsApproving(true);
    setFeedback({ type: '', message: '' });

    // Update current edits first
    await updateClinicalNote(currentNoteId, {
      transcript: transcript.trim(),
      subjective: soapSections.subjective,
      objective: soapSections.objective,
      assessment: soapSections.assessment,
      plan: soapSections.plan,
    });

    const res = await approveClinicalNote(currentNoteId);
    setIsApproving(false);
    setShowApprovalModal(false);

    if (res.success) {
      setNoteStatus('approved');
      setReviewedAt(res.data.reviewed_at || new Date().toISOString());
      setFeedback({
        type: 'success',
        message: 'Clinical note reviewed and approved. Note is now permanently signed. Doctor Prescription PDF is ready to download.'
      });
      loadNotesHistory();
    } else {
      setFeedback({
        type: 'error',
        message: res.error || 'Failed to approve clinical note.'
      });
    }
  };

  // 7. Download Professional Prescription PDF
  const handleDownloadPrescription = async (targetNoteId = null) => {
    const noteId = targetNoteId || currentNoteId;
    if (!noteId) {
      setFeedback({
        type: 'error',
        message: 'No saved clinical note available to generate prescription.'
      });
      return;
    }

    setIsDownloadingPdf(true);
    setDownloadingNoteId(noteId);
    setFeedback({ type: '', message: '' });

    const res = await downloadPrescriptionPdf(noteId);
    setIsDownloadingPdf(false);
    setDownloadingNoteId(null);

    if (res.success) {
      setFeedback({
        type: 'success',
        message: `Doctor Prescription PDF (${res.filename}) downloaded successfully.`
      });
    } else {
      setFeedback({
        type: 'error',
        message: res.error || 'Failed to generate prescription PDF.'
      });
    }
  };


  // Load a historical note into workspace
  const loadExistingNote = (note) => {
    setCurrentNoteId(note.id);
    setSelectedAppointmentId(note.appointment_id || '');
    setTranscript(note.transcript || '');
    setSoapSections({
      subjective: note.subjective || 'Not documented',
      objective: note.objective || 'Not documented',
      assessment: note.assessment || 'Not documented',
      plan: note.plan || 'Not documented',
    });
    setNoteStatus(note.status || 'draft');
    setReviewedAt(note.reviewed_at || null);
    setFeedback({ type: 'success', message: `Loaded clinical note (${note.status.toUpperCase()})` });
  };

  const handleStartNewNote = () => {
    setCurrentNoteId(null);
    setSelectedAppointmentId('');
    setSelectedAppointment(null);
    setTranscript('');
    setSoapSections({
      subjective: '',
      objective: '',
      assessment: '',
      plan: ''
    });
    setNoteStatus('new');
    setReviewedAt(null);
    setAudioBlob(null);
    setAudioUrl(null);
    setFeedback({ type: '', message: '' });
  };

  // Doctor-only guard screen
  if (!isDoctor) {
    return (
      <div className="max-w-2xl mx-auto py-16 text-center space-y-4">
        <div className="w-16 h-16 rounded-3xl bg-rose-500/10 text-rose-400 border border-rose-500/20 flex items-center justify-center mx-auto">
          <ShieldCheck className="w-8 h-8" />
        </div>
        <h2 className="text-xl font-bold text-white">Physician Clinical Access Required</h2>
        <p className="text-xs text-slate-400 max-w-md mx-auto">
          Clinical documentation and SOAP note generation are restricted to registered healthcare professionals. Patients may not generate or edit clinical records.
        </p>
        <button
          onClick={() => navigate('/')}
          className="px-5 py-2.5 rounded-2xl text-xs font-semibold bg-[#6c5dd3] text-white hover:bg-purple-600 transition-colors shadow-lg shadow-purple-600/20"
        >
          Return to Patient Dashboard
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-8 max-w-7xl mx-auto pb-12">
      {/* Header Banner */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-[#6355d8] via-[#735df2] to-[#8c75ff] p-8 text-white shadow-xl shadow-purple-900/20">
        <div className="absolute top-0 right-0 w-80 h-80 bg-white/10 rounded-full blur-2xl pointer-events-none -mr-20 -mt-20" />
        <div className="relative z-10 flex flex-col sm:flex-row sm:items-center justify-between gap-6">
          <div className="space-y-1.5">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-white/20 text-white backdrop-blur-md">
              <Stethoscope className="w-3.5 h-3.5" /> CareFlow Clinical Documentation Engine
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
              Clinical Voice &amp; SOAP Note Workspace
            </h1>
            <p className="text-xs sm:text-sm text-purple-100/90">
              Ambient conversation capture, speech-to-text transcription, and structured SOAP note drafting.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={handleStartNewNote}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-2xl text-xs font-semibold bg-[#12131d] border border-white/[0.08] text-slate-300 hover:text-white transition-colors cursor-pointer"
            >
              <RefreshCw className="w-3.5 h-3.5" /> New Encounter
            </button>
          </div>
        </div>
      </div>

      {/* Notifications / Alerts */}
      {feedback.message && (
        <div
          className={`p-4 rounded-xl border text-xs flex items-center justify-between gap-3 ${
            feedback.type === 'success'
              ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-300'
              : 'bg-rose-500/10 border-rose-500/20 text-rose-300'
          }`}
        >
          <div className="flex items-center gap-2.5">
            {feedback.type === 'success' ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            ) : (
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
            )}
            <span>{feedback.message}</span>
          </div>
          <button
            onClick={() => setFeedback({ type: '', message: '' })}
            className="text-slate-400 hover:text-white text-xs font-bold"
          >
            &times;
          </button>
        </div>
      )}

      {/* Context Selection Row */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 shadow-xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-center gap-3 w-full md:w-auto">
          <div className="p-2.5 rounded-xl bg-sky-500/10 text-sky-400 border border-sky-500/20">
            <Calendar className="w-4 h-4" />
          </div>
          <div className="flex-1">
            <label className="block text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1">
              Select Patient Consultation / Appointment
            </label>
            <select
              value={selectedAppointmentId}
              onChange={(e) => setSelectedAppointmentId(e.target.value)}
              className="bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500/50 w-full md:w-80"
            >
              <option value="">-- Ad-hoc / Walk-in Consultation --</option>
              {appointments.map((appt) => (
                <option key={appt.id} value={appt.id}>
                  {appt.patient_name || 'Patient'} &bull; {appt.appointment_date} ({appt.start_time})
                </option>
              ))}
            </select>
          </div>
        </div>

        {selectedAppointment && (
          <div className="flex items-center gap-4 bg-slate-950/80 px-4 py-2.5 rounded-xl border border-slate-800 text-xs text-slate-300">
            <div className="flex items-center gap-1.5 text-slate-400">
              <User className="w-3.5 h-3.5 text-sky-400" />
              <strong className="text-white">{selectedAppointment.patient_name || 'Patient'}</strong>
            </div>
            <span>&bull;</span>
            <div className="flex items-center gap-1.5 text-slate-400">
              <Clock className="w-3.5 h-3.5 text-teal-400" />
              <span>{selectedAppointment.start_time} - {selectedAppointment.end_time}</span>
            </div>
            {selectedAppointment.reason && (
              <>
                <span>&bull;</span>
                <span className="text-slate-400 italic">"{selectedAppointment.reason}"</span>
              </>
            )}
          </div>
        )}

        <div className="flex items-center gap-2">
          {noteStatus === 'approved' ? (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <CheckCircle2 className="w-3.5 h-3.5" /> Approved & Signed
            </span>
          ) : (noteStatus === 'draft' || currentNoteId || transcript.trim() || soapSections.subjective.trim()) ? (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">
              <Clock className="w-3.5 h-3.5" /> Draft in Progress
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-sky-500/10 text-sky-400 border border-sky-500/20">
              <FileText className="w-3.5 h-3.5" /> New Encounter
            </span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Column: Audio Recording & Transcript (5 cols) */}
        <div className="lg:col-span-5 space-y-6">
          {/* Audio Capture Card */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 space-y-5 shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h2 className="text-sm font-bold text-white flex items-center gap-2">
                <Mic className="w-4 h-4 text-rose-400" /> Conversation Audio Capture
              </h2>
              <span className="text-[10px] text-slate-400 font-medium">Explicit Consent Required</span>
            </div>

            {/* Mic Permission Error */}
            {micPermissionError && (
              <div className="p-3 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-300 text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
                <span>{micPermissionError}</span>
              </div>
            )}

            {/* Recording Controls & Pulse Widget */}
            <div className="bg-slate-950 p-5 rounded-xl border border-slate-800 flex flex-col items-center justify-center space-y-4 text-center">
              {isRecording ? (
                <div className="space-y-3">
                  <div className="relative flex items-center justify-center">
                    <div className="w-16 h-16 rounded-full bg-rose-500/20 animate-ping absolute" />
                    <div className="w-12 h-12 rounded-full bg-rose-500 text-white flex items-center justify-center relative shadow-lg shadow-rose-500/30">
                      <Mic className="w-6 h-6 animate-pulse" />
                    </div>
                  </div>
                  <div>
                    <div className="text-xl font-mono font-bold text-rose-400">
                      {formatTime(recordingDuration)}
                    </div>
                    <span className="text-[11px] text-slate-400">Recording consultation dialogue...</span>
                  </div>
                </div>
              ) : (
                <div className="space-y-1">
                  <p className="text-xs text-slate-300 font-medium">Ready to record consultation</p>
                  <p className="text-[10px] text-slate-500 max-w-xs">
                    Doctor consent required. Audio is securely processed by local Whisper and immediately deleted.
                  </p>
                </div>
              )}

              <div className="flex items-center gap-3">
                {!isRecording ? (
                  <button
                    onClick={startRecording}
                    className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold bg-rose-500 hover:bg-rose-600 text-white shadow-lg shadow-rose-500/20 transition-all cursor-pointer"
                  >
                    <Mic className="w-4 h-4" /> Start Recording
                  </button>
                ) : (
                  <button
                    onClick={stopRecording}
                    className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold bg-slate-800 hover:bg-slate-700 text-white border border-slate-700 transition-all cursor-pointer"
                  >
                    <Square className="w-4 h-4 text-rose-400" /> Stop Recording
                  </button>
                )}
              </div>
            </div>

            {/* Audio Playback & Manual Transcribe Trigger */}
            {audioUrl && !isRecording && (
              <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-800/80 space-y-3">
                <div className="flex items-center justify-between text-xs text-slate-400">
                  <span>Recorded Audio Clip</span>
                  <button
                    onClick={() => handleTranscribeAudio()}
                    disabled={isTranscribing}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-sky-500/10 text-sky-400 border border-sky-500/20 hover:bg-sky-500/20 transition-all cursor-pointer disabled:opacity-50"
                  >
                    {isTranscribing ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin" /> Transcribing...
                      </>
                    ) : (
                      <>
                        <Sparkles className="w-3.5 h-3.5" /> Transcribe with Whisper
                      </>
                    )}
                  </button>
                </div>
                <audio src={audioUrl} controls className="w-full h-8" />
              </div>
            )}

            {/* Audio File Upload Alternative */}
            <div className="border-t border-slate-800/80 pt-4">
              <label className="block text-[11px] font-semibold text-slate-400 mb-2">
                Or Upload Audio File (.wav, .mp3, .webm, .m4a)
              </label>
              <label className="flex items-center justify-center gap-2 p-3 bg-slate-950 hover:bg-slate-900 border border-dashed border-slate-700 hover:border-slate-500 rounded-xl cursor-pointer transition-all text-xs text-slate-400 hover:text-slate-200">
                <UploadCloud className="w-4 h-4 text-sky-400" />
                <span>Choose consultation audio file</span>
                <input
                  type="file"
                  accept="audio/*,.wav,.mp3,.webm,.ogg,.m4a"
                  onChange={handleFileUpload}
                  className="hidden"
                />
              </label>
            </div>
          </div>

          {/* Editable Transcript Card */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 space-y-4 shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <h2 className="text-sm font-bold text-white flex items-center gap-2">
                  <FileText className="w-4 h-4 text-sky-400" /> Consultation Transcript
                </h2>
                <p className="text-[10px] text-slate-400">Review and correct speech before generating SOAP note</p>
              </div>
              <span className="text-[10px] text-slate-500 font-mono">
                {transcript.split(/\s+/).filter(Boolean).length} words
              </span>
            </div>

            <textarea
              value={transcript}
              onChange={(e) => setTranscript(e.target.value)}
              placeholder="Doctor: Good morning. What brings you in today?&#10;Patient: I have had a sore throat and fever for two days..."
              rows={8}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3.5 text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-sky-500/50 leading-relaxed font-sans resize-y"
            />

            <button
              onClick={handleGenerateSoap}
              disabled={!transcript.trim() || isGeneratingSoap}
              className="w-full inline-flex items-center justify-center gap-2 px-4 py-3 rounded-xl text-xs font-bold bg-gradient-to-r from-sky-500 to-teal-500 text-slate-950 hover:opacity-95 shadow-lg shadow-sky-500/20 disabled:opacity-50 transition-all cursor-pointer"
            >
              {isGeneratingSoap ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin text-slate-950" />
                  Generating Structured SOAP Draft...
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4 text-slate-950" />
                  Generate Structured SOAP Draft
                </>
              )}
            </button>
          </div>
        </div>

        {/* Right Column: SOAP Note Sections & Approval (7 cols) */}
        <div className="lg:col-span-7 space-y-6">
          <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 space-y-6 shadow-xl">
            {/* Header & Disclaimer */}
            <div className="space-y-3 border-b border-slate-800 pb-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div>
                  <h2 className="text-base font-bold text-white flex items-center gap-2">
                    <Stethoscope className="w-4 h-4 text-teal-400" /> SOAP Clinical Encounter Record
                  </h2>
                  <p className="text-xs text-slate-400">
                    Physician-editable structured documentation.
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={handleSaveDraft}
                    disabled={isSaving || !transcript.trim()}
                    className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold bg-slate-950 border border-slate-700 text-slate-200 hover:text-white hover:border-slate-600 transition-all cursor-pointer disabled:opacity-50"
                  >
                    {isSaving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5 text-sky-400" />}
                    Save Draft
                  </button>

                  <button
                    onClick={() => setShowApprovalModal(true)}
                    disabled={isApproving || !transcript.trim() || noteStatus === 'approved'}
                    className={`inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer disabled:opacity-50 ${
                      noteStatus === 'approved'
                        ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 cursor-default'
                        : 'bg-emerald-500 hover:bg-emerald-600 text-white shadow-lg shadow-emerald-500/20'
                    }`}
                  >
                    {noteStatus === 'approved' ? (
                      <>
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> Signed & Approved
                      </>
                    ) : (
                      <>
                        <Check className="w-3.5 h-3.5" /> Approve & Sign Note
                      </>
                    )}
                  </button>

                  {noteStatus === 'approved' && (
                    <button
                      onClick={() => handleDownloadPrescription()}
                      disabled={isDownloadingPdf}
                      className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold bg-teal-500 hover:bg-teal-600 text-white shadow-lg shadow-teal-500/25 transition-all cursor-pointer disabled:opacity-50"
                      title="Download Doctor Prescription PDF (A4 Single-Page Print Ready)"
                    >
                      {isDownloadingPdf && !downloadingNoteId ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <FileDown className="w-3.5 h-3.5" />
                      )}
                      Download Prescription PDF
                    </button>
                  )}
                </div>

              </div>

              {/* AI Draft Disclaimer Banner */}
              <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded-xl text-[11px] text-amber-300/90 flex items-start gap-2.5">
                <AlertTriangle className="w-4 h-4 shrink-0 text-amber-400 mt-0.5" />
                <div>
                  <strong className="font-semibold text-amber-300">AI-Generated Clinical Draft:</strong>
                  <span> This documentation requires physician review and explicit verification before being finalized into the medical record. It is not an automated medical diagnosis or prescription.</span>
                </div>
              </div>

              {/* AI Model Attribution Pill */}
              {soapModelAttribution && (
                <div className="flex flex-wrap items-center justify-between gap-2 px-3.5 py-2 bg-slate-950/80 border border-slate-800 rounded-xl text-xs">
                  <div className="flex items-center gap-2 text-slate-300">
                    <Sparkles className="w-3.5 h-3.5 text-teal-400" />
                    <span className="text-[11px] text-slate-400">Generated by:</span>
                    <span className="font-mono text-[11px] font-medium text-teal-300">
                      {soapModelAttribution.provider} &bull; {soapModelAttribution.model}
                    </span>
                    {soapModelAttribution.fallback_used && (
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                        Fallback model active
                      </span>
                    )}
                  </div>
                  {soapModelAttribution.attempted_models && soapModelAttribution.attempted_models.length > 1 && (
                    <span className="text-[10px] text-slate-500 font-mono">
                      Chain: {soapModelAttribution.attempted_models.join(' → ')}
                    </span>
                  )}
                </div>
              )}
            </div>

            {/* 4 SOAP Sections */}
            <div className="space-y-4">
              {/* Subjective */}
              <div className="bg-slate-950 rounded-xl border border-slate-800 p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-bold text-sky-400 uppercase tracking-wider flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-sky-400" />
                    S — Subjective (Symptoms & Patient History)
                  </label>
                  <span className="text-[10px] text-slate-500">Chief complaint, HPI, reported symptoms</span>
                </div>
                <textarea
                  value={soapSections.subjective}
                  onChange={(e) => setSoapSections({ ...soapSections, subjective: e.target.value })}
                  placeholder="Patient-reported symptoms, duration, and medical history..."
                  rows={3}
                  className="w-full bg-slate-900 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:ring-1 focus:ring-sky-500 leading-relaxed font-sans"
                />
              </div>

              {/* Objective */}
              <div className="bg-slate-950 rounded-xl border border-slate-800 p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-bold text-teal-400 uppercase tracking-wider flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-teal-400" />
                    O — Objective (Physical Exam & Measurements)
                  </label>
                  <span className="text-[10px] text-slate-500">Vital signs, physical exam, documented labs</span>
                </div>
                <textarea
                  value={soapSections.objective}
                  onChange={(e) => setSoapSections({ ...soapSections, objective: e.target.value })}
                  placeholder="Documented vital signs, physical examination findings..."
                  rows={3}
                  className="w-full bg-slate-900 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:ring-1 focus:ring-teal-500 leading-relaxed font-sans"
                />
              </div>

              {/* Assessment */}
              <div className="bg-slate-950 rounded-xl border border-slate-800 p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-bold text-purple-400 uppercase tracking-wider flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-purple-400" />
                    A — Assessment (Physician Clinical Impression)
                  </label>
                  <span className="text-[10px] text-slate-500">Primary diagnosis, differential diagnoses</span>
                </div>
                <textarea
                  value={soapSections.assessment}
                  onChange={(e) => setSoapSections({ ...soapSections, assessment: e.target.value })}
                  placeholder="Clinician assessment or stated diagnostic impression..."
                  rows={3}
                  className="w-full bg-slate-900 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:ring-1 focus:ring-purple-500 leading-relaxed font-sans"
                />
              </div>

              {/* Plan */}
              <div className="bg-slate-950 rounded-xl border border-slate-800 p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-bold text-emerald-400 uppercase tracking-wider flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-emerald-400" />
                    P — Plan (Treatment, Orders & Follow-up)
                  </label>
                  <span className="text-[10px] text-slate-500">Medications, tests ordered, follow-up timing</span>
                </div>
                <textarea
                  value={soapSections.plan}
                  onChange={(e) => setSoapSections({ ...soapSections, plan: e.target.value })}
                  placeholder="Prescribed treatment plan, diagnostic orders, patient counseling, and follow-up..."
                  rows={3}
                  className="w-full bg-slate-900 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:ring-1 focus:ring-emerald-500 leading-relaxed font-sans"
                />
              </div>
            </div>

            {/* Note Status Footer & Prescription Ready Banner */}
            {noteStatus === 'approved' && (
              <div className="space-y-3 pt-2">
                <div className="p-4 bg-gradient-to-r from-teal-950/60 via-slate-900/90 to-emerald-950/60 border border-teal-500/30 rounded-xl flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-lg">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-xl bg-teal-500/20 border border-teal-500/30 flex items-center justify-center shrink-0 text-teal-300">
                      <Stethoscope className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-white">Single-Page Prescription PDF Ready</span>
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-teal-500/20 text-teal-300 border border-teal-500/30">
                          A4 Print-Ready
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-400">
                        Generated strictly from this approved SOAP record and verified doctor/patient profiles.
                      </p>
                    </div>
                  </div>

                  <button
                    onClick={() => handleDownloadPrescription()}
                    disabled={isDownloadingPdf}
                    className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold bg-teal-500 hover:bg-teal-600 text-white shadow-md shadow-teal-500/20 transition-all cursor-pointer disabled:opacity-50 shrink-0"
                  >
                    {isDownloadingPdf && !downloadingNoteId ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <FileDown className="w-3.5 h-3.5" />
                    )}
                    Download PDF
                  </button>
                </div>

                {reviewedAt && (
                  <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-emerald-300 text-xs flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                      <span>Officially signed by Dr. {profile?.full_name || 'Physician'}</span>
                    </div>
                    <span className="text-[10px] text-slate-400 font-mono">
                      {new Date(reviewedAt).toLocaleString()}
                    </span>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Previous Clinical Notes History */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 space-y-4 shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <FolderOpen className="w-4 h-4 text-sky-400" /> Recent Encounter Notes
              </h3>
              <span className="text-xs text-slate-400">{previousNotes.length} Records</span>
            </div>

            {loadingNotes ? (
              <div className="py-6 flex items-center justify-center gap-2 text-xs text-slate-400">
                <Loader2 className="w-4 h-4 animate-spin text-sky-400" /> Loading previous notes...
              </div>
            ) : previousNotes.length === 0 ? (
              <p className="text-xs text-slate-500 text-center py-4">
                No clinical notes recorded yet.
              </p>
            ) : (
              <div className="space-y-2.5 max-h-60 overflow-y-auto pr-1">
                {previousNotes.map((note) => (
                  <div
                    key={note.id}
                    onClick={() => loadExistingNote(note)}
                    className={`p-3 bg-slate-950 rounded-xl border transition-all cursor-pointer flex items-center justify-between text-xs ${
                      note.id === currentNoteId
                        ? 'border-sky-500/50 bg-sky-500/5'
                        : 'border-slate-800 hover:border-slate-700'
                    }`}
                  >
                    <div className="space-y-0.5">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-slate-200">
                          {note.patient_name || 'Patient'}
                        </span>
                        <span
                          className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase ${
                            note.status === 'approved'
                              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                              : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                          }`}
                        >
                          {note.status}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-400 truncate max-w-sm">
                        {note.assessment || note.transcript}
                      </p>
                    </div>

                    <div className="flex items-center gap-2 text-slate-500">
                      {note.status === 'approved' && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDownloadPrescription(note.id);
                          }}
                          disabled={isDownloadingPdf && downloadingNoteId === note.id}
                          title="Download Prescription PDF"
                          className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-teal-500/10 hover:bg-teal-500/25 text-teal-300 border border-teal-500/30 text-[11px] font-medium transition-colors cursor-pointer disabled:opacity-50"
                        >
                          {isDownloadingPdf && downloadingNoteId === note.id ? (
                            <Loader2 className="w-3 h-3 animate-spin" />
                          ) : (
                            <FileDown className="w-3 h-3 text-teal-400" />
                          )}
                          <span>PDF</span>
                        </button>
                      )}
                      <span className="text-[10px]">
                        {new Date(note.created_at).toLocaleDateString()}
                      </span>
                      <ChevronRight className="w-4 h-4 text-slate-600" />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

        </div>
      </div>

      {/* Explicit Doctor Approval Confirmation Modal */}
      {showApprovalModal && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 space-y-5 shadow-2xl">
            <div className="flex items-center gap-3 text-emerald-400">
              <div className="w-10 h-10 rounded-full bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center shrink-0">
                <CheckCircle2 className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white">Approve & Sign Clinical Note</h3>
                <p className="text-xs text-slate-400">Formal physician verification</p>
              </div>
            </div>

            <div className="space-y-3 bg-slate-950 p-4 rounded-xl border border-slate-800 text-xs text-slate-300">
              <p className="font-medium text-slate-200">
                By confirming, you certify that:
              </p>
              <ul className="list-disc pl-5 space-y-1.5 text-slate-400">
                <li>You have thoroughly reviewed all Subjective, Objective, Assessment, and Plan sections.</li>
                <li>All clinical details and medication orders are accurate and medically validated.</li>
                <li>This note will be marked as reviewed and accessible in the patient's verified health records.</li>
              </ul>
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={() => setShowApprovalModal(false)}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-950 border border-slate-800 text-slate-400 hover:text-white transition-colors cursor-pointer"
              >
                Cancel & Continue Editing
              </button>

              <button
                onClick={handleApproveNote}
                disabled={isApproving}
                className="inline-flex items-center gap-2 px-5 py-2 rounded-xl text-xs font-bold bg-emerald-500 hover:bg-emerald-600 text-white shadow-lg shadow-emerald-500/20 transition-all cursor-pointer"
              >
                {isApproving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                Confirm & Sign Note
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
