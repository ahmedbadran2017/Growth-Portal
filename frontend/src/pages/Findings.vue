<template>
  <div class="space-y-3">
    <div v-if="!findings.length" class="card p-8 text-center">
      <div class="w-11 h-11 mx-auto rounded-2xl bg-ink-100 text-ink-400 grid place-items-center">
        <NavIcon name="flag" :size="20" />
      </div>
      <p class="mt-3 text-sm font-semibold text-ink-700">{{ t("No open findings") }}</p>
      <p class="mt-1 text-xs text-ink-400">{{ t("The analyst runs at 09:00, after the day is mature enough to judge.") }}</p>
    </div>

    <article v-for="f in findings" :key="f.name" class="card p-4 fade-up">
      <div class="flex items-start gap-2.5">
        <Pill :label="t(f.severity)" :color="SEV[f.severity].color" :bg="SEV[f.severity].bg" dot />
        <span class="text-[11px] text-ink-400 font-mono ms-auto">{{ f.creation?.slice(0, 16) }}</span>
      </div>

      <h3 class="mt-2.5 text-sm font-bold text-ink-900 leading-snug">{{ f.title }}</h3>
      <p class="mt-2 text-xs text-ink-600 leading-relaxed">{{ f.body }}</p>

      <!-- A finding without a re-checkable denominator is an opinion. The tool
           that writes these rejects one that arrives without evidence. -->
      <div v-if="f.evidence" class="mt-3 pt-3 border-t border-ink-100 flex flex-wrap gap-x-4 gap-y-1.5">
        <div v-for="(val, key) in shownEvidence(f)" :key="key">
          <div class="text-[10px] font-semibold uppercase tracking-wide text-ink-400">{{ t(LBL[key] || key) }}</div>
          <div class="text-[11.5px] font-mono text-ink-700">{{ val }}</div>
        </div>
      </div>
    </article>
  </div>
</template>

<script setup>
import NavIcon from "../components/NavIcon.vue";
import Pill from "../components/Pill.vue";
import { useI18n } from "../composables/useI18n";

const { t } = useI18n();

defineProps({ findings: Array });

const SEV = {
  Critical: { color: "#be123c", bg: "#ffe4e6" },
  High: { color: "#c2410c", bg: "#ffedd5" },
  Medium: { color: "#b45309", bg: "#fef3c7" },
  Low: { color: "#57534e", bg: "#f5f5f4" },
};

const LBL = {
  numerator: "Numerator",
  denominator: "Denominator",
  denominator_source: "Denominator source",
  window_start: "From",
  window_end: "To",
};

function shownEvidence(f) {
  const ev = typeof f.evidence === "string" ? JSON.parse(f.evidence || "{}") : f.evidence || {};
  const { query_ref, ...rest } = ev;
  return rest;
}
</script>
