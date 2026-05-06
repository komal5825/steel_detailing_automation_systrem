import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  ClipboardList,
  Database,
  FileText,
  FolderOpen,
  GitBranch,
  Layers,
  LayoutDashboard,
  Package,
  Settings,
  Zap,
} from 'lucide-react';
import { clsx } from 'clsx';

const NAV_SECTIONS = [
  {
    label: 'OVERVIEW',
    items: [
      { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
      { to: '/projects', icon: FolderOpen, label: 'Projects' },
      { to: '/master-db', icon: Database, label: 'Master Database' },
    ],
  },
  {
    label: 'PIPELINE',
    items: [
      { to: '/phase1', icon: Database, label: 'Phase 1 - Master DB' },
      { to: '/phase2', icon: Layers, label: 'Phase 2 - AB / GA' },
      { to: '/phase3', icon: GitBranch, label: 'Phase 3 - Detailing' },
      { to: '/validator', icon: ClipboardList, label: 'Final Validator' },
    ],
  },
  {
    label: 'OPERATIONS',
    items: [
      { to: '/files', icon: FileText, label: 'File Inventory' },
      { to: '/outputs', icon: Package, label: 'Shipping & Release' },
      { to: '/audit', icon: ClipboardList, label: 'Audit Logs' },
      { to: '/settings', icon: Settings, label: 'Settings' },
    ],
  },
];

export default function Sidebar() {
  return (
    <aside className="fixed left-0 top-0 z-40 flex h-screen w-56 flex-col border-r border-blue-950 bg-[#07152F]">
      <div className="flex items-center gap-2 border-b border-white/10 px-4 py-4">
        <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded bg-amber-500">
          <Zap size={14} className="text-white" />
        </div>
        <div>
          <div className="text-xs font-bold leading-tight tracking-wide text-white">INFINITI SOLUTIONS</div>
          <div className="text-xxs leading-tight text-blue-200">STEEL DETAILING AUTOMATION SYSTEM</div>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto py-3">
        {NAV_SECTIONS.map((section) => (
          <div key={section.label} className="mb-4">
            <div className="px-4 py-1 text-xxs font-bold tracking-widest text-blue-300/70">
              {section.label}
            </div>
            {section.items.map((item) => (
              <SidebarItem key={item.to} {...item} />
            ))}
          </div>
        ))}
      </nav>

      <div className="border-t border-white/10 px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-blue-700 text-xxs font-bold text-white">
            KS
          </div>
          <div>
            <div className="text-xs font-semibold leading-tight text-white">Komal S</div>
            <div className="text-xxs leading-tight text-blue-200">It Team</div>
          </div>
        </div>
      </div>
    </aside>
  );
}

function SidebarItem({ to, icon: Icon, label }) {
  return (
    <NavLink
      to={to}
      end={to === '/'}
      className={({ isActive }) =>
        clsx(
          'mx-2 flex items-center gap-2.5 rounded-md px-3 py-1.5 text-xs transition-colors',
          isActive
            ? 'bg-blue-700 font-semibold text-white'
            : 'text-blue-100 hover:bg-white/10 hover:text-white'
        )
      }
    >
      <Icon size={14} className="flex-shrink-0" />
      <span>{label}</span>
    </NavLink>
  );
}
