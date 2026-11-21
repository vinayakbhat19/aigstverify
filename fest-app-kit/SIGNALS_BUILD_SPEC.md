# Signals: Build Spec for Antigravity

Hand this whole file to Antigravity. Build in the phases at the bottom, one phase per session. Do not skip the rules in section 1.

## 0. What we are building

**Signals** is a campus app (first campus: SDMCET Dharwad) with three parts:

1. **Signals**: raise a signal ("need a 4th for badminton") or search nearby; chat with people who reply.
2. **Host your event**: any person can host a fest, competition, workshop or event in 7 steps and publish it to SDMCET only, everyone, or link only.
3. **Fest mode**: entering a fest (for example Fiesta'26) re-themes the app with the fest's own look, a "Stalls and shows" centre button, leaderboard, hunt, and registered QR.

One codebase family, three targets:

| Target | Tech | Host |
|---|---|---|
| Web app (PWA) | React + Vite + TypeScript | Cloudflare Pages |
| Phone app | React Native with Expo (SDK latest stable), Expo Router | Expo Go and EAS Build for testing |
| Backend | Supabase (Postgres, Auth, Realtime, Storage, Edge Functions) | Supabase free tier |

Mail for sign-in codes: Brevo SMTP configured inside Supabase Auth.

## 1. Rules (do not break)

- **Free tier only.** No paid service. No card.
- **Never put secrets in the repo or in chat.** Use `.env` files that are git-ignored. Only the Supabase URL and anon key go in client code. The service role key lives only in Edge Function secrets.
- **Do not touch the existing Fiesta'26 database or the live site** at fiesta26.pages.dev. Signals gets its own Supabase project.
- **Row Level Security on every table.** No table without policies. Clients never get the service role key.
- **Payment is never in the app.** People register by QR themselves, and pay by hand at the registration desk. Only a desk volunteer can mark "paid".
- **Only the host assigns roles and access.** Coordinators manage only their own events.
- **The Signals logo and splash animation are fixed. Do not redesign them.**
- Use the words "Host your event", not "Host your fest".
- Every button must lead somewhere. No dead ends. Every list needs a loading skeleton, an empty state and an error state.
- Accessibility: 44 px minimum touch targets, labels on icon buttons, respect reduced motion, contrast AA.

## 2. Repo layout (monorepo, pnpm workspaces)

```
signals/
  apps/
    web/            React + Vite PWA  -> Cloudflare Pages
    mobile/         Expo (React Native, Expo Router)
  packages/
    core/           shared TypeScript: types, zod schemas, api client, hooks, QR signing helpers
    ui-tokens/      colours, spacing, radii, type scale (one source for web CSS vars and RN theme)
  supabase/
    migrations/     SQL files, numbered
    functions/      Edge Functions (Deno)
    seed.sql
  docs/
  .env.example
  pnpm-workspace.yaml
```

Rule: screens contain no Supabase calls. All data goes through `packages/core/api`. Hooks use TanStack Query. Validation uses zod.

## 3. Design tokens (from the approved canvas)

Dark is default. Light is warm paper.

```ts
export const dark = { bg:'#000000', s1:'#131318', s2:'#1C1C23', s3:'#272730', tx:'#F5F5F7', mu:'#A5A5B0', bd:'#2A2A33', ink:'#0A0A0A', nav:'#0E0E12' };
export const light = { bg:'#F4F1EA', s1:'#FFFFFF', s2:'#ECE8DF', s3:'#DED9CC', tx:'#0A0A0A', mu:'#5A5953', bd:'#DDD8CB', ink:'#0A0A0A', nav:'#16161B' };
export const brand = { yellow:'#FFD60A', pink:'#FF8AB8', purple:'#9B6CFF', cyan:'#22D3EE', lightBlue:'#8CCBFF', ok:'#3DDC97' };
// Fest mode (Fiesta theme, per fest it is overridable by the host)
export const fest = { bg:'#0E0818', header:'#2A1450', card:'#1F1230', line:'#3B2758', yellow:'#FFD60A', pink:'#FF4FD8', purple:'#9B6CFF', cyan:'#22D3EE' };
```

- Font: Inter (400 to 800). Fest wordmarks: Bungee.
- Light blue (`lightBlue`) is the colour of every signal and message screen.
- Radii: cards 26 to 30, buttons fully rounded (capsule), inputs 18. Spacing on an 8 pt grid.
- Bottom nav: floating rounded bar. The active tab lifts 12 px and tilts (`rotateX(16deg)`). Centre is the **Signal coin** (logo, with slow ping rings). Tabs: Home, Events, (Signal), Host, Me.
- Motion only to show state. No decorative loops except the coin ping and radar sweep. Disable all under reduced motion.
- Loading is skeleton shimmer, never a spinner.

## 4. Screens and routes

Web routes and Expo Router paths are the same names.

**Open and auth**
`/` splash (fixed) → `/welcome` → `/login` or `/signup` → `/otp` (6 boxes) → `/campus-verify` (optional college email) → `/interests` → `/permissions` (location, notifications) → `/home`. Also `/forgot`, `/forgot-sent`, `/about`.

**Main tabs**
- `/home`: big fest card (Fiesta'26) → fest mode; small cards labelled Competition or Workshop; "Signals raised near you"; header icons Search, Bell, Messages, Profile; "About Signals" link at the bottom. A second tab or segment: SDMCET feed and Communities.
- `/events`: "My fest" first (QR, map, registered status), then my events with map and a "Call coordinator" button. Nearby events show fests first, then single events.
- `/signal` (the coin): two options, **Raise your signal** or **Search nearby**.
  - `/signal/permission` → `/signal/search` (radar animation with small boxes appearing, skeleton results) → `/signal/[id]` detail → `/chat/[id]`.
  - `/signal/raise` → `/signal/raised` → `/signal/mine`.
- `/inbox`, `/notifications`, `/search`, `/communities`, `/communities/[id]`.
- `/host`: see section 5.
- `/me`: profile card with QR (Share QR), rows: My signals, Fest mode, Coordinator tools (only if assigned), App settings, Notifications, edit details, sign out, delete account. Sub pages: `/me/edit`, `/me/settings`, `/me/notifications`, `/me/sign-out`, `/me/delete`. "Keep my QR offline" setting.

**Event pages (participant)**
`/event/[id]` detail → `/event/[id]/register` (self-register by QR, "pay at the desk" notice) → `/my-qr` (ticket style) → `/event/[id]/map` (registration desk is stop 1, then venues with walking times).

**Fest mode** (own theme, logo and nav; centre button is "Stalls and shows" instead of Signal; profile shows the registered QR and "Back to Signals")
`/fest/[id]` enter → home, competitions (events), shows (main concert and singer), stalls, leaderboard, hunt, more, my profile, event detail, manage (for coordinators).

**Coordinator and desk** (phone and laptop)
Coordinator: home, scan, scan-not-registered, list (works offline), winners, ended. Desk: laptop view with top bar, registration ledger, mark paid.

**States** (build as components, reused everywhere): Offline banner, Slow network banner with progress bar, Update available, skeletons for home, events, signals.

## 5. Host your event (7 steps)

Entry: `/host/about` (about the host person: name, role, college, phone) → `/host/type` ("What are you hosting?": Fest, Competition, Workshop, Event) → `/host/start` ("Let's get started") → hub with the 7 steps and progress:

1. **Name, logo, theme**: name, logo upload, banner, colours.
2. **Schedule**: start, end, per day timings.
3. **Sponsors and management**: sponsor list with tier and logo; team members; host assigns roles (coordinator, desk volunteer, scanner). Only the host can do this.
4. **Events, concerts, stalls, shows**: inside a fest add competitions, workshops, the main concert (singer), auto expo, bike showcase, stalls. Each item: name, date, time, venue, coordinator, rules, help contact, prize, max team size.
5. **Map**: place venues, registration desk first; walking times.
6. **Look and intro**: preview as participant, intro text, cover.
7. **Publish**: audience = Only SDMCET, Everyone, or Link only. Shows a share link and QR poster. Then `/host/live`.

Progress saves after every step (draft rows). A host can edit after publishing.

Laptop version: the same 7 steps with a top nav bar (no side column). Phone version: bottom nav.

## 6. Backend (Supabase)

Create one new Supabase project. Enable extensions: `postgis`, `pgcrypto`.

### 6.1 Tables (migration 001)

```sql
create extension if not exists postgis;
create extension if not exists pgcrypto;

create table profiles(
  id uuid primary key references auth.users on delete cascade,
  name text not null check (char_length(name) between 2 and 60),
  college text, interests text[] default '{}',
  avatar_url text, phone text,
  campus_verified boolean default false,
  created_at timestamptz default now());

create table signals(
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references profiles on delete cascade,
  title text not null check (char_length(title) between 3 and 80),
  kind text not null check (kind in ('Study','Sport','Food','Ride','Other')),
  place text not null,
  geo geography(point,4326),
  expires_at timestamptz not null default now() + interval '3 hours',
  closed_at timestamptz, created_at timestamptz default now());
create index on signals using gist(geo);

create table signal_messages(
  id bigint generated always as identity primary key,
  signal_id uuid not null references signals on delete cascade,
  sender uuid not null references profiles,
  recipient uuid not null references profiles,
  body text not null check (char_length(body) <= 500),
  created_at timestamptz default now());

create table events(                       -- a fest is an event with kind='fest'; items point to a parent
  id uuid primary key default gen_random_uuid(),
  parent_id uuid references events on delete cascade,
  host_id uuid not null references profiles,
  kind text not null check (kind in ('fest','competition','workshop','event','concert','stall','show','expo')),
  name text not null, theme jsonb default '{}', logo_url text, banner_url text,
  starts_at timestamptz, ends_at timestamptz, venue text, rules text,
  coordinator_id uuid references profiles, help_phone text, prize text, team_max int default 1,
  audience text not null default 'sdmcet' check (audience in ('sdmcet','everyone','link')),
  link_token text default encode(gen_random_bytes(9),'hex'),
  status text not null default 'draft' check (status in ('draft','live','ended')),
  step int default 1, body jsonb default '{}', created_at timestamptz default now());

create table event_roles(
  event_id uuid references events on delete cascade,
  user_id uuid references profiles on delete cascade,
  role text check (role in ('coordinator','desk','scanner')),
  scope_event_id uuid references events,   -- coordinators manage only this child event
  primary key(event_id,user_id,role));

create table sponsors(id uuid primary key default gen_random_uuid(), event_id uuid references events on delete cascade, name text, tier text, logo_url text, link text);
create table venues(id uuid primary key default gen_random_uuid(), event_id uuid references events on delete cascade, name text, is_desk boolean default false, position int, geo geography(point,4326), walk_minutes int);

create table registrations(
  event_id uuid references events on delete cascade,
  user_id uuid references profiles on delete cascade,
  qr_secret text not null default encode(gen_random_bytes(16),'hex'),
  paid boolean default false, paid_by uuid references profiles, paid_at timestamptz,
  checked_in boolean default false, created_at timestamptz default now(),
  primary key(event_id,user_id));

create table entries(                      -- registration for a competition inside a fest
  event_id uuid references events on delete cascade,
  user_id uuid references profiles on delete cascade,
  team_name text, attended boolean default false, score numeric, rank int,
  primary key(event_id,user_id));

create table reports(id bigint generated always as identity primary key, reporter uuid references profiles, signal_id uuid references signals, reason text, created_at timestamptz default now());
create table blocks(blocker uuid references profiles, blocked uuid references profiles, primary key(blocker,blocked));
create table notifications(id bigint generated always as identity primary key, user_id uuid references profiles, title text, body text, link text, read boolean default false, created_at timestamptz default now());
create table push_tokens(user_id uuid references profiles on delete cascade, token text, platform text, primary key(user_id,token));
```

### 6.2 RLS (migration 002), required policies

Enable RLS on every table above, then:

- `profiles`: a user reads and writes only their own row. Other users see only `id, name, avatar_url, college` through a view `public_profiles`.
- `signals`: select where `closed_at is null and expires_at > now()` and the author is not blocked by the viewer; insert and update only own rows.
- `signal_messages`: select and insert only when the user is `sender` or `recipient`.
- `events`: select when `status='live'` and (`audience='everyone'`, or `audience='sdmcet'` and the viewer is `campus_verified`, or the viewer is host or has a role). `link` events are returned only by the RPC `get_event_by_link(token)`. Insert, update and delete only by `host_id`.
- `event_roles`: only the host of the event can insert, update or delete.
- `registrations`: a user can insert their own row with `paid=false, checked_in=false` and read their own; **no client can update `paid` or `checked_in`**.
- Desk and coordinator changes go through `security definer` functions only:
  - `mark_paid(event uuid, user uuid)`: caller must have role `desk` or be host.
  - `check_in(event uuid, qr text)`: caller must have role `scanner`, `desk` or `coordinator`.
  - `record_result(event uuid, user uuid, score numeric)`: caller must be coordinator of that child event.
  - `nearby_signals(lat double precision, lng double precision, radius_m int)`: returns signals within radius, excludes blocked users.
- `notifications`, `push_tokens`: own rows only.
- Storage buckets: `avatars` and `event-media`. Public read. Write only into a folder named with the user's own uid or the event the user hosts. Max 2 MB, images only.

### 6.3 Auth

- Email OTP, 6 digits (Supabase Auth, "Email OTP" enabled, magic-link template changed to show `{{ .Token }}`).
- SMTP: Brevo, configured in Supabase dashboard. Never commit the key.
- A user whose email ends with `@sdmcet.ac.in` gets `campus_verified = true` via a database trigger on `auth.users` insert. Others can verify later through `/campus-verify`.
- Rate limits: keep Supabase defaults; add client side cooldown of 30 s on "Send a new code".
- Delete account calls an Edge Function that removes the user (needs service role) and cascades.

### 6.4 Edge Functions (Deno)

| Function | Purpose |
|---|---|
| `qr-sign` | Returns a signed QR payload `v1.<eventId>.<userId>.<hmac>` using the secret `QR_HMAC_KEY`. The phone caches it for offline. |
| `qr-verify` | Not needed online (desks verify offline with the public check below), kept for audits. |
| `delete-account` | Deletes the caller. |
| `push-send` | Sends Expo push notifications when a message or reply arrives (database webhook). |
| `expire-signals` | Scheduled hourly; closes expired signals. |

Offline QR check: use HMAC with a per event secret that is downloaded to coordinator and desk devices only after they sign in with a role. Participants only hold the signed payload.

### 6.5 Realtime

Subscribe to `signal_messages` filtered by `recipient = auth.uid()` and to `signals` inserts in the viewer's area (through a coarse geohash column if volume grows). Keep to the free tier connection limit: unsubscribe on screen blur.

## 7. Shared client logic (`packages/core`)

- `api/` one file per area: `auth.ts, profile.ts, signals.ts, chat.ts, events.ts, host.ts, registrations.ts, desk.ts`.
- `hooks/`: `useSession, useSignals(nearby), useChat, useEvent, useMyFest, useHostDraft`.
- Offline: persist TanStack Query cache (web: IndexedDB; mobile: MMKV or AsyncStorage). Queue writes made offline (check-in marks, messages) and flush when online. Show the Offline banner when `navigator.onLine` or NetInfo says so.
- Location: ask only when the user taps Search nearby or Raise. Round coordinates to 3 decimals before storing. Never show exact location to others, only place text and distance bands.
- Validation: zod schemas shared between web, mobile and (for Edge Functions) Deno.

## 8. Web app (React + Vite PWA)

- React Router, TanStack Query, CSS variables from `ui-tokens`, Tailwind optional.
- `vite-plugin-pwa`: manifest (name Signals, black background, icons 192 and 512 maskable), service worker precaches the shell, runtime caching for API reads, offline fallback page.
- Responsive: phone layout is the main layout. At laptop width, the host and coordinator areas switch to the laptop layout with a **top navigation bar** and no side column.
- Cloudflare Pages deploy:
  - Build command `pnpm --filter web build`, output `apps/web/dist`.
  - Add `public/_redirects` containing `/* /index.html 200`.
  - Env vars in Pages dashboard: `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`.
  - Add a `_headers` file: `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, and a CSP that allows only your Supabase URL, Google Fonts and self.
  - Custom domain later; start on `*.pages.dev`.

## 9. Mobile app (React Native with Expo)

- Expo Router (file based routes mirroring section 4), `expo-secure-store` for the session, `expo-location`, `expo-notifications`, `expo-camera` (QR scan), `react-native-qrcode-svg`, `expo-haptics`, `react-native-reanimated` for the nav lift and tilt, `@react-native-community/netinfo`.
- Nav bar: custom tab bar component. Active tab `translateY(-12)` and `rotateX(16deg)` with `perspective`, spring animation. Centre Signal coin with two ping rings. In fest mode the centre button changes to "Stalls and shows" and the whole theme switches to the fest tokens.
- Fest mode is a navigator group `/fest/[id]` with its own theme provider. "Back to Signals" restores the previous theme.
- Test now with Expo Go: `pnpm --filter mobile start`, scan the QR with Expo Go. Camera, location and notifications work in Expo Go for development.
- Test builds on a real phone:
  - `eas build:configure`, then `eas build -p android --profile preview` (APK, free tier queue) for Android.
  - iOS needs an Apple developer account for a device build; until then use Expo Go on iPhone.
- `app.config.ts` reads `EXPO_PUBLIC_SUPABASE_URL` and `EXPO_PUBLIC_SUPABASE_ANON_KEY`.
- Permissions copy: location "Signals uses your location only while you search or raise a signal." Camera "To scan registration QR codes."

## 10. Security checklist (verify before launch)

- RLS enabled on every table; test with two accounts that user A cannot read or change user B's rows.
- A normal user cannot set `paid` or `checked_in` (try it from the client and expect denial).
- Coordinator A cannot edit coordinator B's event.
- Storage upload is denied outside the user's own folder, and files over 2 MB or non images are rejected.
- No service role key in any client bundle (`grep` the build output).
- Rate limit signal creation (max 5 open signals per user, 10 messages per minute) with a trigger or constraint.
- Report and block work from signal detail and chat.
- Do not run load or security tests against the production Supabase project or the live Fiesta site. Use a separate staging project.

## 11. Build phases (give these one at a time)

**Phase 1: Foundation.** Create the monorepo, tokens package, Supabase project files, migrations 001 and 002, seed data (one fest with 4 events, 6 signals), `.env.example`. Done when `supabase db reset` runs and RLS tests pass.

**Phase 2: Auth and shell (web and mobile).** Splash, welcome, signup, login, 6 box OTP, interests, permissions, tab shell with the 3D nav, Home skeleton. Done when a real email code signs a user in on web and in Expo Go.

**Phase 3: Signals.** Choose, permission, radar search with `nearby_signals`, raise, raised, mine, detail, chat with realtime, inbox, report and block. Done when two phones can raise, find and chat.

**Phase 4: Me and settings.** Profile card, QR with Share, edit profile, settings, notifications, offline QR, sign out, delete account.

**Phase 5: Events and registration.** Home fest card, events tab, event detail, self-register by QR, my QR, event map with the desk as stop 1.

**Phase 6: Host your event.** About host, type, start, hub, seven steps, publish with audience, live page, share link and QR poster, laptop layout with top nav.

**Phase 7: Fest mode.** Theme switch, Stalls and shows, competitions, shows, stalls, leaderboard, hunt, profile with registered QR, back to Signals.

**Phase 8: Coordinator and desk.** Roles by host, scan with offline verify, lists, winners, desk ledger and mark paid, laptop layouts.

**Phase 9: Polish and release.** Offline and slow network states everywhere, update banner, push notifications, accessibility pass, Lighthouse PWA 90+, Cloudflare Pages deploy, EAS preview APK.

## 12. Prompt to paste into Antigravity at the start of every phase

> You are building the Signals app from `SIGNALS_BUILD_SPEC.md`. Work only on Phase N. Follow section 1 rules and the design tokens in section 3. Do not change anything outside this phase. Write the code, run the type check and tests, and list what you built, what is stubbed, and any decision you made that the spec did not cover. Do not commit secrets. Ask me before adding any paid service or new dependency that is heavier than 100 KB.

## 13. Things you must give Antigravity (the owner supplies)

- A new Supabase project URL and anon key (put in `.env`, never in chat).
- Brevo SMTP credentials (enter in the Supabase dashboard).
- Real fest name, dates, venues, sponsor logos, the Fiesta'26 logo file.
- The final Signals logo files (SVG) and app icon.
- Your Cloudflare account for Pages, and an Expo account for EAS.

## 14. Reference

- Approved design canvas (every screen above): https://claude.ai/artifact/Tw3gNXu3asQUjeXGXW2JVe
- Working web prototype of Phase 2 to 4 (Next.js static, mock data) is in `signals-app.zip`. Use it as a visual reference only; rebuild on Vite as specified here.
- Other docs in this kit: `PLATFORM_HOST_YOUR_EVENT.md` (roles, QR, desk, publish rules), `APP_MAP.md`, `HOSTING_CLOUDFLARE.md`.
