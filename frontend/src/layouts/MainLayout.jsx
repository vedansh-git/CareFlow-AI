import React, { useState, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { getAppointments } from '../services/api';
import {
  LayoutDashboard,
  Users,
  Calendar,
  Sparkles,
  FolderOpen,
  FileText,
  Briefcase,
  LogOut,
  ChevronLeft,
  ChevronRight,
  Menu,
  X,
  Search,
  CalendarDays,
  Shield,
  Star,
  HelpCircle,
  Home,
} from 'lucide-react';

export const MainLayout = ({ children }) => {
  const { user, profile, signOut } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  // Sidebar collapse state
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [appointmentCount, setAppointmentCount] = useState(null);

  const isDoctor = profile?.role === 'doctor';
  const role = profile?.role || 'patient';

  // Fetch appointment count for sidebar badge
  useEffect(() => {
    let isMounted = true;
    const fetchBadgeData = async () => {
      if (user) {
        try {
          const res = await getAppointments();
          if (res.success && Array.isArray(res.data) && isMounted) {
            const active = res.data.filter((a) => a.status === 'scheduled' || a.status === 'confirmed');
            setAppointmentCount(active.length);
          }
        } catch (e) {
          // ignore error for badge
        }
      }
    };
    fetchBadgeData();
    return () => {
      isMounted = false;
    };
  }, [user, location.pathname]);

  // Close mobile drawer on route change
  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  // Navigation configuration based on authoritative role
  const navItems = isDoctor
    ? [
        { path: '/', label: 'Dashboard', icon: LayoutDashboard },
        {
          path: '/doctor/appointments',
          label: 'Doctor Portal',
          icon: Briefcase,
          badge: appointmentCount > 0 ? appointmentCount : null,
          badgeColor: 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30',
        },
        { path: '/clinical-notes', label: 'Clinical Notes', icon: FileText },
        { path: '/assistant', label: 'AI Assistant', icon: Sparkles },
        { path: '/documents', label: 'My Documents', icon: FolderOpen },
      ]
    : [
        { path: '/', label: 'Dashboard', icon: LayoutDashboard },
        { path: '/doctors', label: 'Doctors', icon: Users },
        {
          path: '/appointments',
          label: 'My Appointments',
          icon: Calendar,
          badge: appointmentCount > 0 ? appointmentCount : null,
          badgeColor: 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30',
        },
        { path: '/assistant', label: 'AI Assistant', icon: Sparkles },
        { path: '/documents', label: 'My Documents', icon: FolderOpen },
      ];

  const secondaryItems = [
    { label: 'Documentation', icon: HelpCircle, onClick: () => navigate('/documents') },
  ];

  // Dynamic formatted date
  const todayFormatted = new Intl.DateTimeFormat('en-US', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(new Date());

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    if (isDoctor) {
      navigate('/doctor/appointments');
    } else {
      navigate('/doctors');
    }
  };

  const displayName = profile?.full_name || user?.email?.split('@')[0] || 'CareFlow User';
  const roleLabel = isDoctor ? 'Physician Specialist' : 'Verified Patient';

  return (
    <div className="min-h-screen bg-[#0c0d14] text-slate-100 flex font-sans overflow-x-hidden">
      {/* Mobile Backdrop */}
      {mobileOpen && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* LEFT SIDEBAR */}
      <aside
        className={`fixed top-0 bottom-0 left-0 z-50 flex flex-col bg-[#12131c] border-r border-white/[0.07] transition-all duration-300 ease-in-out ${
          mobileOpen ? 'translate-x-0 w-64' : '-translate-x-full lg:translate-x-0'
        } ${collapsed ? 'lg:w-20' : 'lg:w-64'}`}
      >
        {/* Sidebar Header: Brand / Logo */}
        <div className="h-20 flex items-center justify-between px-5 border-b border-white/[0.06]">
          <Link to="/" className="flex items-center gap-3 group overflow-hidden">
            <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-violet-600 via-purple-600 to-indigo-500 flex items-center justify-center text-white font-bold shadow-lg shadow-purple-600/30 shrink-0 group-hover:scale-105 transition-transform">
              <svg className="w-6 h-6 fill-current" viewBox="0 0 24 24">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 14.5h-2v-3.5H7.5v-2H11V7.5h2v3.5h3.5v2H13v3.5z"/>
              </svg>
            </div>
            {(!collapsed || mobileOpen) && (
              <div className="flex flex-col">
                <span className="text-lg font-bold tracking-tight text-white flex items-center gap-1.5">
                  CareFlow<span className="text-purple-400">.AI</span>
                </span>
                <span className="text-[10px] font-medium text-slate-400 tracking-wider uppercase">
                  Clinical Workspace
                </span>
              </div>
            )}
          </Link>

          {/* Mobile close button */}
          <button
            onClick={() => setMobileOpen(false)}
            className="lg:hidden p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/5"
            aria-label="Close menu"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Workspace Label */}
        {(!collapsed || mobileOpen) && (
          <div className="px-6 pt-6 pb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
            Workspace
          </div>
        )}

        {/* Primary Navigation List */}
        <div className="flex-1 px-3 py-2 space-y-1.5 overflow-y-auto">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive =
              item.path === '/'
                ? location.pathname === '/'
                : location.pathname.startsWith(item.path);

            return (
              <Link
                key={item.path}
                to={item.path}
                title={collapsed && !mobileOpen ? item.label : undefined}
                className={`relative flex items-center gap-3.5 px-3.5 py-3 rounded-2xl text-sm font-medium transition-all group ${
                  isActive
                    ? 'bg-[#6c5dd3] text-white shadow-lg shadow-purple-600/30'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]'
                } ${collapsed && !mobileOpen ? 'justify-center px-0' : ''}`}
              >
                <Icon
                  className={`w-5 h-5 shrink-0 transition-transform group-hover:scale-110 ${
                    isActive ? 'text-white' : 'text-slate-400 group-hover:text-purple-300'
                  }`}
                />

                {(!collapsed || mobileOpen) && (
                  <span className="truncate flex-1 font-medium">{item.label}</span>
                )}

                {(!collapsed || mobileOpen) && item.badge && (
                  <span
                    className={`px-2 py-0.5 rounded-full text-[11px] font-bold ${
                      isActive ? 'bg-white/20 text-white' : item.badgeColor
                    }`}
                  >
                    {item.badge}
                  </span>
                )}

                {/* Collapsed active dot indicator */}
                {collapsed && !mobileOpen && isActive && (
                  <span className="absolute right-1.5 top-1/2 -translate-y-1/2 w-1.5 h-1.5 rounded-full bg-white shadow-sm" />
                )}
              </Link>
            );
          })}

          {/* Secondary Nav Divider */}
          <div className="pt-4 pb-2">
            <div className="border-t border-white/[0.06] my-2" />
            {(!collapsed || mobileOpen) && (
              <div className="px-3 py-1 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                Support & Tools
              </div>
            )}
          </div>

          {secondaryItems.map((item, idx) => {
            const Icon = item.icon;
            return (
              <button
                key={idx}
                onClick={item.onClick}
                title={collapsed && !mobileOpen ? item.label : undefined}
                className={`w-full flex items-center gap-3.5 px-3.5 py-2.5 rounded-xl text-xs font-medium text-slate-400 hover:text-slate-200 hover:bg-white/[0.04] transition-all group ${
                  collapsed && !mobileOpen ? 'justify-center px-0' : ''
                }`}
              >
                <Icon className="w-4 h-4 shrink-0 text-slate-400 group-hover:text-purple-300" />
                {(!collapsed || mobileOpen) && <span className="truncate">{item.label}</span>}
              </button>
            );
          })}

          {/* Sign Out Action in Sidebar */}
          <button
            onClick={signOut}
            title={collapsed && !mobileOpen ? 'Sign Out' : undefined}
            className={`w-full flex items-center gap-3.5 px-3.5 py-2.5 rounded-xl text-xs font-medium text-rose-400/90 hover:text-rose-300 hover:bg-rose-500/10 transition-all group ${
              collapsed && !mobileOpen ? 'justify-center px-0' : ''
            }`}
          >
            <LogOut className="w-4 h-4 shrink-0 text-rose-400" />
            {(!collapsed || mobileOpen) && <span>Log out</span>}
          </button>
        </div>

        {/* Sidebar Collapse Toggle Button (Desktop) */}
        <div className="hidden lg:flex items-center justify-end px-4 py-2 border-t border-white/[0.04]">
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="p-2 rounded-xl bg-white/[0.03] text-slate-400 hover:text-white hover:bg-white/[0.08] transition-colors"
            title={collapsed ? 'Expand Sidebar' : 'Collapse Sidebar'}
          >
            {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          </button>
        </div>

        {/* Sidebar Footer: User Card (Inspired by Cure.Med doctor profile card) */}
        <div className="p-3 border-t border-white/[0.06] bg-[#0e0f17]/90">
          <div
            className={`flex items-center gap-3 p-2.5 rounded-2xl bg-[#181926] border border-white/[0.07] ${
              collapsed && !mobileOpen ? 'justify-center p-2' : ''
            }`}
          >
            <div className="relative shrink-0">
              <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-purple-500 to-indigo-600 flex items-center justify-center font-bold text-xs text-white uppercase shadow-md shadow-purple-600/20">
                {displayName.charAt(0)}
              </div>
              <span className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-emerald-500 border-2 border-[#181926]" />
            </div>

            {(!collapsed || mobileOpen) && (
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-bold text-slate-100 truncate">{displayName}</p>
                  <div className="flex items-center gap-0.5 text-amber-400 text-[10px] font-bold">
                    <Star className="w-3 h-3 fill-amber-400 text-amber-400" />
                    <span>5.0</span>
                  </div>
                </div>
                <p className="text-[10px] text-purple-300 font-medium truncate capitalize">
                  {roleLabel}
                </p>
              </div>
            )}
          </div>
        </div>
      </aside>

      {/* MAIN CONTAINER */}
      <div
        className={`flex-1 flex flex-col min-w-0 transition-all duration-300 ease-in-out ${
          collapsed ? 'lg:ml-20' : 'lg:ml-64'
        }`}
      >
        {/* TOP BAR */}
        <header className="sticky top-0 z-30 h-20 bg-[#0c0d14]/85 backdrop-blur-xl border-b border-white/[0.07] px-4 sm:px-8 flex items-center justify-between gap-4">
          <div className="flex items-center gap-4 flex-1 max-w-xl">
            {/* Mobile hamburger menu toggle */}
            <button
              onClick={() => setMobileOpen(true)}
              className="lg:hidden p-2 rounded-xl bg-white/[0.05] border border-white/[0.08] text-slate-300 hover:text-white"
              aria-label="Open navigation menu"
            >
              <Menu className="w-5 h-5" />
            </button>

            {/* Global Search Input (Cure.Med Style) */}
            <form onSubmit={handleSearchSubmit} className="relative w-full">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder={
                  isDoctor
                    ? 'Search appointments, patients, clinical records...'
                    : 'Search doctors, specialties, consultations...'
                }
                className="w-full pl-10 pr-4 py-2.5 bg-[#171824] border border-white/[0.08] focus:border-purple-500/50 rounded-2xl text-xs sm:text-sm text-slate-200 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-purple-500/20 transition-all"
              />
            </form>
          </div>

          {/* Right Top Actions (Cure.Med Top Bar Style) */}
          <div className="flex items-center gap-3 shrink-0">
            {/* Dynamic Date Badge */}
            <div className="hidden sm:flex items-center gap-2 px-3.5 py-2 rounded-2xl bg-[#171824] border border-white/[0.08] text-xs font-medium text-slate-300">
              <CalendarDays className="w-3.5 h-3.5 text-purple-400" />
              <span>{todayFormatted}</span>
            </div>

            {/* Quick Home / Dashboard Action Pill */}
            <Link
              to="/"
              className="hidden md:inline-flex items-center gap-1.5 px-4 py-2 rounded-2xl bg-[#6c5dd3] hover:bg-[#5d4ec9] text-white text-xs font-semibold shadow-lg shadow-purple-600/25 transition-all cursor-pointer"
            >
              <Home className="w-3.5 h-3.5" />
              <span>Home</span>
            </Link>

            {/* Role Chip */}
            <div className="hidden lg:flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-purple-500/10 border border-purple-500/20 text-purple-300 text-[11px] font-semibold uppercase tracking-wider">
              <Shield className="w-3 h-3 text-purple-400" />
              <span>{role}</span>
            </div>

            {/* Sign Out Button */}
            <button
              onClick={signOut}
              title="Sign Out"
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-2xl bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/20 text-rose-300 text-xs font-semibold transition-all cursor-pointer"
            >
              <LogOut className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Sign Out</span>
            </button>
          </div>
        </header>

        {/* MAIN PAGE CONTENT */}
        <main className="flex-1 p-4 sm:p-8 max-w-7xl w-full mx-auto">
          {children}
        </main>

        {/* FOOTER */}
        <footer className="border-t border-white/[0.05] bg-[#0c0d14] py-5 px-6 text-center text-xs text-slate-400">
          <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2">
            <span>CareFlow AI — Clinical Workflow &amp; Deterministic Consultation Engine</span>
            <span className="text-slate-400">HIPAA &amp; RLS Grounded Healthcare System</span>
          </div>
        </footer>
      </div>
    </div>
  );
};
