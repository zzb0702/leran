/** Minimal inline SVG icon set (stroke-based, currentColor). */

const base = {
  width: 18,
  height: 18,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

export function IconHome() {
  return (
    <svg {...base}>
      <path d="M3 10.5 12 3l9 7.5" />
      <path d="M5 9.5V21h14V9.5" />
      <path d="M9.5 21v-6h5v6" />
    </svg>
  );
}

export function IconMedia() {
  return (
    <svg {...base}>
      <rect x="2.5" y="4" width="19" height="16" rx="3" />
      <path d="m10 9 5 3-5 3z" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function IconBook() {
  return (
    <svg {...base}>
      <path d="M4 4.5A2.5 2.5 0 0 1 6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5z" />
      <path d="M4 17.5h16" />
    </svg>
  );
}

export function IconRepeat() {
  return (
    <svg {...base}>
      <path d="M17 2.5 21 6.5l-4 4" />
      <path d="M3 11V9a3 3 0 0 1 3-3h15" />
      <path d="M7 21.5 3 17.5l4-4" />
      <path d="M21 13v2a3 3 0 0 1-3 3H3" />
    </svg>
  );
}

export function IconGraph() {
  return (
    <svg {...base}>
      <circle cx="12" cy="12" r="2.6" />
      <circle cx="4.5" cy="5.5" r="1.8" />
      <circle cx="19.5" cy="5.5" r="1.8" />
      <circle cx="5" cy="18.5" r="1.8" />
      <circle cx="19" cy="18.5" r="1.8" />
      <path d="M6 6.8 10 10m8-3.2L14 10M6.4 17.4 10 14m7.6 3.4L14 14" />
    </svg>
  );
}

export function IconGear() {
  return (
    <svg {...base}>
      <circle cx="12" cy="12" r="3.2" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .34 1.87l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.7 1.7 0 0 0-1.87-.34 1.7 1.7 0 0 0-1 1.55V21a2 2 0 1 1-4 0v-.09a1.7 1.7 0 0 0-1-1.55 1.7 1.7 0 0 0-1.87.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.7 1.7 0 0 0 .34-1.87 1.7 1.7 0 0 0-1.55-1H3a2 2 0 1 1 0-4h.09a1.7 1.7 0 0 0 1.55-1 1.7 1.7 0 0 0-.34-1.87l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.7 1.7 0 0 0 1.87.34h.09a1.7 1.7 0 0 0 1-1.55V3a2 2 0 1 1 4 0v.09a1.7 1.7 0 0 0 1 1.55 1.7 1.7 0 0 0 1.87-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.7 1.7 0 0 0-.34 1.87v.09a1.7 1.7 0 0 0 1.55 1H21a2 2 0 1 1 0 4h-.09a1.7 1.7 0 0 0-1.55 1z" />
    </svg>
  );
}

export function IconSun() {
  return (
    <svg {...base} width={28} height={28}>
      <circle cx="12" cy="12" r="4.2" />
      <path d="M12 2.5v2.4M12 19.1v2.4M2.5 12h2.4M19.1 12h2.4M5 5l1.7 1.7M17.3 17.3 19 19M19 5l-1.7 1.7M6.7 17.3 5 19" />
    </svg>
  );
}

export function IconMoon() {
  return (
    <svg {...base} width={28} height={28}>
      <path d="M20.5 14.5A8.5 8.5 0 0 1 9.5 3.5a8.5 8.5 0 1 0 11 11z" />
    </svg>
  );
}

export function IconPlay() {
  return (
    <svg {...base} width={14} height={14}>
      <path d="M6 4.5 19 12 6 19.5z" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function IconArrow() {
  return (
    <svg {...base} width={14} height={14}>
      <path d="M4 12h15M13 6l6 6-6 6" />
    </svg>
  );
}

export function IconClock() {
  return (
    <svg {...base}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3.2 2" />
    </svg>
  );
}

export function IconChart() {
  return (
    <svg {...base}>
      <path d="M4 20V10M10 20V4M16 20v-8M22 20H2" />
    </svg>
  );
}

export function IconQuote() {
  return (
    <svg {...base} width={22} height={22} fill="currentColor" stroke="none">
      <path d="M4 6h6v6H7c0 2 1 3 3 3.4V18c-3.8-.4-6-2.7-6-7zm10 0h6v6h-3c0 2 1 3 3 3.4V18c-3.8-.4-6-2.7-6-7z" />
    </svg>
  );
}

export function IconLeaf() {
  return (
    <svg width={20} height={20} viewBox="0 0 24 24" fill="#2f7d54" stroke="none">
      <path d="M20 3s-9-1-14 4C2.5 10.5 3 17 3 17s1 .5 3.5.5c0 0-1.5-6 2.5-10-2 5-1 9.5-1 9.5S12 20 16 17c5-3.7 4-14 4-14z" />
    </svg>
  );
}
