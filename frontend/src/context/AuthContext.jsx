import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { supabase, isSupabaseConfigured } from '../lib/supabase';

const AuthContext = createContext({
  user: null,
  session: null,
  profile: null,
  loading: true,
  isConfigured: false,
  signIn: async () => {},
  signUp: async () => {},
  signOut: async () => {},
  refreshProfile: async () => {},
});

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [session, setSession] = useState(null);
  const [profile, setProfile] = useState(null);
  const [profileError, setProfileError] = useState(null);
  const [loading, setLoading] = useState(true);
  const configured = isSupabaseConfigured();

  const fetchProfile = useCallback(async (userId, userEmail) => {
    if (!userId || !configured) {
      setProfile(null);
      setProfileError(null);
      return null;
    }
    try {
      setProfileError(null);
      const { data, error } = await supabase
        .from('profiles')
        .select('*')
        .eq('id', userId)
        .single();

      if (error) {
        console.warn('Error fetching profile from Supabase:', error.message);
        setProfileError(error.message);
        setProfile(null);
        return null;
      }

      setProfile(data);
      setProfileError(null);
      return data;
    } catch (err) {
      console.error('Unexpected error fetching profile:', err);
      setProfileError(err.message || 'Unexpected error fetching profile');
      setProfile(null);
      return null;
    }
  }, [configured]);

  useEffect(() => {
    if (!configured) {
      setLoading(false);
      return;
    }

    // 1. Get initial session
    const initAuth = async () => {
      try {
        const { data: { session: initialSession } } = await supabase.auth.getSession();
        setSession(initialSession);
        const initialUser = initialSession?.user ?? null;
        setUser(initialUser);

        if (initialUser) {
          await fetchProfile(initialUser.id, initialUser.email);
        }
      } catch (err) {
        console.error('Error getting initial Supabase session:', err);
      } finally {
        setLoading(false);
      }
    };

    initAuth();

    // 2. Listen for auth changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange(async (event, currentSession) => {
      setSession(currentSession);
      const currentUser = currentSession?.user ?? null;
      setUser(currentUser);

      if (currentUser) {
        await fetchProfile(currentUser.id, currentUser.email);
      } else {
        setProfile(null);
      }
      setLoading(false);
    });

    return () => {
      subscription?.unsubscribe();
    };
  }, [configured, fetchProfile]);

  const signIn = async ({ email, password }) => {
    if (!configured) {
      throw new Error('Supabase is not configured. Please add VITE_SUPABASE_URL and VITE_SUPABASE_PUBLISHABLE_KEY to frontend/.env');
    }
    const { data, error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });
    if (error) throw error;
    
    let loadedProfile = null;
    if (data?.user?.id) {
      loadedProfile = await fetchProfile(data.user.id, data.user.email);
    }
    return { ...data, profile: loadedProfile };
  };

  const signUp = async ({ email, password, fullName, role = 'patient' }) => {
    if (!configured) {
      throw new Error('Supabase is not configured. Please add VITE_SUPABASE_URL and VITE_SUPABASE_PUBLISHABLE_KEY to frontend/.env');
    }
    // Security Rule: Only 'patient' or 'doctor' roles are permissible during registration.
    // 'admin' role cannot be self-assigned.
    const sanitizedRole = role === 'doctor' ? 'doctor' : 'patient';

    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: {
          full_name: fullName,
          role: sanitizedRole,
        },
      },
    });
    if (error) throw error;

    let loadedProfile = null;
    if (data?.user?.id) {
      loadedProfile = await fetchProfile(data.user.id, data.user.email);
    }
    return { ...data, profile: loadedProfile, role: sanitizedRole };
  };

  const signOut = async () => {
    if (!configured) {
      setUser(null);
      setSession(null);
      setProfile(null);
      setProfileError(null);
      return;
    }
    const { error } = await supabase.auth.signOut();
    if (error) console.error('Sign out error:', error.message);
    setUser(null);
    setSession(null);
    setProfile(null);
    setProfileError(null);
  };

  const refreshProfile = async () => {
    if (user?.id) {
      return await fetchProfile(user.id, user.email);
    }
    return null;
  };

  const value = {
    user,
    session,
    profile,
    profileError,
    loading,
    isConfigured: configured,
    signIn,
    signUp,
    signOut,
    fetchProfile,
    refreshProfile,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
