import React from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import Sidebar from './components/layout/Sidebar';
import ToastContainer from './components/shared/Toast';
import Dashboard from './pages/Dashboard';
import NewProject from './pages/NewProject';
import ProjectWorkspace from './pages/ProjectWorkspace';
import ReportsPage from './pages/ReportsPage';
import AuditLogsPage from './pages/AuditLogsPage';

export default function App() {
  return (
    <div className="min-h-screen bg-slate-100 text-slate-950">
      <Sidebar />
      <main className="ml-56 min-h-screen">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/projects" element={<Dashboard />} />
          <Route path="/projects/new" element={<NewProject />} />
          <Route path="/projects/:projectId" element={<ProjectWorkspace />} />
          <Route path="/phase2" element={<Dashboard />} />
          <Route path="/phase3" element={<Dashboard />} />
          <Route path="/reports" element={<ReportsPage />} />
          <Route path="/reports/:projectId" element={<ReportsPage />} />
          <Route path="/audit" element={<AuditLogsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
      <ToastContainer />
    </div>
  );
}
