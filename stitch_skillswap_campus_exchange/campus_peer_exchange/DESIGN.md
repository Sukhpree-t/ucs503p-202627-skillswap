---
name: Campus Peer Exchange
colors:
  surface: '#f8f9ff'
  surface-dim: '#cbdbf5'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4ff'
  surface-container: '#e5eeff'
  surface-container-high: '#dce9ff'
  surface-container-highest: '#d3e4fe'
  on-surface: '#0b1c30'
  on-surface-variant: '#464555'
  inverse-surface: '#213145'
  inverse-on-surface: '#eaf1ff'
  outline: '#777587'
  outline-variant: '#c7c4d8'
  surface-tint: '#4d44e3'
  primary: '#3525cd'
  on-primary: '#ffffff'
  primary-container: '#4f46e5'
  on-primary-container: '#dad7ff'
  inverse-primary: '#c3c0ff'
  secondary: '#006b5f'
  on-secondary: '#ffffff'
  secondary-container: '#6df5e1'
  on-secondary-container: '#006f64'
  tertiary: '#684000'
  on-tertiary: '#ffffff'
  tertiary-container: '#885500'
  on-tertiary-container: '#ffd4a4'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#e2dfff'
  primary-fixed-dim: '#c3c0ff'
  on-primary-fixed: '#0f0069'
  on-primary-fixed-variant: '#3323cc'
  secondary-fixed: '#71f8e4'
  secondary-fixed-dim: '#4fdbc8'
  on-secondary-fixed: '#00201c'
  on-secondary-fixed-variant: '#005048'
  tertiary-fixed: '#ffddb8'
  tertiary-fixed-dim: '#ffb95f'
  on-tertiary-fixed: '#2a1700'
  on-tertiary-fixed-variant: '#653e00'
  background: '#f8f9ff'
  on-background: '#0b1c30'
  surface-variant: '#d3e4fe'
typography:
  headline-xl:
    fontFamily: Inter
    fontSize: 40px
    fontWeight: '700'
    lineHeight: 48px
    letterSpacing: -0.02em
  headline-xl-mobile:
    fontFamily: Inter
    fontSize: 30px
    fontWeight: '700'
    lineHeight: 38px
    letterSpacing: -0.015em
  headline-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.015em
  headline-lg-mobile:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.005em
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
    letterSpacing: 0em
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
    letterSpacing: 0em
  body-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
    letterSpacing: 0.005em
  label-lg:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: 0.01em
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.02em
  label-sm:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.03em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-desktop: 1.5rem
  margin: 1rem
  margin-tablet: 2rem
  margin-desktop: 3rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2rem
---

## Brand & Style

This design system serves a campus-exclusive, credit-based peer skill exchange. It merges the focused clarity of academic productivity tools with the transactional precision and security of modern fintech. The interface must inspire absolute trust among university students managing their personal time and earned credits, while remaining fluid, approachable, and fast-paced.

The design philosophy balances **Modern Minimalist Utility** with **Fintech Tactility**:
- Structured and systematic: layouts respect strict visual hierarchies, eliminating clutter so students can rapidly verify peer credibility, review escrow status, and execute trades.
- Dependable and transparent: micro-interactions, ledger badges, and escrow indicators feel solid and unambiguous.
- High-contrast precision: information architecture prioritizes transactional states (pending, held in escrow, settled) with zero visual ambiguity.

## Colors

The palette establishes an authoritative academic ground accented by vivid transaction signifiers.

### Role Allocation
- **Primary (`#4F46E5` / Indigo):** Anchors brand presence, key navigation nodes, primary submission actions, and verified academic identity verification markers.
- **Secondary / Earning / Growth (`#14B8A6` / Teal):** Direct signifier for credit acquisition, completed trades, skill gain indicators, and positive ledger actions.
- **Tertiary / Escrow / Attention (`#F59E0B` / Amber):** Highlights active escrows, pending session swaps, timer alerts, and states requiring mutual student confirmation.
- **Critical / Danger (`#EF4444` / Red):** Reserved strictly for trade disputes, cancellation confirmations, and validation alerts.
- **Settled / Affirmation (`#22C55E` / Green):** Indicates successful smart confirmations, confirmed release of escrow funds, and online verification presence.
- **Neutral Core (Slate Spectrum):**
  - Dark Slate (`#0F172A`): Primary text in light mode; background base in dark mode.
  - Slate Mid (`#334155`): Secondary copy, structural borders, and subtle icon strokes.
  - Slate Muted (`#64748B`): Meta labels, timestamps, and de-emphasized grid dividers.
  - Canvas Mist (`#F8FAFC`): Base background surface in light mode.

### Theming Behavior
- **Light Theme:** Surfaces rest on `#F8FAFC`, stepping to pure `#FFFFFF` for primary interaction cards, bounded by 1px border lines (`#E2E8F0`).
- **Dark Theme:** Surfaces invert to `#0F172A` canvas with elevated card surfaces at `#1E293B` and borders at `#334155`. State accents maintain minimum 4.5:1 contrast ratios across both modes.

## Typography

The type architecture relies entirely on `Inter` to project structured neutrality, legibility, and technical accuracy.

- **Headlines:** Use weights `600` (Semi-Bold) and `700` (Bold) with tightened tracking (`-0.01em` to `-0.02em`) to produce authoritative, confident anchors for balance cards, skill titles, and profile headers.
- **Body Text:** Maintained strictly at weight `400` with open line heights (`1.5` to `1.55`) for effortless scanning of exchange terms, syllabi outlines, and messaging threads.
- **Financial & Numeric Data:** Credit ledger quantities, swap rates, and time logs utilize tabular numeric alignment (`tnum`) to ensure aligned balances within statement modules and swap summaries.
- **Labels & Badges:** Use weight `600` with subtle letter-spacing for upper and mixed-case credit chips, escrow tags, and campus domain pills.

## Layout & Spacing

The layout model is anchored by an 8px vertical baseline rhythm and an adaptable fluid grid tailored to student usage across desktop labs, laptop libraries, and mobile campus transit:

- **Desktop (>= 1200px):** 12-column fluid grid, `3rem` (48px) margins, and `1.5rem` (24px) gutters. Maximizes dashboard efficiency with side-by-side ledger history, incoming request queues, and skill discovery.
- **Tablet (768px – 1199px):** 8-column fluid grid with `2rem` (32px) margins and `1rem` (16px) gutters. Multi-column transactions stack into modular card feeds.
- **Mobile (< 768px):** 4-column layout with `1rem` (16px) margins and `1rem` (16px) gutters. Actions shift to thumb-zone friendly bottom sheets and persistent lower action decks for rapid trade handshakes.

## Elevation & Depth

Visual hierarchy employs a refined combination of **tonal surface layering**, **ultra-diffused ambient shadows**, and **crisp micro-borders**:

- **Card Surfaces:** Standard card containers do not rely on heavy drop shadows. They use crisp 1px borders (`#E2E8F0` in light; `#334155` in dark) layered with an ambient shadow: `box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04), 0 4px 12px rgba(15, 23, 42, 0.03)`.
- **Interactive Hover & Drag:** On hover, skill cards and trade rows elevate smoothly using `box-shadow: 0 6px 20px rgba(79, 70, 229, 0.08)`, gently pulling primary brand hue into the elevation physics.
- **Escrow & Transaction Modals:** Crucial confirmation modals and swap sheets float at the highest elevation tier with a diffused dark shadow (`box-shadow: 0 20px 40px -8px rgba(15, 23, 42, 0.16)`) and a background blur (`backdrop-filter: blur(8px)`) applied to the backing scrim.

## Shapes

The shape hierarchy is approachable yet structured, utilizing consistent corner curvatures to differentiate cards from operational interactive elements:

- **Primary Cards & Containers:** Styled with `rounded-2xl` (1rem / 16px) to yield modern, comfortable containers for peer profiles, session details, and credit logs.
- **Input Controls & Secondary Modules:** Utilize `rounded-lg` (0.5rem / 8px) for buttons, search inputs, and modal wrappers to reinforce operational discipline.
- **Chips, Badges, and Micro-Indicators:** Adopt full pills (`rounded-full` / 9999px) to distinctly isolate monetary balances, verified university status badges, and availability tags from block-level layouts.

## Components

### Buttons & Interactive Triggers
- **Primary ("Initiate Swap"):** Deep Indigo background (`#4F46E5`), white text (`#FFFFFF`), `rounded-lg` border radius, semi-bold typography. 44px minimum height for optimal mobile tap-targets. Interactive state: darken to `#4338CA` on hover.
- **Secondary / Action ("Accept Credit"):** Teal accent (`#14B8A6`) or Indigo outline with 1.5px border width and soft tint fill on hover (`rgba(79, 70, 229, 0.04)`).
- **Destructive ("Dispute / Cancel"):** Subtle red tint background (`#FEF2F2`) with red label (`#EF4444`) shifting to solid red fill on explicit confirmation.

### Credit Chips & Status Badges
- **Credit Balance Chip (`1 cr`, `5 cr`):** Pill-shaped container (`rounded-full`) with an ultra-fine border. Uses deep Indigo or Teal typography paired with an 8% opacity tint background of the respective color. Tabular figures ensure numeric consistency.
- **Escrow Status Badges:**
  - *Pending / In Escrow:* Soft amber tint background (`#FEF3C7`), dark amber text (`#B45309`), accompanied by a miniature clock or lock icon.
  - *Settled / Released:* Mint/green tint background (`#DCFCE7`), deep green text (`#15803D`), accompanied by a verified checkmark icon.

### Cards (Skill Exchange & Profile)
- Enclosed with `rounded-2xl` corners, 1px perimeter border, and subtle ambient shadow.
- Divided cleanly into: header (peer profile, verified major, and rating), core offering (skill offered vs. skill requested), and footer metadata (credit fee and swap availability).

### Input Fields & Controls
- **Inputs:** 1px border (`#CBD5E1`), 8px radius (`rounded-lg`), 16px interior padding. On focus, triggers an Indigo border highlight (`#4F46E5`) accompanied by an indigo ring glow (`0 0 0 3px rgba(79, 70, 229, 0.15)`).
- **Checkboxes & Radios:** Rounded square / circle with 2px solid border, transitioning to solid Indigo fill with crisp white iconography upon selection.

### Campus Verification Banner
- Distinctive structural module pinned to peer profiles showing confirmed `.edu` / university institution credentials, styled with an Indigo-to-Teal ambient micro-gradient border to guarantee trust before trade execution.