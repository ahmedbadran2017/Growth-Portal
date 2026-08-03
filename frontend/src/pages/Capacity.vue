<template>
  <div class="space-y-4">
    <!-- The sentence every scaling decision actually turned on, assembled
         rather than left for the reader to derive from a table. -->
    <div class="card-raised p-4" :class="cap.budget_capped ? '' : 'border-amber-200'">
      <div class="flex items-start gap-2.5">
        <span class="w-9 h-9 rounded-xl grid place-items-center shrink-0"
              :class="cap.budget_capped ? 'bg-teal-50 text-teal-600' : 'bg-amber-50 text-amber-600'">
          <NavIcon name="gauge" :size="18" />
        </span>
        <div class="min-w-0">
          <div class="text-sm font-bold leading-snug">{{ cap.headline }}</div>
          <div v-if="cap.totals?.utilization != null" class="mt-1.5 flex items-baseline gap-2">
            <span class="figure text-2xl font-extrabold"
                  :style="{ color: cap.totals.utilization >= 85 ? '#0d9488' : cap.totals.utilization <= 40 ? '#be123c' : '#a16207' }">
              {{ cap.totals.utilization }}%
            </span>
            <span class="text-[11px] text-ink-400">
              {{ t("of authorised budget used") }} ·
              <b class="figure">{{ money(cap.totals.spend) }}</b> {{ t("of") }}
              <b class="figure">{{ money(cap.totals.authorised) }}</b>
            </span>
          </div>
        </div>
      </div>
    </div>

    <div v-if="!rows.length" class="card p-8 text-center text-sm text-ink-400">
      {{ t("No campaign spend in this window") }}
    </div>

    <div v-else class="card overflow-x-auto">
      <table class="w-full text-[12.5px]">
        <thead>
          <tr class="text-[10px] font-bold uppercase tracking-wide text-ink-400 border-b border-ink-200">
            <th class="text-start px-3 py-2">{{ t("Campaign") }}</th>
            <th class="text-start px-3 py-2 w-[150px]">{{ t("Utilization") }}</th>
            <th class="text-end px-3 py-2">{{ t("Spend/day") }}</th>
            <th class="text-end px-3 py-2">{{ t("Budget") }}</th>
            <th class="text-end px-3 py-2">ROAS</th>
            <th class="text-start px-3 py-2">{{ t("Constraint") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.entity_id"
              class="border-b border-ink-100 last:border-0 hover:bg-ink-50/60 transition-colors">
            <td class="px-3 py-2 max-w-[260px]">
              <div dir="auto" class="font-semibold text-ink-800 truncate" :title="r.label">{{ r.label }}</div>
              <span class="text-[10px] font-bold uppercase tracking-wide text-ink-400">
                {{ PLATFORM[r.platform] || r.platform }}
              </span>
            </td>

            <td class="px-3 py-2">
              <div v-if="r.utilization != null" class="flex items-center gap-1.5">
                <div class="meter flex-1">
                  <div class="fill" :style="{ width: Math.min(100, r.utilization) + '%', background: c(r) }" />
                  <!-- The cap line. Anything reaching it is asking for money;
                       anything far below it will not spend what it already has. -->
                  <div class="notch" style="inset-inline-start: 85%" :title="t('budget-capped above here')" />
                </div>
                <span class="figure text-[11px] font-bold w-10 text-end" :style="{ color: c(r) }">
                  {{ r.utilization }}%
                </span>
              </div>
              <span v-else class="text-[11px] text-ink-300">{{ t("no budget data") }}</span>
            </td>

            <td class="px-3 py-2 text-end figure font-bold">{{ money(r.spend_per_day) }}</td>
            <td class="px-3 py-2 text-end figure text-ink-500">{{ r.budget != null ? money(r.budget) : "—" }}</td>
            <td class="px-3 py-2 text-end figure font-bold"
                :style="{ color: r.roas >= 5 ? '#0d9488' : r.roas >= 2 ? '#a16207' : '#be123c' }">
              {{ r.roas != null ? r.roas + "x" : "—" }}
            </td>
            <td class="px-3 py-2">
              <Pill :label="t(LABEL[r.constraint])" :color="CC[r.constraint].c" :bg="CC[r.constraint].b" dot />
              <div v-if="r.delivery_status" class="text-[10px] text-ink-400 font-mono mt-0.5 truncate max-w-[160px]"
                   :title="r.delivery_status">{{ r.delivery_status }}</div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <p v-if="cap.no_budget_data" class="text-[11px] text-amber-700">
      {{ t("{0} campaign(s) have no budget data — their capacity is unknown, not unlimited.", cap.no_budget_data) }}
    </p>
  </div>
</template>

<script setup>
import { computed } from "vue";
import NavIcon from "../components/NavIcon.vue";
import Pill from "../components/Pill.vue";
import { money } from "../api.js";
import { useI18n } from "../composables/useI18n";

const { t } = useI18n();
const props = defineProps({ capacity: Object });

const PLATFORM = { meta: "Meta", google_ads: "Google", tiktok: "TikTok" };
const LABEL = { budget: "Budget-capped", delivery: "Delivery-limited", none: "Normal", unknown: "Unknown" };
const CC = {
  budget: { c: "#0d9488", b: "#ccfbf1" },
  delivery: { c: "#be123c", b: "#ffe4e6" },
  none: { c: "#57534e", b: "#f5f5f4" },
  unknown: { c: "#a8a29e", b: "#fafaf9" },
};

const cap = computed(() => props.capacity || {});
const rows = computed(() => cap.value.rows || []);
const c = (r) => (r.utilization >= 85 ? "#0d9488" : r.utilization <= 40 ? "#be123c" : "#a16207");
</script>
