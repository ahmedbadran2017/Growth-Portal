<template>
  <div class="card p-3.5">
    <div class="text-[10px] font-bold uppercase tracking-wide text-ink-400">{{ label }}</div>
    <div class="flex items-baseline gap-1.5 mt-0.5">
      <span class="figure text-[22px] font-extrabold leading-none" :style="color ? { color } : {}">
        {{ shown }}
      </span>
      <span v-if="unit" class="text-[10px] font-bold text-ink-400">{{ unit }}</span>
      <span v-if="sub" class="figure text-xs font-bold text-ink-500 ms-auto">{{ sub }}</span>
    </div>
    <Sparkline v-if="series?.length > 1" class="mt-2" :values="series" :color="color || '#a8a29e'" />
  </div>
</template>

<script setup>
import { computed } from "vue";
import Sparkline from "./Sparkline.vue";
import { money } from "../api.js";

const props = defineProps({
  label: String,
  value: [Number, String],
  unit: String,
  sub: String,
  color: String,
  series: { type: Array, default: () => [] },
});

// A percentage rounded to a whole number loses the digit that matters:
// 81.3 and 81.7 are a different confirmation rate, and money() would show
// both as 81.
const shown = computed(() => {
  if (props.value == null) return "—";
  return props.unit === "%" ? Number(props.value).toFixed(1) : money(props.value);
});
</script>
