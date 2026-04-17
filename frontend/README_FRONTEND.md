# Infiniti Solutions — Steel Detailing System · Frontend README

> **React · TailwindCSS · WebSocket · FastAPI Integration**
> Engineering-focused UI | Live stage tracking | Human decision points | Output management

---

## Table of Contents

1. [Overview](#1-overview)
2. [Tech Stack](#2-tech-stack)
3. [Project Structure](#3-project-structure)
4. [Installation & Setup](#4-installation--setup)
5. [Environment Configuration](#5-environment-configuration)
6. [Application Pages & Routing](#6-application-pages--routing)
7. [Core Components](#7-core-components)
8. [WebSocket — Live Tracking](#8-websocket--live-tracking)
9. [Human Decision Panels](#9-human-decision-panels)
10. [State Management](#10-state-management)
11. [API Integration Layer](#11-api-integration-layer)
12. [Project Creation Flow](#12-project-creation-flow)
13. [Live Dashboard — Stage Tracking](#13-live-dashboard--stage-tracking)
14. [Validation & Escalation Views](#14-validation--escalation-views)
15. [Learning System UI](#15-learning-system-ui)
16. [Output & Release Management](#16-output--release-management)
17. [Design System & Styling](#17-design-system--styling)
18. [Running the Frontend](#18-running-the-frontend)
19. [Build & Deployment](#19-build--deployment)

---

## 1. Overview

The React frontend is the single interface through which engineers interact with the steel detailing agent system. It is not a generic dashboard — every screen maps to a specific engineering workflow decision point.

**Key responsibilities:**
- Project creation and file upload
- Real-time stage progress monitoring via WebSocket
- Displaying human decision points (revision conflict resolution, missing field approvals, escalation review, rule change approvals, final release gate)
- Showing Level 2 smart field suggestions
- Output download and release management

The frontend **never makes decisions autonomously** — it surfaces the system's output to the engineer and waits for explicit approval at every gated step.

---

## 2. Tech Stack

| Technology | Version | Purpose |
|-----------|---------|---------|
| React | ≥18.2 | UI framework |
| Vite | ≥5.0 | Build tool + dev server |
| TailwindCSS | ≥3.4 | Utility-first styling |
| React Router v6 | ≥6.22 | Client-side routing |
| Zustand | ≥4.5 | Lightweight global state |
| TanStack Query (React Query) | ≥5.0 | API data fetching + caching |
| Axios | ≥1.6 | HTTP client |
| native WebSocket API | — | Live tracking (no lib needed) |
| Recharts | ≥2.10 | Stage progress charts, accuracy charts |
| Lucide React | ≥0.363 | Icon set |
| clsx + tailwind-merge | latest | Conditional class merging |
| date-fns | ≥3.0 | Timestamp formatting |
| React Hook Form | ≥7.50 | Form management |
| Zod | ≥3.22 | Form validation schema |

---

## 3. Project Structure

```
frontend/
├── index.html
├── vite.config.js
├── tailwind.config.js
├── postcss.config.js
├── package.json
├── .env                              # Frontend env (API base URL)
├── .env.production
│
├── public/
│   ├── favicon.ico
│   └── logo.svg
│
└── src/
    ├── main.jsx                      # React entry point
    ├── App.jsx                       # Router setup + layout
    │
    ├── pages/                        # One file per route
    │   ├── Dashboard.jsx             # All projects overview
    │   ├── NewProject.jsx            # Project creation form
    │   ├── ProjectDetail.jsx         # Live tracking for one project
    │   ├── StageDetail.jsx           # Drilldown into one stage
    │   ├── ValidationReport.jsx      # Stage validation results table
    │   ├── EscalationInbox.jsx       # All open escalations
    │   ├── EscalationDetail.jsx      # Single escalation review
    │   ├── RuleProposals.jsx         # Phase 1 rule change proposals
    │   ├── RuleProposalDetail.jsx    # Diff view for one rule proposal
    │   ├── Outputs.jsx               # Output files and release gate
    │   └── Settings.jsx              # App settings (paths, LLM model)
    │
    ├── components/
    │   │
    │   ├── layout/
    │   │   ├── Sidebar.jsx           # Navigation sidebar
    │   │   ├── TopBar.jsx            # Project title + status badge
    │   │   └── PageWrapper.jsx       # Consistent page padding + title
    │   │
    │   ├── project/
    │   │   ├── ProjectCard.jsx       # Dashboard project tile
    │   │   ├── ProjectStatusBadge.jsx # PASS / FAIL / PENDING badges
    │   │   ├── FileUploadPanel.jsx   # Drag-and-drop file upload
    │   │   ├── FileInventoryTable.jsx # P2-01 file classification results
    │   │   └── RevisionConflictPanel.jsx # Human gate: pick governing file
    │   │
    │   ├── stages/
    │   │   ├── StageStatusBoard.jsx  # Full stage table (all 10+ stages)
    │   │   ├── StageRow.jsx          # Single row in status board
    │   │   ├── StageProgressBar.jsx  # Per-project % complete bar
    │   │   ├── StageTimeline.jsx     # Visual stage flow with pass/fail icons
    │   │   ├── CheckpointTrail.jsx   # CP1 → CP2 → CP3 visual with rollback
    │   │   └── LiveLogPanel.jsx      # Streaming WebSocket log output
    │   │
    │   ├── decisions/               # Human decision point components
    │   │   ├── MissingFieldPanel.jsx      # P2-02 missing field approval
    │   │   ├── SuggestionPopup.jsx        # Level 2 smart suggestion Accept/Reject
    │   │   ├── EscalationCard.jsx         # Escalation summary + resolve button
    │   │   ├── FallbackAlertBanner.jsx    # Alert when fallback was triggered
    │   │   ├── HandoffApprovalPanel.jsx   # Engineer handoff approval
    │   │   └── FinalReleaseGate.jsx       # P3-05 final output release
    │   │
    │   ├── validation/
    │   │   ├── ValidationMatrix.jsx       # Stage validation results table
    │   │   ├── ValidationRow.jsx          # Single field validation row
    │   │   ├── SeverityBadge.jsx          # CRITICAL / MAJOR / MINOR badges
    │   │   ├── FailureClassTag.jsx        # FIELD_MISSING, GEOMETRY_CONFLICT etc.
    │   │   └── ValidationSummaryCard.jsx  # Pass/fail/warning counts
    │   │
    │   ├── learning/
    │   │   ├── RuleDiffViewer.jsx         # Old rule vs proposed rule side-by-side
    │   │   ├── RuleProposalCard.jsx       # Rule proposal summary card
    │   │   ├── CorrectionEventsList.jsx   # Events that triggered the proposal
    │   │   └── LearningActivityLog.jsx    # Recent learning events feed
    │   │
    │   ├── outputs/
    │   │   ├── OutputPackageCard.jsx      # AB/GA/Shop etc. output card
    │   │   ├── OutputFileRow.jsx          # DXF / DWG / PDF file row with download
    │   │   ├── ReleaseChecklist.jsx       # Pre-release checklist (P3-05 summary)
    │   │   └── OutputSelectionPanel.jsx   # Engineer picks which outputs to generate
    │   │
    │   └── shared/
    │       ├── StatusBadge.jsx            # Reusable PASS/FAIL/BLOCKED badge
    │       ├── InfoBox.jsx                # Highlighted info/warning/critical box
    │       ├── ConfirmDialog.jsx          # Generic confirm dialog
    │       ├── LoadingSpinner.jsx
    │       ├── EmptyState.jsx
    │       ├── ErrorBoundary.jsx
    │       └── Tooltip.jsx
    │
    ├── hooks/
    │   ├── useWebSocket.js           # WebSocket connection + message handler
    │   ├── useProject.js             # Project data + mutations
    │   ├── useStages.js              # Stage status queries
    │   ├── useEscalations.js         # Escalation data + resolve mutations
    │   ├── useOutputs.js             # Output file queries + download
    │   └── useLearning.js            # Rule proposals + suggestions
    │
    ├── api/                          # Axios API client layer
    │   ├── client.js                 # Axios instance + interceptors
    │   ├── projects.js               # Project CRUD + file upload
    │   ├── stages.js                 # Stage control + approval
    │   ├── validations.js            # Validation result queries
    │   ├── escalations.js            # Escalation queries + actions
    │   ├── outputs.js                # Output queries + download
    │   └── learning.js               # Rule proposals + suggestions
    │
    ├── store/                        # Zustand global state
    │   ├── projectStore.js           # Active project, list of projects
    │   ├── wsStore.js                # WebSocket connection state + message buffer
    │   ├── notificationStore.js      # Toast notifications queue
    │   └── userStore.js              # Current engineer name (for sign-offs)
    │
    ├── constants/
    │   ├── stages.js                 # Stage codes, names, phase groupings
    │   ├── statusColors.js           # Tailwind classes for each status
    │   ├── failureClasses.js         # All 20 failure class labels
    │   └── outputTypes.js            # Output type definitions
    │
    └── utils/
        ├── formatters.js             # Date, duration, percentage formatters
        ├── statusHelpers.js          # Status badge logic, icon selection
        └── downloadHelpers.js        # Trigger file download from blob
```

---

## 4. Installation & Setup

```bash
cd frontend
npm install
```

**package.json dependencies (key):**
```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.22.0",
    "axios": "^1.6.0",
    "@tanstack/react-query": "^5.0.0",
    "zustand": "^4.5.0",
    "recharts": "^2.10.0",
    "lucide-react": "^0.363.0",
    "react-hook-form": "^7.50.0",
    "zod": "^3.22.0",
    "@hookform/resolvers": "^3.3.0",
    "clsx": "^2.1.0",
    "tailwind-merge": "^2.2.0",
    "date-fns": "^3.0.0"
  },
  "devDependencies": {
    "vite": "^5.0.0",
    "@vitejs/plugin-react": "^4.2.0",
    "tailwindcss": "^3.4.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0"
  }
}
```

---

## 5. Environment Configuration

```env
# .env (development)
VITE_API_BASE_URL=http://localhost:8000/api
VITE_WS_BASE_URL=ws://localhost:8000/ws
VITE_APP_NAME=Infiniti Steel Agent System
VITE_APP_VERSION=1.0.0

# .env.production
VITE_API_BASE_URL=http://localhost:8000/api     # Same for desktop deployment
VITE_WS_BASE_URL=ws://localhost:8000/ws
```

**Using in code:**
```js
const apiBase = import.meta.env.VITE_API_BASE_URL;
const wsBase  = import.meta.env.VITE_WS_BASE_URL;
```

---

## 6. Application Pages & Routing

```jsx
// src/App.jsx
import { BrowserRouter, Routes, Route } from 'react-router-dom';

<Routes>
  <Route path="/"                            element={<Dashboard />} />
  <Route path="/projects/new"                element={<NewProject />} />
  <Route path="/projects/:uuid"              element={<ProjectDetail />} />
  <Route path="/projects/:uuid/stages/:code" element={<StageDetail />} />
  <Route path="/projects/:uuid/validation"   element={<ValidationReport />} />
  <Route path="/projects/:uuid/outputs"      element={<Outputs />} />
  <Route path="/escalations"                 element={<EscalationInbox />} />
  <Route path="/escalations/:id"             element={<EscalationDetail />} />
  <Route path="/rules/proposals"             element={<RuleProposals />} />
  <Route path="/rules/proposals/:id"         element={<RuleProposalDetail />} />
  <Route path="/settings"                    element={<Settings />} />
</Routes>
```

---

## 7. Core Components

### `StageStatusBoard`

The central component of the project dashboard. Shows all stages in a colour-coded table.

```jsx
// src/components/stages/StageStatusBoard.jsx
// Props: { stages: Stage[], onApproveHandoff, onTriggerRerun }

const STATUS_STYLES = {
  PASS:                 'bg-green-100 text-green-800 border-green-300',
  'PASS WITH WARNINGS': 'bg-yellow-50 text-yellow-800 border-yellow-300',
  FAIL:                 'bg-red-100 text-red-800 border-red-300',
  BLOCKED:              'bg-gray-100 text-gray-600 border-gray-300',
  'ESCALATE':           'bg-amber-100 text-amber-800 border-amber-300',
  'RE-RUN REQUIRED':    'bg-red-50 text-red-700 border-red-300',
  PENDING:              'bg-slate-100 text-slate-500 border-slate-300',
};

export function StageStatusBoard({ stages, onApproveHandoff, onTriggerRerun }) {
  return (
    <table className="w-full text-sm border-collapse">
      <thead>
        <tr className="bg-slate-800 text-white">
          <th className="px-3 py-2 text-left font-medium">Stage</th>
          <th className="px-3 py-2 text-left font-medium">Agent</th>
          <th className="px-3 py-2 text-left font-medium">Status</th>
          <th className="px-3 py-2 text-left font-medium">Duration</th>
          <th className="px-3 py-2 text-left font-medium">Downstream</th>
          <th className="px-3 py-2 text-left font-medium">Actions</th>
        </tr>
      </thead>
      <tbody>
        {stages.map(stage => (
          <StageRow
            key={stage.stage_code}
            stage={stage}
            onApproveHandoff={onApproveHandoff}
            onTriggerRerun={onTriggerRerun}
          />
        ))}
      </tbody>
    </table>
  );
}
```

### `SuggestionPopup` (Level 2 Learning)

```jsx
// src/components/decisions/SuggestionPopup.jsx
// Appears when Level 2 learning engine has a field value suggestion

export function SuggestionPopup({ suggestion, onAccept, onReject }) {
  const { field_name, suggested_value, confidence, similar_project_count, similar_projects } = suggestion;
  const confidencePct = Math.round(confidence * 100);

  return (
    <div className="fixed bottom-6 right-6 w-96 bg-white rounded-xl shadow-2xl border border-amber-200 z-50">
      <div className="bg-amber-50 px-4 py-3 rounded-t-xl border-b border-amber-200 flex items-center gap-2">
        <span className="text-amber-600">⚡</span>
        <span className="font-semibold text-amber-800 text-sm">Field Suggestion</span>
      </div>
      <div className="p-4">
        <p className="text-xs text-slate-500 uppercase tracking-wide mb-1">Missing Field</p>
        <p className="font-semibold text-slate-800 mb-3">{field_name}</p>
        <div className="bg-slate-50 rounded-lg p-3 mb-3">
          <p className="text-xs text-slate-500 mb-1">Suggested Value</p>
          <p className="text-lg font-bold text-blue-700">{suggested_value}</p>
          <p className="text-xs text-slate-500 mt-1">
            Based on {similar_project_count} similar projects · {confidencePct}% confidence
          </p>
        </div>
        <p className="text-xs text-slate-500 mb-3">
          This is an AI suggestion. You must accept or reject. Accepted values are flagged
          as "engineer-approved" in the traceability record.
        </p>
        <div className="flex gap-2">
          <button
            onClick={() => onAccept(suggestion)}
            className="flex-1 bg-green-600 hover:bg-green-700 text-white text-sm font-medium py-2 rounded-lg"
          >
            Accept
          </button>
          <button
            onClick={() => onReject(suggestion)}
            className="flex-1 bg-slate-200 hover:bg-slate-300 text-slate-700 text-sm font-medium py-2 rounded-lg"
          >
            Reject
          </button>
        </div>
      </div>
    </div>
  );
}
```

### `RuleDiffViewer`

```jsx
// src/components/learning/RuleDiffViewer.jsx
// Shows old validation rule vs proposed new rule side-by-side

export function RuleDiffViewer({ proposal }) {
  return (
    <div className="grid grid-cols-2 gap-4">
      <div>
        <div className="text-xs font-semibold text-red-600 uppercase tracking-wide mb-2">
          Current Rule
        </div>
        <pre className="bg-red-50 border border-red-200 rounded-lg p-4 text-xs text-red-800 whitespace-pre-wrap font-mono">
          {proposal.existing_rule_text}
        </pre>
      </div>
      <div>
        <div className="text-xs font-semibold text-green-600 uppercase tracking-wide mb-2">
          Proposed Update
        </div>
        <pre className="bg-green-50 border border-green-200 rounded-lg p-4 text-xs text-green-800 whitespace-pre-wrap font-mono">
          {proposal.proposed_rule_text}
        </pre>
      </div>
      <div className="col-span-2">
        <div className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-2">
          Rationale (from Learning Agent)
        </div>
        <p className="text-sm text-slate-700 bg-slate-50 rounded-lg p-3">
          {proposal.proposal_rationale}
        </p>
        <p className="text-xs text-slate-500 mt-2">
          Triggered by {proposal.trigger_event_count} correction events on field:
          <code className="ml-1 bg-slate-100 px-1 rounded">{proposal.trigger_field_code}</code>
        </p>
      </div>
    </div>
  );
}
```

### `FinalReleaseGate`

```jsx
// src/components/decisions/FinalReleaseGate.jsx
// Shown when P3-05 returns PASS — engineer selects outputs and approves release

export function FinalReleaseGate({ project, finalCheckSummary, onApproveRelease }) {
  const [selected, setSelected] = React.useState({
    ab: true, ga: true, shop: true, sheeting: true,
    shipping: true, installation: true, full_package: true
  });

  const outputOptions = [
    { key: 'ab',           label: 'AB Drawings (DWG + PDF)' },
    { key: 'ga',           label: 'GA Drawings (DWG + PDF)' },
    { key: 'shop',         label: 'Shop Drawings (DWG + PDF)' },
    { key: 'sheeting',     label: 'Sheeting & BOQ (DXF + PDF)' },
    { key: 'shipping',     label: 'Shipping List (XLSX + PDF)' },
    { key: 'installation', label: 'Installation Drawings (DWG + PDF)' },
    { key: 'full_package', label: 'Full Release Package (ZIP)' },
  ];

  return (
    <div className="bg-white rounded-xl border-2 border-green-400 shadow-lg p-6">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-8 h-8 rounded-full bg-green-500 flex items-center justify-center text-white font-bold">✓</div>
        <div>
          <h2 className="font-bold text-green-800">Final Check Passed — Release Gate</h2>
          <p className="text-sm text-slate-600">
            {finalCheckSummary.total_warnings} warnings · 0 critical failures · Ready for release
          </p>
        </div>
      </div>
      <p className="text-sm text-slate-600 mb-4">
        Select the outputs to generate and approve the release. Output files will be
        created only after your approval.
      </p>
      <div className="grid grid-cols-2 gap-2 mb-6">
        {outputOptions.map(opt => (
          <label key={opt.key} className="flex items-center gap-2 cursor-pointer text-sm">
            <input
              type="checkbox"
              checked={selected[opt.key]}
              onChange={e => setSelected(s => ({ ...s, [opt.key]: e.target.checked }))}
              className="rounded border-slate-300"
            />
            {opt.label}
          </label>
        ))}
      </div>
      <button
        onClick={() => onApproveRelease(selected)}
        className="w-full bg-green-600 hover:bg-green-700 text-white font-semibold py-3 rounded-xl text-sm"
      >
        Approve Release & Generate Outputs
      </button>
    </div>
  );
}
```

---

## 8. WebSocket — Live Tracking

```js
// src/hooks/useWebSocket.js
import { useEffect, useRef } from 'react';
import { useWsStore } from '../store/wsStore';

export function useWebSocket(projectUuid) {
  const wsRef = useRef(null);
  const { addMessage, setConnected } = useWsStore();

  useEffect(() => {
    if (!projectUuid) return;

    const wsUrl = `${import.meta.env.VITE_WS_BASE_URL}/${projectUuid}`;
    wsRef.current = new WebSocket(wsUrl);

    wsRef.current.onopen = () => {
      setConnected(true);
      console.log(`WS connected for project ${projectUuid}`);
    };

    wsRef.current.onmessage = (event) => {
      const message = JSON.parse(event.data);
      addMessage(message);
      handleMessage(message);
    };

    wsRef.current.onclose = () => setConnected(false);
    wsRef.current.onerror = (err) => console.error('WebSocket error:', err);

    return () => wsRef.current?.close();
  }, [projectUuid]);

  function handleMessage(msg) {
    switch (msg.type) {
      case 'stage_update':
        // Invalidate React Query cache for this project's stages
        queryClient.invalidateQueries(['stages', msg.project_uuid]);
        break;
      case 'escalation_raised':
        useNotificationStore.getState().add({ type: 'warning', text: `Escalation: ${msg.reason}` });
        break;
      case 'suggestion_ready':
        useSuggestionStore.getState().queue(msg.suggestion);
        break;
      case 'output_ready':
        queryClient.invalidateQueries(['outputs', msg.project_uuid]);
        useNotificationStore.getState().add({ type: 'success', text: 'Output files ready for download' });
        break;
    }
  }
}
```

**WebSocket message types the frontend handles:**

| Type | Action |
|------|--------|
| `stage_update` | Refresh stage status board |
| `validation_result` | Append row to validation matrix |
| `escalation_raised` | Show toast + badge on escalation inbox |
| `suggestion_ready` | Queue SuggestionPopup |
| `handoff_approved` | Refresh stage + show confirmation |
| `output_ready` | Refresh outputs page + show download prompt |
| `rule_proposal` | Show badge on rule proposals nav item |
| `log_line` | Append to LiveLogPanel stream |

---

## 9. Human Decision Panels

These are the most critical UI components. Each maps to a specific backend escalation or gate.

### Decision 1 — Revision Conflict (P2-01)
```jsx
// Shown on: ProjectDetail page, when P2-01 status = ESCALATE
// Component: RevisionConflictPanel.jsx
// Shows: Ranked list of design file candidates with filename, confidence %, revision indicator
// Action: Radio button select → "Set as Governing Source" button → POST /stages/P2-01/resolve
```

### Decision 2 — Missing Fields (P2-02)
```jsx
// Shown on: ProjectDetail page, when P2-02 status = ESCALATE
// Component: MissingFieldPanel.jsx
// Shows: Table of missing fields with field_code, field_name, impact (BLOCKS/WARNS)
// Action: Text input for each field → "Submit Fields" → POST /stages/P2-02/resolve
```

### Decision 3 — Fallback Escalation
```jsx
// Shown on: EscalationDetail page
// Component: EscalationCard.jsx
// Shows: Stage ID, failure class, failure evidence, suggested action
// Actions: "Provide Correction" (opens input form) | "Override & Continue" (with confirmation)
// POST /escalations/:id/resolve
```

### Decision 4 — Level 2 Suggestion
```jsx
// Shown on: Floating popup (SuggestionPopup.jsx)
// Appears immediately when WebSocket delivers suggestion_ready message
// Actions: Accept (POST /learning/suggestions/:id/accept) | Reject (POST /learning/suggestions/:id/reject)
// Does not block UI — engineer can dismiss and come back
```

### Decision 5 — Rule Change Proposal (Phase 1 periodic)
```jsx
// Shown on: RuleProposalDetail page
// Component: RuleDiffViewer.jsx
// Shows: Side-by-side old rule vs proposed, rationale, triggering correction events list
// Actions: "Approve Rule Update" | "Reject Proposal"
// POST /learning/proposals/:id/approve | /reject
```

### Decision 6 — Final Release Gate (P3-05)
```jsx
// Shown on: Outputs page when P3-05 = PASS
// Component: FinalReleaseGate.jsx
// Shows: Summary of final check, warning list, output selection checkboxes
// Action: "Approve Release & Generate Outputs" → POST /projects/:uuid/outputs/generate
```

---

## 10. State Management

**Zustand stores** (lightweight, no Redux overhead needed):

```js
// src/store/projectStore.js
import { create } from 'zustand';

export const useProjectStore = create((set) => ({
  activeProjectUuid: null,
  projects: [],
  setActiveProject: (uuid) => set({ activeProjectUuid: uuid }),
  setProjects: (projects) => set({ projects }),
}));

// src/store/wsStore.js
export const useWsStore = create((set) => ({
  connected: false,
  messages: [],            // Rolling buffer (last 200 messages)
  setConnected: (v) => set({ connected: v }),
  addMessage: (msg) => set((state) => ({
    messages: [...state.messages.slice(-199), msg]
  })),
}));

// src/store/notificationStore.js
export const useNotificationStore = create((set) => ({
  notifications: [],
  add: (n) => set((s) => ({ notifications: [...s.notifications, { ...n, id: Date.now() }] })),
  remove: (id) => set((s) => ({ notifications: s.notifications.filter(n => n.id !== id) })),
}));
```

**React Query** handles all server data with automatic caching and background refresh:

```js
// src/hooks/useStages.js
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { stagesApi } from '../api/stages';

export function useStages(projectUuid) {
  return useQuery({
    queryKey: ['stages', projectUuid],
    queryFn: () => stagesApi.getAll(projectUuid),
    refetchInterval: 5000,        // Poll every 5s (WS also invalidates)
    enabled: !!projectUuid,
  });
}

export function useApproveHandoff(projectUuid) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (stageCode) => stagesApi.approveHandoff(projectUuid, stageCode),
    onSuccess: () => queryClient.invalidateQueries(['stages', projectUuid]),
  });
}
```

---

## 11. API Integration Layer

```js
// src/api/client.js
import axios from 'axios';

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

// Request interceptor — attach engineer name for audit trail
client.interceptors.request.use((config) => {
  const { engineerName } = useUserStore.getState();
  if (engineerName) config.headers['X-Engineer-Name'] = engineerName;
  return config;
});

// Response interceptor — handle errors globally
client.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const msg = error.response?.data?.detail || 'Request failed';
    useNotificationStore.getState().add({ type: 'error', text: msg });
    return Promise.reject(error);
  }
);

export default client;
```

```js
// src/api/projects.js
export const projectsApi = {
  create:    (data) => client.post('/projects/', data),
  getAll:    ()     => client.get('/projects/'),
  getOne:    (uuid) => client.get(`/projects/${uuid}`),
  uploadFiles: (uuid, formData) =>
    client.post(`/projects/${uuid}/files`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    }),
  runPhase2: (uuid) => client.post(`/projects/${uuid}/run/phase2`),
  runPhase3: (uuid) => client.post(`/projects/${uuid}/run/phase3`),
};
```

---

## 12. Project Creation Flow

```
1. Engineer clicks "New Project" in sidebar
2. NewProject.jsx renders form with React Hook Form + Zod validation
3. Fields: Project ID (e.g. Q-157), Project Name, Location, Project Type,
           Client Name, Start Date, Output Required (checkboxes)
4. On submit: POST /api/projects/ → returns project_uuid
5. Redirect to file upload step
6. FileUploadPanel.jsx: drag-and-drop or file picker
   - Accepts: .std, .xml, .xlsx, .dwg, .dxf, .pdf, .zip, .rar (and more)
   - Shows upload progress per file
   - POST /api/projects/:uuid/files (multipart)
7. Engineer clicks "Start Processing"
8. POST /api/projects/:uuid/run/phase2
9. Redirect to ProjectDetail.jsx (live dashboard)
```

**Form validation schema:**
```js
// src/pages/NewProject.jsx
import { z } from 'zod';

const projectSchema = z.object({
  proposal_id:  z.string().min(2, 'Project ID required').max(50),
  project_name: z.string().min(3, 'Project name required'),
  location:     z.string().optional(),
  project_type: z.enum(['Industrial Building', 'Warehouse', 'Multi-storey',
                         'Commercial Building', 'Process Plant', 'Other']),
  client_name:  z.string().optional(),
  start_date:   z.string().optional(),
  outputs_required: z.object({
    ab: z.boolean(), ga: z.boolean(), shop: z.boolean(),
    sheeting: z.boolean(), shipping: z.boolean(),
    installation: z.boolean(), full_package: z.boolean(),
  }),
});
```

---

## 13. Live Dashboard — Stage Tracking

```jsx
// src/pages/ProjectDetail.jsx — main project monitoring screen

export function ProjectDetail() {
  const { uuid } = useParams();
  const { data: stages }  = useStages(uuid);
  const { data: project } = useProject(uuid);
  useWebSocket(uuid);     // Connect WebSocket for live updates

  // Compute overall progress
  const passedCount = stages?.filter(s => s.status.startsWith('PASS')).length ?? 0;
  const totalStages = stages?.length ?? 10;
  const progressPct = Math.round((passedCount / totalStages) * 100);

  return (
    <PageWrapper title={project?.project_name}>
      {/* Progress bar */}
      <StageProgressBar value={progressPct} stagesCompleted={passedCount} total={totalStages} />

      {/* Human decision alerts (float above content) */}
      <DecisionAlertBanner stages={stages} />

      {/* Stage status board */}
      <StageStatusBoard stages={stages} />

      {/* Checkpoint timeline */}
      <CheckpointTrail projectUuid={uuid} />

      {/* Live log panel */}
      <LiveLogPanel projectUuid={uuid} />
    </PageWrapper>
  );
}
```

**Stage colour rules** (in `constants/statusColors.js`):
```js
export const STAGE_STATUS_COLORS = {
  PASS:                 { bg: 'bg-green-100',  text: 'text-green-800',  dot: 'bg-green-500'  },
  'PASS WITH WARNINGS': { bg: 'bg-yellow-50',  text: 'text-yellow-800', dot: 'bg-yellow-400' },
  FAIL:                 { bg: 'bg-red-100',    text: 'text-red-800',    dot: 'bg-red-500'    },
  BLOCKED:              { bg: 'bg-slate-100',  text: 'text-slate-500',  dot: 'bg-slate-400'  },
  'ESCALATE':           { bg: 'bg-amber-100',  text: 'text-amber-800',  dot: 'bg-amber-500'  },
  'RE-RUN REQUIRED':    { bg: 'bg-red-50',     text: 'text-red-700',    dot: 'bg-red-400'    },
  PENDING:              { bg: 'bg-slate-50',   text: 'text-slate-400',  dot: 'bg-slate-300'  },
  IN_PROGRESS:          { bg: 'bg-blue-50',    text: 'text-blue-700',   dot: 'bg-blue-500 animate-pulse' },
};
```

---

## 14. Validation & Escalation Views

```jsx
// src/components/validation/ValidationMatrix.jsx
// Shows per-field validation results for a given stage

const SEVERITY_STYLES = {
  CRITICAL:      'bg-red-600 text-white',
  MAJOR:         'bg-red-100 text-red-700',
  MINOR:         'bg-yellow-100 text-yellow-700',
  INFORMATIONAL: 'bg-slate-100 text-slate-600',
};

// src/pages/EscalationDetail.jsx
// Shows full escalation detail: stage, type, evidence, suggested action
// Actions: Provide Correction (opens input form) | Override (with warning dialog)
// Every resolution is logged with engineer name + timestamp
```

---

## 15. Learning System UI

### Rule Proposals Page (`/rules/proposals`)
- Lists all pending rule proposals as cards
- Each card: field_code, trigger count, proposal date, status badge
- Click → `RuleProposalDetail` page with diff viewer + approve/reject buttons
- Engineer must type a review note before approving (enforced by form validation)

### Learning Activity Log
- Shows recent correction_events, approved proposals, Level 3 index updates
- Filter by project, field_code, date range
- Read-only audit trail

---

## 16. Output & Release Management

```jsx
// src/pages/Outputs.jsx

// State machine:
// P3-05 PENDING  → Show "Awaiting final check completion"
// P3-05 PASS     → Show FinalReleaseGate component
// P3-05 FAIL     → Show critical failure list, re-run options
// RELEASE APPROVED → Show OutputPackageCards with download buttons

// OutputPackageCard.jsx: one card per output type
// Shows: DXF link, DWG link, PDF link, file size, generated_at timestamp
// Download: GET /api/projects/:uuid/outputs/download?type=AB&format=pdf

// Full package download:
// GET /api/projects/:uuid/outputs/download?type=PACKAGE
// Returns PACKAGE.zip
```

---

## 17. Design System & Styling

**TailwindCSS configuration** (`tailwind.config.js`):

```js
export default {
  content: ['./src/**/*.{jsx,js,tsx,ts}'],
  theme: {
    extend: {
      colors: {
        navy:    { DEFAULT: '#0D1B3E', light: '#1A3A6B' },
        steel:   { DEFAULT: '#1A56A0', light: '#D6E8F7' },
        teal:    { DEFAULT: '#0E7C7B' },
        pass:    { DEFAULT: '#1E7A3E', bg: '#E6F4EA' },
        fail:    { DEFAULT: '#B91C1C', bg: '#FEE2E2' },
        warn:    { DEFAULT: '#92400E', bg: '#FEF3C7' },
        blocked: { DEFAULT: '#374151', bg: '#F3F4F6' },
      },
      fontFamily: {
        sans: ['IBM Plex Sans', 'system-ui', 'sans-serif'],
        mono: ['IBM Plex Mono', 'ui-monospace', 'monospace'],
      },
    },
  },
};
```

**Design principles:**
- Stage status always shown with colour + text (never colour alone — accessibility)
- Every human decision point has a clear "what happens if I do this" description before the action button
- No action that triggers agent re-runs shows just an icon — always labelled
- CRITICAL severity items always shown with a red left border, never just a colour badge

---

## 18. Running the Frontend

```bash
cd frontend
npm run dev
```

Frontend serves at: `http://localhost:5173`

Backend must be running at `http://localhost:8000` (set in `.env`).

---

## 19. Build & Deployment

```bash
# Production build
npm run build
# Output in: frontend/dist/

# Preview production build locally
npm run preview
```

**Desktop deployment:** For desktop deployment (Electron or just a bundled webapp), build with `npm run build` and serve the `dist/` folder via a local HTTP server bundled with the desktop app.

```bash
# Simple local server (if Electron not used)
npx serve dist -p 3000
```

---

*Infiniti Solutions — Steel Detailing Multi-Agent System | Frontend Developer Reference | v1.0 April 2026*
