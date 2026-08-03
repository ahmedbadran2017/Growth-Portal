<template>
  <span
    class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold whitespace-nowrap"
    :style="{ color, background: bg, boxShadow: ring ? `inset 0 0 0 1px ${ring}` : 'none' }"
  >
    <span v-if="dot" class="w-1.5 h-1.5 rounded-full" :style="{ background: color }" />
    <slot>{{ label }}</slot>
  </span>
</template>

<script setup>
defineProps({
  label: { type: String, default: "" },
  color: { type: String, default: "#475569" },
  bg: { type: String, default: "#f1f5f9" },
  ring: { type: String, default: "" },
  dot: { type: Boolean, default: false },
});
</script>
