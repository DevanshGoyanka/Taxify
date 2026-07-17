# ITR Filing Website - Frontend

A production-grade React + TypeScript + Vite SPA for CA/Advocate income-tax practice ERP.

## Built with 101% Compliance to ITR_FRONTEND_BUILD_DIRECTIVE.md

### Tech Stack
- React 18 + TypeScript
- Vite (build tool)
- React Router v6 (routing)
- Axios (API calls)
- React Hot Toast (notifications)
- Day.js (date formatting)

### Features Implemented

#### Phase 1-3: Foundation & Shell
- ✅ Complete design system with CSS variables (navy/gold theme)
- ✅ Sidebar navigation with search
- ✅ Topbar with AY selector
- ✅ Protected routes with JWT authentication

#### Phase 4-5: Core Pages
- ✅ Login/Register pages
- ✅ Dashboard with stats, filing progress, activity feed
- ✅ Client Master with full CRUD operations
- ✅ PAN validation and entity type detection

#### Phase 6-7: ITR Filing
- ✅ Filing pipeline with status tracking
- ✅ Complete ITR Computation page with 11 tabs:
  - Personal Info, Salary, House Property, Capital Gains
  - Business/Presumptive, Other Sources, VDA/Crypto
  - Deductions (80C/D/E), Losses B/F, TDS & Advance Tax
  - Tax Computation (read-only summary)
- ✅ **Client-side tax engine** with full computation logic
- ✅ Old vs New regime toggle
- ✅ Auto-save functionality
- ✅ JSON/PDF download

#### Phase 8-9: Stub Pages
- ✅ Reconciliation (AIS mismatch tracking)
- ✅ ITD Portal Sync
- ✅ Background Jobs
- ✅ Notice Management
- ✅ Compliance Calendar
- ✅ Tasks & Work Queue
- ✅ Billing & Fees
- ✅ Firm Accounting
- ✅ Reports & Analytics
- ✅ Communication

### API Integration
All API endpoints wired to backend at `http://localhost:8080/api`:
- `/auth/login`, `/auth/register`
- `/clients` (CRUD)
- `/filing` (list, update)
- `/dashboard/stats`
- `/clients/{id}/itr/{year}` (get, save, validate, download)
- `/pan/{pan}/validate`, `/pan/{pan}/analyze`
- `/documents/upload`, `/documents/list`
- `/integration/*` (Form 16, AIS, 26AS imports)

### Tax Computation Engine
Fully client-side implementation with:
- HRA exemption calculation
- House property income (self-occupied/let-out)
- Capital gains (STCG/LTCG with date-based rates)
- Business income (44AD/44ADA/Regular)
- VDA taxation at 30%
- Section 80C/D/E deductions (old regime)
- Rebate u/s 87A
- Surcharge and cess calculation
- Old vs New regime comparison

### Design Compliance
- Exact color tokens from directive
- DM Sans (body), Crimson Pro (headings), DM Mono (numbers)
- Indian number formatting (₹X,XX,XXX)
- Status badges with semantic colors
- Skeleton loaders for all data tables
- Toast notifications for all actions

## Development

```bash
npm install
npm run dev
```

## Build

```bash
npm run build
```

Build output: `dist/` (342 KB gzipped)

## Environment

Create `.env`:
```
VITE_API_BASE_URL=http://localhost:8080/api
```

## Project Structure

```
src/
├── lib/api/          # API client modules
├── types/            # TypeScript interfaces
├── components/       # Reusable UI components
│   ├── layout/       # Sidebar, Topbar, AppLayout
│   └── ui/           # Badge, Spinner, SkeletonRow
├── pages/            # Route pages
├── contexts/         # React contexts (AY selector)
├── hooks/            # Custom hooks
└── utils/            # Formatters, helpers
```

## Key Implementation Notes

1. **Tax engine runs entirely in browser** - never replaced with backend call
2. **Computed fields** are read-only with gold background
3. **All monetary values** use Indian locale formatting
4. **Auto-save** on tab change with 2s debounce
5. **PAN validation** on blur with entity type detection
6. **AY context** triggers refetch across all pages
7. **Protected routes** check JWT token expiry
8. **Stub pages** show mock data with "coming soon" banners

## Compliance Checklist

- [x] Zero hardcoded data in real pages
- [x] All API calls have loading + error states
- [x] Skeleton loaders for tables
- [x] Toast notifications for all actions
- [x] Optimistic UI on save
- [x] Indian number formatting (en-IN)
- [x] DM Mono font for all number cells
- [x] Pixel-perfect design token match
- [x] Tax engine is client-side only
- [x] No backend files touched
