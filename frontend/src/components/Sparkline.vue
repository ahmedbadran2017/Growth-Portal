<template>
  <svg v-if="pts.length > 1" class="spark" :viewBox="`0 0 ${W} ${H}`" preserveAspectRatio="none">
    <defs>
      <linearGradient :id="gid" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" :stop-color="color" stop-opacity="0.20" />
        <stop offset="100%" :stop-color="color" stop-opacity="0" />
      </linearGradient>
    </defs>

    <!-- The peer baseline, drawn behind the series. A line without its
         reference is a shape, not a judgement. -->
    <line
      v-if="baseY !== null"
      :x1="0" :x2="W" :y1="baseY" :y2="baseY"
      stroke="#a8a29e" stroke-width="1" stroke-dasharray="3 3" vector-effect="non-scaling-stroke"
    />

    <path :d="area" :fill="`url(#${gid})`" />
    <path :d="line" fill="none" :stroke="color" stroke-width="1.5"
          stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke" />
    <circle :cx="last.x" :cy="last.y" r="2.5" :fill="color" />
  </svg>

  <!-- Said out loud rather than rendered as an empty box: no history is a
       different state from a flat line. -->
  <div v-else class="text-[10.5px] text-ink-300 h-7 flex items-center">not enough history</div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  values: { type: Array, default: () => [] },
  baseline: { type: Number, default: null },
  color: { type: String, default: "#57534e" },
});

const W = 100;
const H = 28;
// Unique per instance so two sparklines never share a gradient id.
const gid = `sg${Math.random().toString(36).slice(2, 9)}`;

const clean = computed(() => props.values.filter((v) => v !== null && v !== undefined && !isNaN(v)));

const scale = computed(() => {
  const v = clean.value;
  if (!v.length) return null;
  // The baseline is inside the range on purpose — if the series never crosses
  // it, the gap should still be visible rather than clipped off the top.
  const all = props.baseline != null ? [...v, props.baseline] : v;
  const lo = Math.min(...all);
  const hi = Math.max(...all);
  const pad = (hi - lo) * 0.15 || Math.abs(hi) * 0.1 || 1;
  return { lo: lo - pad, hi: hi + pad };
});

const pts = computed(() => {
  const v = clean.value;
  const s = scale.value;
  if (!s || v.length < 2) return [];
  const span = s.hi - s.lo || 1;
  return v.map((val, i) => ({
    x: (i / (v.length - 1)) * W,
    y: H - ((val - s.lo) / span) * H,
  }));
});

const baseY = computed(() => {
  const s = scale.value;
  if (!s || props.baseline == null) return null;
  return H - ((props.baseline - s.lo) / (s.hi - s.lo || 1)) * H;
});

const line = computed(() => pts.value.map((p, i) => `${i ? "L" : "M"}${p.x},${p.y}`).join(" "));
const area = computed(() =>
  pts.value.length ? `${line.value} L${W},${H} L0,${H} Z` : ""
);
const last = computed(() => pts.value[pts.value.length - 1] || { x: 0, y: 0 });
</script>
