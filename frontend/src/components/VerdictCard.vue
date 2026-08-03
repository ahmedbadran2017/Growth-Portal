<template>
  <div class="card-raised card-hover verdict-tint p-4 ps-5" :style="{ '--vc': meta.color }">
    <div class="flex items-start justify-between gap-2">
      <div class="flex items-center gap-1.5 min-w-0">
        <Pill :label="t(meta.label)" :color="meta.color" :bg="meta.bg" :ring="meta.ring" dot />
        <!-- Which platform's accounting produced this number. Meta at 8.5 and
             TikTok at 14.7 were never on the same scale, so the badge is not
             decoration — it names the baseline the verdict was judged against. -->
        <span
          v-if="ev.platform"
          class="text-[10px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded-md bg-ink-100 text-ink-500"
        >{{ PLATFORM[ev.platform] || ev.platform }}</span>
      </div>
      <div class="text-end">
        <div
          v-if="v.impact_mad"
          class="figure text-[26px] font-extrabold leading-none"
          :style="{ color: meta.color }"
        >
          {{ money(v.impact_mad) }}
        </div>
        <div v-if="v.impact_mad" class="text-[10px] font-semibold text-ink-400 mt-0.5">{{ t("MAD/mo") }}</div>
        <div v-else class="text-[11px] text-ink-400">{{ t("No estimated impact") }}</div>
      </div>
    </div>

    <!-- dir="auto" because product names are Turkish or French inside an RTL
         page; without it the bidi algorithm moves a leading number to the end
         and "12 Li Standlı…" becomes a different name on screen. -->
    <p
      dir="auto"
      class="mt-2.5 text-sm font-semibold text-ink-900 leading-snug line-clamp-2"
      :title="v.entity_label"
    >
      {{ v.entity_label }}
    </p>
    <p class="mt-1 text-xs text-ink-500">{{ headline }}</p>

    <div v-if="ev.baseline != null" class="mt-3">
      <div class="meter">
        <div class="fill" :style="{ width: scaled(rate) + '%', background: meta.color }" />
        <div
          class="notch"
          :style="{ insetInlineStart: scaled(ev.baseline) + '%' }"
          :title="`${t('baseline')} ${fmt(ev.baseline)}`"
        />
      </div>
      <div class="flex items-center justify-between mt-1.5 text-[11px] text-ink-400">
        <span class="figure font-bold text-[13px]" :style="{ color: meta.color }">{{ fmt(rate) }}</span>
        <span>{{ t("baseline") }} <span class="figure">{{ fmt(ev.baseline) }}</span></span>
      </div>

      <Sparkline
        v-if="ev.series?.length"
        class="mt-2"
        :values="ev.series"
        :baseline="ev.baseline"
        :color="meta.color"
      />
    </div>

    <p class="mt-2.5 text-xs text-ink-700 leading-relaxed">{{ v.recommended_action }}</p>

    <!-- TikTok keeps moving for 48h and PMAX for 72h. A window containing
         provisional days is understated by an unknown amount, and that belongs
         next to the number rather than in a footnote. -->
    <div
      v-if="ev.provisional_days"
      class="mt-2 inline-flex items-center gap-1.5 text-[11px] text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-2 py-1"
    >
      <NavIcon name="hourglass" :size="11" />
      {{ ev.provisional_days }} {{ t("days still maturing — this is a floor, not a final number") }}
    </div>

    <!-- The failure mix is what turns a verdict into an assignment: refusals go
         to the product page, unreachable goes to lead quality, phone
         cancellations go to the confirmation desk. -->
    <div v-if="ev.dominant_failure" class="mt-3 rounded-xl bg-ink-50 border border-ink-200/60 px-3 py-2">
      <div class="flex items-center gap-1.5 flex-wrap">
        <span class="text-[10px] font-bold uppercase tracking-wide text-ink-400">{{ t("Largest failure source") }}</span>
        <span class="text-xs font-bold text-ink-800">
          {{ t(OWNER[ev.dominant_failure] || ev.dominant_failure) }}
        </span>
      </div>
      <div class="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-ink-500">
        <span v-for="m in mix" :key="m.k">
          {{ t(m.k) }} <b class="font-mono font-semibold text-ink-700">{{ m.n }}</b>
        </span>
      </div>
    </div>

    <!-- Evidence is open, not behind a toggle. Every number here can be
         re-derived from what is printed, because the failure this portal exists
         to prevent is acting on a number nobody checked. -->
    <div class="mt-3 pt-3 border-t border-ink-100">
      <div class="grid grid-cols-2 gap-x-3 gap-y-1.5">
        <div v-for="f in facts" :key="f.k">
          <div class="text-[10px] font-semibold uppercase tracking-wide text-ink-400">{{ t(f.k) }}</div>
          <div class="text-[11.5px] text-ink-700" :class="f.mono ? 'font-mono' : ''">{{ f.v }}</div>
        </div>
      </div>

      <button
        class="mt-2.5 inline-flex items-center gap-1 text-[11px] font-semibold text-ink-400 hover:text-brand-600 transition-colors"
        @click="showQuery = !showQuery"
      >
        <NavIcon name="chevron-down" :size="12" :class="showQuery ? 'rotate-180' : ''" />
        {{ t("Query") }}
      </button>
      <p v-if="showQuery" class="mt-1 text-[10.5px] leading-relaxed text-ink-400 font-mono">
        {{ v.query_ref }}
      </p>

      <div class="mt-3 flex items-center gap-1.5">
        <button
          class="btn-outline !px-2.5 !py-1 !text-[11px]"
          :disabled="!live"
          @click="$emit('act', v, 'Acknowledged')"
        >
          {{ t("Acknowledge") }}
        </button>
        <button
          class="btn-primary !px-2.5 !py-1 !text-[11px]"
          :disabled="!live"
          @click="$emit('act', v, 'Actioned')"
        >
          {{ t("Actioned") }}
        </button>
        <button
          class="btn-ghost !px-2.5 !py-1 !text-[11px] ms-auto"
          :disabled="!live"
          @click="$emit('act', v, 'Dismissed')"
        >
          {{ t("Dismiss") }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";
import Pill from "./Pill.vue";
import NavIcon from "./NavIcon.vue";
import Sparkline from "./Sparkline.vue";
import { money, pct, state } from "../api.js";
import { VERDICT, OWNER } from "../verdicts.js";
import { useI18n } from "../composables/useI18n";

const { t } = useI18n();

const PLATFORM = { meta: "Meta", google_ads: "Google", tiktok: "TikTok", erpnext: "ERP" };

const props = defineProps({ v: Object });
defineEmits(["act"]);

const showQuery = ref(false);
const live = computed(() => state.live !== false);
const meta = computed(() => VERDICT[props.v.verdict] || VERDICT.Watch);
const ev = computed(() => props.v.evidence || {});
const rate = computed(() =>
  ev.value.value != null ? ev.value.value : (props.v.numerator / props.v.denominator) * 100
);
const headline = computed(() => props.v.headline.replace(props.v.entity_label + ": ", ""));

// Delivery rate is a percentage; ROAS is a multiple. Printing "8.5%" for a
// ROAS of 8.5 would be a different claim entirely.
const isRatio = computed(() => props.v.metric === "roas");
const fmt = (n) => (n == null ? "—" : isRatio.value ? `${pct(n, 2)}x` : `${pct(n)}%`);

// A meter fixed at 0-100 is useless for ROAS, where the interesting range sits
// between 1 and 20. Scale against the pair being compared instead.
function scaled(n) {
  if (n == null) return 0;
  if (!isRatio.value) return Math.min(100, n);
  const top = Math.max(rate.value || 0, ev.value.baseline || 0) * 1.25 || 1;
  return Math.min(100, (n / top) * 100);
}

const mix = computed(() =>
  [
    { k: "Confirmation", n: ev.value.cancelled_confirm },
    { k: "Unreachable", n: ev.value.unreachable },
    { k: "Product refused", n: ev.value.refused_product },
    { k: "Duplicate", n: ev.value.duplicate_or_denied },
  ].filter((m) => m.n)
);

const facts = computed(() => [
  isRatio.value
    ? { k: "Revenue ÷ spend", v: `${money(props.v.numerator)} ÷ ${money(props.v.denominator)}`, mono: true }
    : { k: "Numerator ÷ denominator", v: `${props.v.numerator} ÷ ${props.v.denominator}`, mono: true },
  { k: "Denominator source", v: props.v.denominator_source },
  { k: "Window", v: `${props.v.window_start} → ${props.v.window_end}`, mono: true },
  { k: "Sample", v: props.v.sample_size, mono: true },
  ...(ev.value.cpa ? [{ k: "Cost per purchase", v: money(ev.value.cpa), mono: true }] : []),
  ...(ev.value.currency ? [{ k: "Currency", v: ev.value.currency }] : []),
]);
</script>
