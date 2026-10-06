import axios from 'axios';
import { API_BASE_URL } from '../utils/constants';
import { supabase } from '../lib/supabase';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});


// Request Interceptor: Automatically attach Supabase Auth JWT token if session exists
apiClient.interceptors.request.use(
  async (config) => {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (session?.access_token) {
        config.headers.Authorization = `Bearer ${session.access_token}`;
      }
    } catch (err) {
      console.warn('Error attaching Supabase token to API request:', err);
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response Interceptor: Automatically refresh Supabase Auth token on 401 and retry once
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      try {
        const { data: { session }, error: refreshError } = await supabase.auth.refreshSession();
        if (!refreshError && session?.access_token) {
          originalRequest.headers.Authorization = `Bearer ${session.access_token}`;
          return apiClient(originalRequest);
        }
      } catch (refreshErr) {
        console.warn('Failed to refresh Supabase session on 401:', refreshErr);
      }
    }
    return Promise.reject(error);
  }
);


export const checkHealth = async () => {
  try {
    const response = await apiClient.get('/api/health');
    return {
      success: true,
      data: response.data,
    };
  } catch (error) {
    return {
      success: false,
      error: error.response?.data?.detail || error.message || 'Unable to connect to backend service',
    };
  }
};

export const getMe = async () => {
  try {
    const response = await apiClient.get('/api/me');
    return {
      success: true,
      data: response.data,
    };
  } catch (error) {
    return {
      success: false,
      status: error.response?.status || 500,
      error: error.response?.data?.detail || error.message || 'Failed to authenticate with FastAPI backend',
    };
  }
};

// ----------------------------------------------------------------------
// Doctor APIs
// ----------------------------------------------------------------------

export const getDoctors = async () => {
  let allDoctors = [];
  
  // 1. Try Supabase direct query first if configured
  try {
    const { data: supaDocs, error: supaErr } = await supabase
      .from('doctors')
      .select(`
        id,
        profile_id,
        specialty,
        qualification,
        bio,
        is_active,
        profiles (
          full_name
        )
      `)
      .eq('is_active', true);

    if (!supaErr && supaDocs && supaDocs.length > 0) {
      allDoctors = supaDocs.map((d) => ({
        id: d.id,
        profile_id: d.profile_id,
        specialty: d.specialty,
        qualification: d.qualification,
        bio: d.bio,
        is_active: d.is_active,
        full_name: d.profiles?.full_name || 'Doctor',
      }));
    }
  } catch (err) {
    console.warn('Supabase getDoctors error, falling back to backend:', err);
  }

  // 2. Fetch from FastAPI backend and merge
  try {
    const response = await apiClient.get('/api/doctors');
    if (response.data) {
      const existingProfileIds = new Set(allDoctors.map(d => d.profile_id));
      for (const doc of response.data) {
        if (!existingProfileIds.has(doc.profile_id)) {
          allDoctors.push(doc);
        }
      }
    }
    return { success: true, data: allDoctors };
  } catch (error) {
    if (allDoctors.length > 0) {
      return { success: true, data: allDoctors };
    }
    return {
      success: false,
      status: error.response?.status || 500,
      error: error.response?.data?.detail || error.message || 'Failed to fetch doctors',
    };
  }
};

export const getDoctorById = async (doctorId) => {
  // 1. Try Supabase direct query first
  try {
    const { data: supaDoc, error: supaErr } = await supabase
      .from('doctors')
      .select(`
        id,
        profile_id,
        specialty,
        qualification,
        bio,
        is_active,
        profiles (
          full_name
        )
      `)
      .eq('id', doctorId)
      .single();

    if (!supaErr && supaDoc) {
      return {
        success: true,
        data: {
          id: supaDoc.id,
          profile_id: supaDoc.profile_id,
          specialty: supaDoc.specialty,
          qualification: supaDoc.qualification,
          bio: supaDoc.bio,
          is_active: supaDoc.is_active,
          full_name: supaDoc.profiles?.full_name || 'Doctor',
        },
      };
    }
  } catch (err) {
    console.warn('Supabase getDoctorById error, falling back to backend:', err);
  }

  // 2. Fallback to FastAPI backend
  try {
    const response = await apiClient.get(`/api/doctors/${doctorId}`);
    return { success: true, data: response.data };
  } catch (error) {
    return {
      success: false,
      status: error.response?.status || 500,
      error: error.response?.data?.detail || error.message || 'Failed to fetch doctor details',
    };
  }
};

export const getDoctorAvailability = async (doctorId) => {
  // 1. Try Supabase direct query first
  try {
    const { data: slots, error: supaErr } = await supabase
      .from('doctor_availability')
      .select('*')
      .eq('doctor_id', doctorId)
      .eq('is_active', true)
      .order('day_of_week', { ascending: true })
      .order('start_time', { ascending: true });

    if (!supaErr && slots) {
      return { success: true, data: slots };
    }
  } catch (err) {
    console.warn('Supabase getDoctorAvailability error, falling back to backend:', err);
  }

  // 2. Fallback to FastAPI backend
  try {
    const response = await apiClient.get(`/api/doctors/${doctorId}/availability`);
    return { success: true, data: response.data };
  } catch (error) {
    return {
      success: false,
      status: error.response?.status || 500,
      error: error.response?.data?.detail || error.message || 'Failed to fetch doctor schedule',
    };
  }
};

// ----------------------------------------------------------------------
// Appointment APIs
// ----------------------------------------------------------------------

export const getAppointments = async () => {
  let allAppts = [];

  // 1. Query Supabase appointments under active user RLS
  try {
    const { data: appts, error } = await supabase
      .from('appointments')
      .select(`
        *,
        doctors (
          specialty,
          profiles ( full_name )
        ),
        patients (
          profiles ( full_name )
        )
      `)
      .order('appointment_date', { ascending: true })
      .order('start_time', { ascending: true });

    if (!error && Array.isArray(appts)) {
      allAppts = appts.map((a) => ({
        ...a,
        doctor_name: a.doctors?.profiles?.full_name || 'Doctor',
        doctor_specialty: a.doctors?.specialty || 'General',
        patient_name: a.patients?.profiles?.full_name || 'Patient',
      }));
    }
  } catch (err) {
    console.warn('Supabase getAppointments error:', err);
  }

  // 2. Query FastAPI backend appointments (which is strictly isolated to current authenticated user)
  try {
    const response = await apiClient.get('/api/appointments');
    if (response.data && Array.isArray(response.data)) {
      const existingIds = new Set(allAppts.map((a) => a.id));
      for (const appt of response.data) {
        if (!existingIds.has(appt.id)) {
          allAppts.push(appt);
        }
      }
    }
  } catch (error) {
    if (allAppts.length === 0) {
      console.warn('FastAPI getAppointments fallback error:', error);
    }
  }

  // Chronologically sort all retrieved appointments
  allAppts.sort((a, b) => {
    const timeA = `${a.appointment_date || '9999-99-99'}T${a.start_time || '00:00:00'}`;
    const timeB = `${b.appointment_date || '9999-99-99'}T${b.start_time || '00:00:00'}`;
    return timeA.localeCompare(timeB);
  });

  return { success: true, data: allAppts };
};

export const createAppointment = async ({ doctor_id, appointment_date, start_time, end_time, reason }) => {
  let createdAppt = null;

  // 1. Try creating in Supabase if session exists
  try {
    const { data: { user } } = await supabase.auth.getUser();
    if (user) {
      let patientId = null;
      const { data: patient } = await supabase
        .from('patients')
        .select('id')
        .eq('profile_id', user.id)
        .maybeSingle();

      if (patient?.id) {
        patientId = patient.id;
      } else {
        const { data: newPat } = await supabase
          .from('patients')
          .insert({ profile_id: user.id })
          .select('id')
          .maybeSingle();
        if (newPat?.id) patientId = newPat.id;
      }

      if (patientId) {
        const { data: newAppt, error: supaErr } = await supabase
          .from('appointments')
          .insert({
            patient_id: patientId,
            doctor_id,
            appointment_date,
            start_time,
            end_time,
            reason: reason || 'General Consultation',
            status: 'scheduled',
          })
          .select()
          .maybeSingle();

        if (!supaErr && newAppt) {
          createdAppt = newAppt;
        }
      }
    }
  } catch (err) {
    console.warn('Supabase createAppointment error:', err);
  }

  // 2. Always persist to FastAPI backend to ensure backend data store and AI agents stay in sync
  try {
    const response = await apiClient.post('/api/appointments', {
      doctor_id,
      appointment_date,
      start_time,
      end_time,
      reason,
    });
    if (response.data) {
      return { success: true, data: createdAppt || response.data };
    }
  } catch (error) {
    if (createdAppt) {
      return { success: true, data: createdAppt };
    }
    return {
      success: false,
      status: error.response?.status || 500,
      error: error.response?.data?.detail || error.message || 'Failed to book appointment',
    };
  }

  return { success: true, data: createdAppt };
};

export const cancelAppointment = async (appointmentId) => {
  try {
    const { data, error: supaErr } = await supabase
      .from('appointments')
      .update({ status: 'cancelled' })
      .eq('id', appointmentId)
      .select();

    if (!supaErr && data && data.length > 0) {
       return { success: true, data: data[0] };
    }
  } catch (err) {}

  try {
    const response = await apiClient.patch(`/api/appointments/${appointmentId}/cancel`);
    return { success: true, data: response.data };
  } catch (error) {
    return {
      success: false,
      status: error.response?.status || 500,
      error: error.response?.data?.detail || error.message || 'Failed to cancel appointment',
    };
  }
};

// ----------------------------------------------------------------------
// Doctor Self-Management APIs
// ----------------------------------------------------------------------

export const getDoctorMe = async () => {
  // 1. Try Supabase direct query first
  try {
    const { data: { user } } = await supabase.auth.getUser();
    if (user) {
      const { data: supaDoc, error: supaErr } = await supabase
        .from('doctors')
        .select(`
          id,
          profile_id,
          specialty,
          qualification,
          bio,
          is_active,
          profiles (
            full_name
          )
        `)
        .eq('profile_id', user.id)
        .single();

      if (!supaErr && supaDoc) {
        return {
          success: true,
          data: {
            id: supaDoc.id,
            profile_id: supaDoc.profile_id,
            specialty: supaDoc.specialty,
            qualification: supaDoc.qualification,
            bio: supaDoc.bio,
            is_active: supaDoc.is_active,
            full_name: supaDoc.profiles?.full_name || 'Doctor',
          },
        };
      }
    }
  } catch (err) {
    console.warn('Supabase getDoctorMe error, falling back to backend:', err);
  }

  // 2. Fallback to FastAPI backend
  try {
    const response = await apiClient.get('/api/doctor/me');
    return { success: true, data: response.data };
  } catch (error) {
    return {
      success: false,
      status: error.response?.status || 500,
      error: error.response?.data?.detail || error.message || 'Failed to load doctor profile',
    };
  }
};

export const getDoctorMeAvailability = async () => {
  // 1. Try Supabase direct query first
  try {
    const { data: { user } } = await supabase.auth.getUser();
    if (user) {
      const { data: supaDoc } = await supabase
        .from('doctors')
        .select('id')
        .eq('profile_id', user.id)
        .single();

      if (supaDoc?.id) {
        const { data: slots, error: slotErr } = await supabase
          .from('doctor_availability')
          .select('*')
          .eq('doctor_id', supaDoc.id)
          .order('day_of_week', { ascending: true })
          .order('start_time', { ascending: true });

        if (!slotErr && slots) {
          return { success: true, data: slots };
        }
      }
    }
  } catch (err) {
    console.warn('Supabase getDoctorMeAvailability error, falling back to backend:', err);
  }

  // 2. Fallback to FastAPI backend
  try {
    const response = await apiClient.get('/api/doctor/me/availability');
    return { success: true, data: response.data };
  } catch (error) {
    return {
      success: false,
      status: error.response?.status || 500,
      error: error.response?.data?.detail || error.message || 'Failed to load availability slots',
    };
  }
};

export const addDoctorMeAvailability = async (payload) => {
  // 1. Try Supabase direct insert first
  try {
    const { data: { user } } = await supabase.auth.getUser();
    if (user) {
      const { data: supaDoc } = await supabase
        .from('doctors')
        .select('id')
        .eq('profile_id', user.id)
        .single();

      if (supaDoc?.id) {
        const { data: newSlot, error: insertErr } = await supabase
          .from('doctor_availability')
          .insert({
            doctor_id: supaDoc.id,
            day_of_week: payload.day_of_week,
            start_time: payload.start_time,
            end_time: payload.end_time,
            is_active: payload.is_active ?? true,
          })
          .select()
          .single();

        if (!insertErr && newSlot) {
          return { success: true, data: newSlot };
        }
      }
    }
  } catch (err) {
    console.warn('Supabase addDoctorMeAvailability error, falling back to backend:', err);
  }

  // 2. Fallback to FastAPI backend
  try {
    const response = await apiClient.post('/api/doctor/me/availability', payload);
    return { success: true, data: response.data };
  } catch (error) {
    return {
      success: false,
      status: error.response?.status || 500,
      error: error.response?.data?.detail || error.message || 'Failed to add availability',
    };
  }
};

export const deleteDoctorMeAvailability = async (availabilityId) => {
  // 1. Try Supabase direct delete first
  try {
    const { error: delErr } = await supabase
      .from('doctor_availability')
      .delete()
      .eq('id', availabilityId);

    if (!delErr) {
      return { success: true, data: { message: 'Slot deleted successfully' } };
    }
  } catch (err) {
    console.warn('Supabase deleteDoctorMeAvailability error, falling back to backend:', err);
  }

  // 2. Fallback to FastAPI backend
  try {
    const response = await apiClient.delete(`/api/doctor/me/availability/${availabilityId}`);
    return { success: true, data: response.data };
  } catch (error) {
    return {
      success: false,
      status: error.response?.status || 500,
      error: error.response?.data?.detail || error.message || 'Failed to delete availability',
    };
  }
};

// ----------------------------------------------------------------------
// Assistant APIs
// ----------------------------------------------------------------------

export const chatWithAssistant = async (message, history = []) => {
  try {
    const response = await apiClient.post(
      '/api/assistant/chat',
      {
        message,
        history,
      },
      {
        timeout: 60000, // 60s dedicated timeout for RAG + LLM inference
      }
    );
    return { success: true, data: response.data };
  } catch (error) {
    const isTimeout = error.code === 'ECONNABORTED' || error.message?.includes('timeout');
    const errMsg = isTimeout
      ? 'The assistant took longer than expected to respond. Please try again.'
      : (error.response?.data?.detail || error.message || 'Failed to communicate with assistant');

    return {
      success: false,
      status: error.response?.status || (isTimeout ? 504 : 500),
      error: errMsg,
    };
  }
};


// ----------------------------------------------------------------------
// Clinical Documentation & SOAP Notes APIs
// ----------------------------------------------------------------------

export const transcribeAudio = async (formData) => {
  try {
    const response = await apiClient.post('/api/clinical-notes/transcribe', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      timeout: 60000, // 60s for STT
    });
    return { success: true, data: response.data };
  } catch (error) {
    const isTimeout = error.code === 'ECONNABORTED' || error.message?.includes('timeout');
    const errMsg = isTimeout
      ? 'Audio transcription timed out. Please try a shorter recording or type your transcript directly.'
      : (error.response?.data?.detail || error.message || 'Failed to transcribe audio consultation');

    return {
      success: false,
      status: error.response?.status || (isTimeout ? 504 : 500),
      error: errMsg,
    };
  }
};

export const generateSoapNote = async ({ transcript, patient_context }) => {
  try {
    const response = await apiClient.post(
      '/api/clinical-notes/generate-soap',
      {
        transcript,
        patient_context,
      },
      {
        timeout: 60000, // 60s for LLM generation
      }
    );
    return { success: true, data: response.data };
  } catch (error) {
    const isTimeout = error.code === 'ECONNABORTED' || error.message?.includes('timeout');
    const errMsg = isTimeout
      ? 'SOAP note generation timed out. Please try again.'
      : (error.response?.data?.detail || error.message || 'Failed to generate SOAP note draft');

    return {
      success: false,
      status: error.response?.status || (isTimeout ? 504 : 500),
      error: errMsg,
    };
  }
};

export const createClinicalNote = async (payload) => {
  try {
    const response = await apiClient.post('/api/clinical-notes', payload);
    return { success: true, data: response.data };
  } catch (error) {
    return {
      success: false,
      status: error.response?.status || 500,
      error: error.response?.data?.detail || error.message || 'Failed to save clinical note',
    };
  }
};

export const getClinicalNotes = async (params = {}) => {
  try {
    const response = await apiClient.get('/api/clinical-notes', { params });
    return { success: true, data: response.data };
  } catch (error) {
    return {
      success: false,
      status: error.response?.status || 500,
      error: error.response?.data?.detail || error.message || 'Failed to fetch clinical notes',
    };
  }
};

export const getClinicalNote = async (noteId) => {
  try {
    const response = await apiClient.get(`/api/clinical-notes/${noteId}`);
    return { success: true, data: response.data };
  } catch (error) {
    return {
      success: false,
      status: error.response?.status || 500,
      error: error.response?.data?.detail || error.message || 'Failed to fetch clinical note details',
    };
  }
};

export const updateClinicalNote = async (noteId, payload) => {
  try {
    const response = await apiClient.put(`/api/clinical-notes/${noteId}`, payload);
    return { success: true, data: response.data };
  } catch (error) {
    return {
      success: false,
      status: error.response?.status || 500,
      error: error.response?.data?.detail || error.message || 'Failed to update clinical note',
    };
  }
};

export const approveClinicalNote = async (noteId) => {
  try {
    const response = await apiClient.post(`/api/clinical-notes/${noteId}/approve`);
    return { success: true, data: response.data };
  } catch (error) {
    return {
      success: false,
      status: error.response?.status || 500,
      error: error.response?.data?.detail || error.message || 'Failed to approve clinical note',
    };
  }
};

export const downloadPrescriptionPdf = async (noteId) => {
  try {
    const response = await apiClient.get(`/api/clinical-notes/${noteId}/prescription-pdf`, {
      responseType: 'blob',
    });

    // Extract filename from Content-Disposition header if available
    let filename = `Prescription_${noteId.slice(0, 8)}.pdf`;
    const disposition = response.headers['content-disposition'];
    if (disposition && disposition.includes('filename=')) {
      const match = disposition.match(/filename="?([^"]+)"?/);
      if (match && match[1]) {
        filename = match[1];
      }
    }

    // Create a Blob from the PDF stream and trigger browser download
    const blob = new Blob([response.data], { type: 'application/pdf' });
    const blobUrl = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = blobUrl;
    link.setAttribute('download', filename);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(blobUrl);

    return { success: true, filename };
  } catch (error) {
    let errorMsg = 'Failed to download prescription PDF.';
    if (error.response?.data instanceof Blob) {
      try {
        const text = await error.response.data.text();
        const json = JSON.parse(text);
        if (json.detail) errorMsg = json.detail;
      } catch (e) {
        // ignore parse error
      }
    } else if (error.response?.data?.detail) {
      errorMsg = error.response.data.detail;
    } else if (error.message) {
      errorMsg = error.message;
    }
    return {
      success: false,
      status: error.response?.status || 500,
      error: errorMsg,
    };
  }
};

export const getPrescriptionData = async (noteId) => {
  try {
    const response = await apiClient.get(`/api/clinical-notes/${noteId}/prescription-data`);
    return { success: true, data: response.data };
  } catch (error) {
    return {
      success: false,
      status: error.response?.status || 500,
      error: error.response?.data?.detail || error.message || 'Failed to fetch prescription data',
    };
  }
};


// ----------------------------------------------------------------------
// Appointment AI Agent API (Step 7 - Groq Tool-Calling Agent)
// ----------------------------------------------------------------------

export const chatWithAppointmentAgent = async (messages) => {
  try {
    const response = await apiClient.post('/api/agent/appointment-chat', { messages });
    return {
      success: true,
      data: response.data,
    };
  } catch (error) {
    return {
      success: false,
      status: error.response?.status || 500,
      error: error.response?.data?.detail || error.message || 'Failed to communicate with Appointment AI Agent',
    };
  }
};

export default apiClient;


