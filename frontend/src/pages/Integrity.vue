<template>
  <div class="space-y-4">
    <div class="card p-4">
      <div class="flex items-center gap-2.5">
        <span
          class="w-9 h-9 rounded-xl grid place-items-center"
          :class="healthy ? 'bg-teal-50 text-teal-600' : 'bg-rose-50 text-rose-600'"
        >
          <NavIcon :name="healthy ? 'check-circle' : 'warning'" :size="18" />
        </span>
        <div>
          <div class="text-sm font-bold">
            {{ healthy ? t("All sources live") : t("A source or a ratio needs a look") }}
          </div>
          <div class="text-[11px] text-ink-400 font-mono">{{ integrity?.checked_at || "—" }}</div>
        </div>
      </div>
      <p class="mt-3 text-xs text-ink-500 leading-relaxed">
        {{ t("A source silently returning zero rows looks identical to one reporting real zeros. The first is a broken token, the second an emergency — this screen is what tells them apart.") }}
      </p>
    </div>

    <section>
      <h2 class="label">{{ t("Sources") }}</h2>
      <div class="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        <div
          v-for="s in integrity?.syncs || []"
          :key="s.source + s.run_day"
          class="card p-3.5"
          :class="s.ok ? '' : 'border-rose-200 bg-rose-50/50'"
        >
          <div class="flex items-center justify-between gap-2">
            <span class="text-sm font-bold font-mono">{{ s.source }}</span>
            <Pill
              :label="s.ok ? t('Live') : t('Down')"
              :color="s.ok ? '#0d9488' : '#be123c'"
              :bg="s.ok ? '#ccfbf1' : '#ffe4e6'"
              dot
            />
          </div>
          <div class="mt-2 flex items-baseline gap-3 text-[11px] text-ink-400">
            <span><b class="font-mono text-sm text-ink-800">{{ s.rows_written }}</b> {{ t("rows") }}</span>
            <span class="font-mono">{{ s.duration_ms }}ms</span>
            <span class="font-mono ms-auto">{{ s.run_day }}</span>
          </div>
        </div>
      </div>
    </section>

    <!-- Both sides of every ratio come from one system by construction. A
         cross-source ratio moves when either system changes, which makes it
         useless as an alarm. -->
    <section v-if="integrity?.anomalies?.length">
      <h2 class="label">{{ t("Ratios off their baseline") }}</h2>
      <div class="space-y-2">
        <div v-for="a in integrity.anomalies" :key="a.metric + a.day" class="card p-3.5 border-amber-200 bg-amber-50/50">
          <div class="flex items-center justify-between gap-2 flex-wrap">
            <span class="text-sm font-bold font-mono">{{ a.metric }}</span>
            <span dir="ltr" class="text-sm font-extrabold font-mono text-amber-700">
              {{ a.deviation_pct > 0 ? "+" : "" }}{{ a.deviation_pct.toFixed(0) }}%
            </span>
          </div>
          <div class="mt-1.5 flex items-center gap-3 text-[11px] text-ink-500">
            <span>{{ t("Value") }} <b class="font-mono text-ink-800">{{ a.ratio }}</b></span>
            <span>{{ t("Baseline") }} <b class="font-mono text-ink-800">{{ a.baseline }}</b></span>
            <span class="font-mono ms-auto text-ink-400">{{ a.day }}</span>
          </div>
        </div>
      </div>
    </section>

    <section v-if="integrity?.freshness?.length">
      <h2 class="label">{{ t("Latest day with data") }}</h2>
      <div class="card divide-y divide-ink-100">
        <div v-for="f in integrity.freshness" :key="f.source" class="flex items-center justify-between px-4 py-2.5">
          <span class="text-xs font-semibold font-mono text-ink-700">{{ f.source }}</span>
          <span class="text-xs font-mono text-ink-500">{{ f.latest }}</span>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed } from "vue";
import NavIcon from "../components/NavIcon.vue";
import Pill from "../components/Pill.vue";
import { useI18n } from "../composables/useI18n";

const { t } = useI18n();

const props = defineProps({ integrity: Object });

const healthy = computed(
  () =>
    (props.integrity?.syncs || []).every((s) => s.ok) && !(props.integrity?.anomalies || []).length
);
</script>
