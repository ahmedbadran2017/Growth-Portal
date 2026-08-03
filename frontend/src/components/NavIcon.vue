<template>
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
    :width="size"
    :height="size"
    :class="flip ? 'rtl:-scale-x-100' : ''"
  >
    <component :is="el.tag" v-for="(el, i) in shapes" :key="i" v-bind="el.attrs" />
  </svg>
</template>

<script setup>
// The app's single icon set (lucide-style strokes) — data-driven so adding a
// glyph is one line, and every emoji in the UI has a crisp vector twin.
import { computed } from "vue";

const p = (d) => ({ tag: "path", attrs: { d } });
const c = (cx, cy, r, extra = {}) => ({ tag: "circle", attrs: { cx, cy, r, ...extra } });
const rc = (x, y, width, height, rx) => ({ tag: "rect", attrs: { x, y, width, height, rx } });
const ln = (x1, y1, x2, y2) => ({ tag: "line", attrs: { x1, y1, x2, y2 } });

const ICONS = {
  dashboard: [rc(3, 3, 7, 9, 1.5), rc(14, 3, 7, 5, 1.5), rc(14, 12, 7, 9, 1.5), rc(3, 16, 7, 5, 1.5)],
  board: [rc(3, 3, 18, 18, 2), p("M8 7v7"), p("M12 7v4"), p("M16 7v9")],
  list: [ln(8, 6, 21, 6), ln(8, 12, 21, 12), ln(8, 18, 21, 18), ln(3, 6, 3.01, 6), ln(3, 12, 3.01, 12), ln(3, 18, 3.01, 18)],
  user: [p("M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"), c(12, 7, 4)],
  bell: [p("M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"), p("M10.3 21a1.94 1.94 0 0 0 3.4 0")],
  users: [p("M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"), c(9, 7, 4), p("M22 21v-2a4 4 0 0 0-3-3.87"), p("M16 3.13a4 4 0 0 1 0 7.75")],
  settings: [
    p("M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"),
    c(12, 12, 3),
  ],

  // status / KPI
  "circle-dot": [c(12, 12, 10), c(12, 12, 1.5)],
  "circle-dashed": [c(12, 12, 9.5, { "stroke-dasharray": "4.2 4.2" })],
  inbox: [p("M22 12h-6l-2 3h-4l-2-3H2"), p("M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11")],
  flag: [p("M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"), ln(4, 22, 4, 15)],
  alarm: [c(12, 13, 8), p("M12 9v4l2 2"), p("M5 3 2 6"), p("m22 6-3-3")],
  clock: [c(12, 12, 10), p("M12 6v6l4 2")],
  hourglass: [p("M5 22h14"), p("M5 2h14"), p("M17 22v-4.172a2 2 0 0 0-.586-1.414L12 12l-4.414 4.414A2 2 0 0 0 7 17.828V22"), p("M7 2v4.172a2 2 0 0 0 .586 1.414L12 12l4.414-4.414A2 2 0 0 0 17 6.172V2")],
  check: [p("M20 6 9 17l-5-5")],
  "check-circle": [c(12, 12, 10), p("m9 12 2 2 4-4")],
  x: [p("M18 6 6 18"), p("m6 6 12 12")],

  // actions & metadata
  paperclip: [p("m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48")],
  sparkles: [p("M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"), p("M20 3v4"), p("M22 5h-4")],
  eye: [p("M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"), c(12, 12, 3)],
  calendar: [rc(3, 4, 18, 18, 2), p("M8 2v4"), p("M16 2v4"), p("M3 10h18")],
  download: [p("M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"), p("m7 10 5 5 5-5"), p("M12 15V3")],
  link: [p("M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"), p("M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71")],
  message: [p("M7.9 20A9 9 0 1 0 4 16.1L2 22Z")],
  at: [c(12, 12, 4), p("M16 8v5a3 3 0 0 0 6 0v-1a10 10 0 1 0-4 8")],
  pencil: [p("M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z"), p("m15 5 4 4")],
  refresh: [p("M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"), p("M21 3v5h-5"), p("M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"), p("M3 21v-5h5")],
  send: [p("M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z"), p("m21.854 2.147-10.94 10.939")],
  ban: [c(12, 12, 10), p("m4.9 4.9 14.2 14.2")],
  gauge: [p("m12 14 4-4"), p("M3.34 19a10 10 0 1 1 17.32 0")],
  "chevron-down": [p("m6 9 6 6 6-6")],
  // Directional glyphs mirror under RTL via the `flip` prop.
  "chevron-left": [p("m15 18-6-6 6-6")],
  "chevron-right": [p("m9 18 6-6-6-6")],
  file: [p("M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7z"), p("M14 2v4a2 2 0 0 0 2 2h4")],
  "trend-up": [p("M16 7h6v6"), p("m22 7-8.5 8.5-5-5L2 17")],
  globe: [c(12, 12, 10), p("M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"), p("M2 12h20")],
  warning: [p("m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"), p("M12 9v4"), p("M12 17h.01")],
  "check-square": [p("m9 11 3 3L22 4"), p("M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11")],
  "arrow-right": [p("M5 12h14"), p("m12 5 7 7-7 7")],
  trash: [p("M3 6h18"), p("M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"), p("M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"), ln(10, 11, 10, 17), ln(14, 11, 14, 17)],
};

const props = defineProps({
  name: { type: String, required: true },
  size: { type: [Number, String], default: 16 },
  // Directional glyphs (chevrons, arrows) must point the other way in RTL.
  flip: { type: Boolean, default: false },
});

const shapes = computed(() => ICONS[props.name] || []);
</script>
