<template>
  <div class="space-y-4">
    <!-- Today -->
    <section>
      <h2 class="label">{{ t("Today") }}</h2>
      <div class="grid gap-2.5 grid-cols-2 lg:grid-cols-4 stagger">
        <Kpi :label="t('Orders')" :value="k.today?.orders" :series="series('orders')" color="#d45d3e" />
        <Kpi :label="t('Sales')" :value="k.today?.revenue_mad" unit="MAD" :series="series('revenue_mad')" color="#0d9488" />
        <Kpi :label="t('Ad spend')" :value="k.today?.ad_spend_try" unit="TRY" :series="series('ad_spend_try')" color="#6d28d9" />
        <Kpi :label="t('Confirmation')" :value="k.today?.confirmation_pct" unit="%" :series="series('confirmation_pct')" color="#a16207" />
      </div>
    </section>

    <!-- Month -->
    <section>
      <h2 class="label">{{ t("This month") }}</h2>
      <div class="grid gap-2.5 grid-cols-2 lg:grid-cols-4">
        <Kpi :label="t('Orders')" :value="k.month?.orders" />
        <Kpi :label="t('Sales')" :value="k.month?.revenue_mad" unit="MAD" />
        <Kpi :label="t('Confirmed')" :value="k.month?.confirmed"
             :sub="k.month?.confirmation_pct != null ? `${k.month.confirmation_pct}%` : ''" color="#a16207" />
        <Kpi :label="t('Delivered')" :value="k.month?.delivered"
             :sub="k.month?.delivery_pct != null ? `${k.month.delivery_pct}%` : ''" color="#0d9488" />
      </div>

      <!-- The two rates are measured in two different systems over two
           different denominators. Saying so on the screen stops anyone
           multiplying them into a single funnel number. -->
      <div class="card p-3.5 mt-2.5 grid gap-3 sm:grid-cols-2">
        <div>
          <div class="text-[10px] font-bold uppercase tracking-wide text-ink-400">{{ t("Confirmation rate") }}</div>
          <div class="figure text-lg font-bold text-ink-800">{{ k.month?.confirmation_pct ?? "—" }}%</div>
          <p class="text-[11px] text-ink-400 mt-0.5">
            {{ t("call centre · confirmed ÷ all orders placed") }}
          </p>
        </div>
        <div>
          <div class="text-[10px] font-bold uppercase tracking-wide text-ink-400">{{ t("Delivery rate") }}</div>
          <div class="figure text-lg font-bold text-ink-800">{{ k.month?.delivery_pct ?? "—" }}%</div>
          <p class="text-[11px] text-ink-400 mt-0.5">
            {{ t("courier · delivered ÷ resolved orders") }}
            <template v-if="k.month?.in_transit">
              · <b class="figure">{{ money(k.month.in_transit) }}</b> {{ t("still in transit") }}
            </template>
          </p>
        </div>
      </div>
    </section>

    <!-- Spend -->
    <section>
      <h2 class="label">{{ t("Ad spend, all platforms") }}</h2>
      <div class="card p-4">
        <div class="flex items-end gap-4 flex-wrap">
          <div>
            <div class="figure text-3xl font-extrabold text-ink-900">
              {{ money(k.spend?.total_try) }}
              <span class="text-[11px] font-bold text-ink-400">TRY</span>
            </div>
            <!-- Converted only when a rate is configured, and the rate is
                 printed next to the number. Ad accounts are TRY and orders are
                 MAD; a converted figure with an invisible rate is a number
                 nobody can check. -->
            <div v-if="k.spend?.total_mad" class="text-xs text-ink-500 mt-0.5">
              ≈ <b class="figure">{{ money(k.spend.total_mad) }}</b> MAD
              <span class="text-ink-300">@ {{ k.spend.try_to_mad_rate }}</span>
            </div>
            <div v-else class="text-[11px] text-amber-700 mt-1">
              {{ t("No TRY→MAD rate configured — spend is not comparable to sales above") }}
            </div>
          </div>

          <div class="ms-auto flex gap-4 flex-wrap">
            <div v-for="s in k.spend?.by_source || []" :key="s.source" class="text-end">
              <div class="text-[10px] font-bold uppercase tracking-wide text-ink-400">
                {{ PLATFORM[s.source] || s.source }}
              </div>
              <div class="figure text-base font-bold text-ink-800">{{ money(s.spend_try) }}</div>
            </div>
          </div>
        </div>

        <div v-if="!k.spend?.sources_reporting" class="mt-3 text-[11.5px] text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
          {{ t("No platform has reported spend yet — the adapters are written but have never run.") }}
        </div>

        <!-- Blended, and labelled blended. Spend ÷ all orders is how the
             business actually runs; it is not attribution and must never be
             read per-campaign. -->
        <div v-if="k.blended?.cost_per_order_try" class="mt-3 pt-3 border-t border-ink-100 flex gap-6 flex-wrap">
          <div>
            <div class="text-[10px] font-bold uppercase tracking-wide text-ink-400">{{ t("Blended cost / order") }}</div>
            <div class="figure text-base font-bold">{{ k.blended.cost_per_order_try }} <span class="text-[10px] text-ink-400">TRY</span></div>
          </div>
          <div v-if="k.blended.cost_per_delivered_try">
            <div class="text-[10px] font-bold uppercase tracking-wide text-ink-400">{{ t("Blended cost / delivered") }}</div>
            <div class="figure text-base font-bold text-brand-600">{{ k.blended.cost_per_delivered_try }} <span class="text-[10px] text-ink-400">TRY</span></div>
          </div>
          <p class="text-[11px] text-ink-400 self-end max-w-xs">{{ t(k.blended.note) }}</p>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed } from "vue";
import Kpi from "../components/Kpi.vue";
import { money } from "../api.js";
import { useI18n } from "../composables/useI18n";

const { t } = useI18n();
const props = defineProps({ overview: Object, daily: { type: Array, default: () => [] } });

const PLATFORM = { meta: "Meta", google_ads: "Google", tiktok: "TikTok" };
const k = computed(() => props.overview || {});
const series = (field) => props.daily.map((d) => d[field]).filter((v) => v != null);
</script>
