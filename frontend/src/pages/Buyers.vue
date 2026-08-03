<template>
  <div class="space-y-4">
    <div v-if="perf.unmapped_accounts" class="card p-3 border-amber-200 bg-amber-50/60 text-[11.5px] text-amber-900">
      {{ t("{0} account(s) are not mapped to a buyer — their spend shows as Unassigned.", perf.unmapped_accounts) }}
      <span class="font-mono text-[10.5px]">site_config.json → media_buyer_accounts</span>
    </div>

    <section>
      <h2 class="label">{{ t("Performance") }}</h2>
      <div v-if="!perf.rows?.length" class="card p-8 text-center text-sm text-ink-400">
        {{ t("No platform spend in the window yet") }}
      </div>
      <div v-else class="grid gap-2.5 sm:grid-cols-2 stagger">
        <div v-for="r in perf.rows" :key="r.buyer + r.platform" class="card p-3.5">
          <div class="flex items-center gap-2">
            <span class="w-7 h-7 rounded-lg bg-ink-100 text-ink-500 grid place-items-center text-[11px] font-bold">
              {{ initials(r.buyer) }}
            </span>
            <div class="min-w-0">
              <div class="text-xs font-bold text-ink-800 truncate">{{ r.buyer }}</div>
              <div class="text-[10px] text-ink-400">{{ PLATFORM[r.platform] || r.platform }} · {{ r.campaigns }} {{ t("campaigns") }}</div>
            </div>
            <div class="ms-auto text-end">
              <div class="figure text-lg font-extrabold" :style="{ color: r.roas >= 5 ? '#0d9488' : r.roas >= 2 ? '#a16207' : '#be123c' }">
                {{ r.roas ?? "—" }}x
              </div>
              <div class="text-[10px] text-ink-400">{{ t("platform ROAS") }}</div>
            </div>
          </div>
          <div class="mt-2.5 grid grid-cols-3 gap-2 text-[11px]">
            <div><div class="text-ink-400">{{ t("Spend") }}</div><div class="figure font-bold">{{ money(r.spend) }} {{ r.currency }}</div></div>
            <div><div class="text-ink-400">{{ t("CPA") }}</div><div class="figure font-bold">{{ r.cpa ?? "—" }}</div></div>
            <div><div class="text-ink-400">{{ t("CPM") }}</div><div class="figure font-bold">{{ r.cpm ?? "—" }}</div></div>
          </div>
        </div>
      </div>
      <p class="text-[11px] text-ink-400 mt-2">{{ t(perf.note || "") }}</p>
    </section>

    <section>
      <h2 class="label">{{ t("Activity") }}</h2>
      <div v-if="!act.summary?.length" class="card p-8 text-center text-sm text-ink-400">
        {{ t("No change log entries yet — platform audit logs arrive with the first sync") }}
      </div>
      <div v-else class="card divide-y divide-ink-100">
        <div v-for="a in act.summary" :key="a.actor" class="p-3.5">
          <div class="flex items-center gap-2 flex-wrap">
            <span class="text-xs font-bold text-ink-800">{{ a.actor }}</span>
            <span class="text-[10.5px] text-ink-400">{{ a.active_days }} {{ t("active days") }} · {{ t("last") }} {{ a.last_change }}</span>
            <div class="ms-auto flex items-baseline gap-3">
              <!-- Human vs automation, separated. Two buyers with 40 changes
                   each are not comparable if 35 of one's were platform
                   recommendations applied on their behalf. -->
              <div class="text-end">
                <div class="figure text-base font-bold text-ink-800">{{ a.human_changes }}</div>
                <div class="text-[9.5px] text-ink-400 uppercase tracking-wide">{{ t("by them") }}</div>
              </div>
              <div v-if="a.automation_changes" class="text-end">
                <div class="figure text-base font-bold text-ink-400">{{ a.automation_changes }}</div>
                <div class="text-[9.5px] text-ink-300 uppercase tracking-wide">{{ t("automation") }}</div>
              </div>
            </div>
          </div>
          <div class="mt-1.5 flex flex-wrap gap-1.5">
            <span v-for="[f, n] in a.top_fields" :key="f"
                  class="text-[10.5px] px-1.5 py-0.5 rounded bg-ink-50 text-ink-500 border border-ink-200/60">
              {{ f }} <b class="figure">{{ n }}</b>
            </span>
          </div>
        </div>
      </div>

      <div v-if="act.coverage?.length" class="mt-2 text-[11px] text-ink-400">
        {{ t("Change-log coverage:") }}
        <span v-for="c in act.coverage" :key="c.source" class="me-3">
          {{ c.source }} <b class="figure">{{ c.changes }}</b>
          <template v-if="c.surface_unknown">
            ({{ c.surface_unknown }} {{ t("without a surface") }})
          </template>
        </span>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { money } from "../api.js";
import { useI18n } from "../composables/useI18n";

const { t } = useI18n();
const props = defineProps({ buyers: Object, buyerActivity: Object });

const PLATFORM = { meta: "Meta", google_ads: "Google", tiktok: "TikTok" };
const perf = computed(() => props.buyers || {});
const act = computed(() => props.buyerActivity || {});

const initials = (s) =>
  String(s || "?").replace(/@.*/, "").split(/[.\s_-]/).map((x) => x[0]).slice(0, 2).join("").toUpperCase();
</script>
