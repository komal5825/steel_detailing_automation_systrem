export const PHASE2_STAGES = [
  {
    code: 'P2-01',
    name: 'Design File Ingestion',
    description: 'Unpacks archives, classifies files, ranks governing design candidates',
    phase: 2,
  },
  {
    code: 'P2-02',
    name: 'Design Completeness Check',
    description: 'Maps available data against master field dictionary',
    phase: 2,
  },
  {
    code: 'P2-03',
    name: 'Anchor Bolt Generation',
    description: 'Generates AB plan, section, detail views',
    phase: 2,
  },
  {
    code: 'P2-04',
    name: 'General Arrangement',
    description: 'Inherits AB grid as fixed reference, builds GA plan + elevations',
    phase: 2,
  },
  {
    code: 'P2-05',
    name: 'AB/GA Validation',
    description: 'Cross-validates AB & GA outputs against governing design file',
    phase: 2,
  },
];

export const PHASE3_STAGES = [
  { code: 'P3-01', name: 'Sheeting', description: 'Roof and wall sheeting data', phase: 3 },
  { code: 'P3-02', name: 'Shop Drawings', description: 'Member-level shop drawings', phase: 3 },
  { code: 'P3-03', name: 'Shipping List', description: 'Dispatch and packing list generation', phase: 3 },
  { code: 'P3-04', name: 'Installation Drawings', description: 'Erection and site installation package', phase: 3 },
  { code: 'P3-05', name: 'Final Check', description: 'Full package validation and release gate', phase: 3 },
];

export const ALL_STAGES = [...PHASE2_STAGES, ...PHASE3_STAGES];

export const STATUS_META = {
  PENDING: { label: 'Pending', color: 'text-slate-600', bg: 'bg-slate-100', dot: 'bg-slate-400', border: 'border-slate-300' },
  RUNNING: { label: 'Running', color: 'text-blue-700', bg: 'bg-blue-50', dot: 'bg-blue-500 animate-pulse', border: 'border-blue-300' },
  IN_PROGRESS: { label: 'Running', color: 'text-blue-700', bg: 'bg-blue-50', dot: 'bg-blue-500 animate-pulse', border: 'border-blue-300' },
  PASSED: { label: 'Completed', color: 'text-emerald-700', bg: 'bg-emerald-50', dot: 'bg-emerald-500', border: 'border-emerald-300' },
  FAILED: { label: 'Failed', color: 'text-red-700', bg: 'bg-red-50', dot: 'bg-red-500', border: 'border-red-300' },
  AWAITING_INPUT: { label: 'Needs Input', color: 'text-amber-700', bg: 'bg-amber-50', dot: 'bg-amber-500', border: 'border-amber-300' },
  BLOCKED: { label: 'Blocked', color: 'text-amber-800', bg: 'bg-amber-100', dot: 'bg-amber-600', border: 'border-amber-300' },
  SKIPPED: { label: 'Skipped', color: 'text-amber-700', bg: 'bg-amber-50', dot: 'bg-amber-500', border: 'border-amber-300' },
  PASS_WITH_WARNINGS: { label: 'Warnings', color: 'text-amber-700', bg: 'bg-amber-50', dot: 'bg-amber-500', border: 'border-amber-300' },
  PARSED: { label: 'Parsed', color: 'text-emerald-700', bg: 'bg-emerald-50', dot: 'bg-emerald-500', border: 'border-emerald-300' },
  EXTRACTED: { label: 'Extracted', color: 'text-blue-700', bg: 'bg-blue-50', dot: 'bg-blue-500', border: 'border-blue-300' },
  UNSUPPORTED: { label: 'Unsupported', color: 'text-slate-600', bg: 'bg-slate-100', dot: 'bg-slate-500', border: 'border-slate-300' },
};
