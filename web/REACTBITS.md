# React Bits Integration & Motion Safety Registry

This document lists all **React Bits** components integrated into the **TriageRAG Console**, including their styling variants, licenses, performance characteristics, and motion-safety fallbacks.

## Clinical Safety UX Inviolable Rule
> [!IMPORTANT]
> **SafetyBanner, alerts, blocked drugs, skipped checks, coverage gaps, and the disclaimer must NEVER be animated, delayed, or obscured.**
> All safety-critical elements render immediately, synchronously, and statically. No React Bits or Framer Motion transitions are permitted on safety output containers.

---

## Motion Safety Architecture

Every animated component integrates with `useMotionOk()` from `@/lib/motion`:
1. **System Reduced Motion:** Automatically queries `(prefers-reduced-motion: reduce)`. If preferred, all animations, particles, spring physics, and canvas rendering are disabled.
2. **User Motion Toggle:** Clinicians can toggle animations on or off via the header toggle. The preference is stored in `localStorage` under `triagerag-motion-pref`.
3. **`<Motion>` Guard:** Any decorative wrapper uses `<Motion fallback={<StaticFallback />}>` ensuring zero animation delay when motion is turned off.

---

## Component Catalog

| Component | Variant | Purpose / Route | Performance Cost | Reduced-Motion Fallback |
| :--- | :--- | :--- | :--- | :--- |
| **`Particles`** | Canvas 2D / TS | Ambient hero background (`/`, `/about`, `/evidence`) | Low (~0.1ms/frame, auto-resizing, 40 particles) | Unmounts canvas, returns `null` |
| **`SplitText`** | Framer Motion / TS | Route titles & non-safety headers | Negligible (one-shot entrance) | Renders standard un-animated `<span>` |
| **`BlurText`** | Framer Motion / TS | Non-critical subtitles & marketing copy | Negligible (one-shot entrance) | Renders standard un-animated `<span>` |
| **`ShinyText`** | CSS Keyframes / TW | System status pills & mode badges | Minimal (GPU-accelerated CSS gradient) | Renders static solid teal highlight |
| **`Magnet`** | Framer Motion / TS | Non-safety CTAs & navigation links | Very low (pointer event on bounded radius) | Standard inline element with zero offset |
| **`SpotlightCard`** | CSS Radial / TW | Scenario selection & metric cards | Low (local cursor coordinate tracking) | Static card with subtle slate border |
| **`CountUp`** | requestAnimationFrame / TS | Benchmarks & evaluation metrics (`/evidence`) | Low (requestAnimationFrame step loop) | Instantly renders target number |
| **`ClickSpark`** | Canvas 2D / TS | Non-safety button click feedback | Very low (transient short-lived sparks) | Disables canvas completely |

---

## Boundary Enforcement
- Components in `src/features/safety/` or any safety-critical view **MUST NOT** import from `src/components/reactbits/`.
- No clinical dosages, physiological scores, contraindication badges, or override buttons may be wrapped with `Magnet` or animated transitions.
