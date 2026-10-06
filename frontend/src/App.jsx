import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { MainLayout } from './layouts/MainLayout';
import { Home } from './pages/Home';
import { Login } from './pages/Login';
import { Register } from './pages/Register';
import { DoctorList } from './pages/DoctorList';
import { DoctorDetails } from './pages/DoctorDetails';
import { BookAppointment } from './pages/BookAppointment';
import { MyAppointments } from './pages/MyAppointments';
import { DoctorPortal } from './pages/DoctorPortal';
import { Assistant } from './pages/Assistant';
import { MyDocuments } from './pages/MyDocuments';
import { ClinicalDocumentation } from './pages/ClinicalDocumentation';
import { ProtectedRoute } from './components/ProtectedRoute';

// Public Route wrapper that redirects authenticated users to their role-specific dashboard
const PublicOnlyRoute = ({ children }) => {
  const { user, profile, loading } = useAuth();
  if (loading) return null;
  if (user) {
    if (profile?.role === 'doctor') {
      return <Navigate to="/doctor/appointments" replace />;
    }
    return <Navigate to="/" replace />;
  }
  return children;
};

function AppRoutes() {
  return (
    <Routes>
      {/* Public Authentication Routes */}
      <Route
        path="/login"
        element={
          <PublicOnlyRoute>
            <Login />
          </PublicOnlyRoute>
        }
      />
      <Route
        path="/register"
        element={
          <PublicOnlyRoute>
            <Register />
          </PublicOnlyRoute>
        }
      />

      {/* Protected Application Routes */}
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <MainLayout>
              <Home />
            </MainLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/doctors"
        element={
          <ProtectedRoute>
            <MainLayout>
              <DoctorList />
            </MainLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/doctors/:doctorId"
        element={
          <ProtectedRoute>
            <MainLayout>
              <DoctorDetails />
            </MainLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/book"
        element={
          <ProtectedRoute>
            <MainLayout>
              <BookAppointment />
            </MainLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/book/:doctorId"
        element={
          <ProtectedRoute>
            <MainLayout>
              <BookAppointment />
            </MainLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/appointments"
        element={
          <ProtectedRoute>
            <MainLayout>
              <MyAppointments />
            </MainLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/doctor/appointments"
        element={
          <ProtectedRoute>
            <MainLayout>
              <DoctorPortal />
            </MainLayout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/assistant"
        element={
          <ProtectedRoute>
            <MainLayout>
              <Assistant />
            </MainLayout>
          </ProtectedRoute>
        }
      />
      
      <Route
        path="/documents"
        element={
          <ProtectedRoute>
            <MainLayout>
              <MyDocuments />
            </MainLayout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/clinical-notes"
        element={
          <ProtectedRoute>
            <MainLayout>
              <ClinicalDocumentation />
            </MainLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/clinical-notes/:appointmentId"
        element={
          <ProtectedRoute>
            <MainLayout>
              <ClinicalDocumentation />
            </MainLayout>
          </ProtectedRoute>
        }
      />

      {/* Catch-all redirect to Home */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
