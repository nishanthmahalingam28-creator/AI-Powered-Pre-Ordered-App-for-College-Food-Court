# Phase 1 — Supabase Foundation

This branch starts the migration of the College Food Court application from the legacy Flask + MySQL/SQLite architecture to the target React + TypeScript + Supabase architecture.

## Target stack

- React 18
- TypeScript 5.5.3
- Vite 5.4.2
- Tailwind CSS 3.4.1
- React Router 6.30.4
- Lucide React
- Supabase PostgreSQL
- Supabase Auth
- Supabase Realtime
- Supabase Storage
- Vite PWA / Workbox
- jsPDF / jsPDF AutoTable
- SheetJS / XLSX
- FileSaver.js
- ESLint
- npm / Node.js

## Phase 1 scope

- PostgreSQL target schema
- UUID-based Supabase Auth identity
- legacy_id mapping for migration from the current integer MySQL IDs
- indexes for menu, order, notification, cart, budget and survey paths
- Row Level Security foundation
- vendor/shop isolation foundation
- Food Survey: one student submission per meal period per day
- no Campus Wallet field
- no Income table
- no direct browser writes to order/payment state

The current Flask/MySQL application remains untouched in this phase.

## Apply

After linking a Supabase project, run the migration through the Supabase CLI or SQL migration workflow.

Do not put a service-role key in frontend code.

## Next phases

Phase 2: Supabase Auth + profile provisioning + complete RLS tests.

Phase 3: React/TypeScript/Vite/Tailwind application shell and routing.

Phase 4: Customer ordering, atomic stock reservation, payment and OTP workflow.
