<template>
  <div class="space-y-4">
    <div class="flex items-center gap-2">
      <button
        v-for="tab in TABS" :key="tab.k"
        class="px-3 py-1.5 rounded-xl text-xs font-semibold border transition-colors"
        :class="view === tab.k ? 'bg-ink-900 text-white border-ink-900' : 'bg-white text-ink-500 border-ink-200 hover:border-ink-300'"
        @click="view = tab.k; focus = null"
      >{{ t(tab.label) }}</button>

      <span v-if="focus" class="text-xs text-ink-500 ms-2">
        {{ t("filtered to") }} <b>{{ focus }}</b>
        <button class="ms-1 text-brand-600 font-bold" @click="focus = null">×</button>
      </span>
      <span class="text-[11px] text-ink-400 ms-auto">{{ t("last {0} days", data.window_days || 30) }}</span>
    </div>

    <div v-if="!rows.length" class="card p-8 text-center text-sm text-ink-400">
      {{ t("No rows in this window") }}
    </div>

    <div v-else class="card overflow-x-auto">
      <table class="w-full text-[12.5px]">
        <thead>
          <tr class="text-[10px] font-bold uppercase tracking-wide text-ink-400 border-b border-ink-200">
            <th class="text-start px-3 py-2">{{ t(view === "suppliers" ? "Supplier" : "Product") }}</th>
            <th class="text-end px-3 py-2">{{ t("Share") }}</th>
            <th class="text-end px-3 py-2">{{ t("Revenue") }}</th>
            <th class="text-end px-3 py-2">{{ t("Orders") }}</th>
            <th class="text-end px-3 py-2 hidden sm:table-cell">{{ t("SKUs") }}</th>
            <th class="text-end px-3 py-2">{{ t("Confirm") }}</th>
            <th class="text-end px-3 py-2 hidden sm:table-cell">{{ t("Delivery") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="r in rows" :key="r.supplier || r.item_code"
            class="border-b border-ink-100 last:border-0 hover:bg-ink-50/60 transition-colors"
            :class="view === 'suppliers' ? 'cursor-pointer' : ''"
            @click="view === 'suppliers' && drill(r.supplier)"
          >
            <td class="px-3 py-2 max-w-[240px]">
              <div dir="auto" class="font-semibold text-ink-800 truncate" :title="r.supplier || r.label">
                {{ r.supplier || r.label }}
              </div>
              <div v-if="r.supplier && view === 'products'" class="text-[10.5px] text-ink-400">{{ r.supplier }}</div>
            </td>

            <!-- Share is a bar, not just a number: 41% vs 19% is a structural
                 fact about the business and it should be visible without
                 reading two figures and subtracting. -->
            <td class="px-3 py-2 w-[110px]">
              <div class="flex items-center gap-1.5 justify-end">
                <div class="h-1.5 w-12 rounded-full bg-ink-100 overflow-hidden">
                  <div class="h-full rounded-full bg-brand-500" :style="{ width: Math.min(100, r.share_pct) + '%' }" />
                </div>
                <span class="figure text-[11px] font-bold text-ink-700 w-9 text-end">{{ r.share_pct }}%</span>
              </div>
            </td>

            <td class="px-3 py-2 text-end figure font-bold">{{ money(r.revenue_mad) }}</td>
            <td class="px-3 py-2 text-end figure">{{ money(r.orders) }}</td>
            <td class="px-3 py-2 text-end figure hidden sm:table-cell text-ink-500">{{ r.skus ?? "—" }}</td>
            <td class="px-3 py-2 text-end">
              <span class="figure font-bold" :style="{ color: rateColor(r.confirmation_pct, 81) }">
                {{ r.confirmation_pct ?? "—" }}%
              </span>
            </td>
            <td class="px-3 py-2 text-end hidden sm:table-cell">
              <span class="figure" :style="{ color: rateColor(r.delivery_pct, 81) }">
                {{ r.delivery_pct != null ? r.delivery_pct + "%" : "—" }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <p class="text-[11px] text-ink-400">
      {{ t("Share is of the rows listed. Confirmation is the call centre; delivery is the courier — different systems, different denominators.") }}
    </p>
  </div>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { api, money } from "../api.js";
import { useI18n } from "../composables/useI18n";

const { t } = useI18n();
const props = defineProps({ suppliers: Object, products: Object });

const TABS = [{ k: "suppliers", label: "Suppliers" }, { k: "products", label: "Products" }];
const view = ref("suppliers");
const focus = ref(null);
const drilled = ref(null);

const data = computed(() => (view.value === "suppliers" ? props.suppliers : props.products) || {});
const rows = computed(() =>
  (focus.value && drilled.value ? drilled.value.rows : data.value.rows) || []
);

async function drill(supplier) {
  focus.value = supplier;
  view.value = "products";
  drilled.value = await api.products({ supplier });
}
watch(view, (v) => { if (v === "suppliers") { focus.value = null; drilled.value = null; } });

// Green above the book's own rate, red well below it. The reference is the
// business's actual level, not a target someone typed.
function rateColor(v, base) {
  if (v == null) return "#a8a29e";
  if (v >= base) return "#0d9488";
  if (v >= base - 10) return "#a16207";
  return "#be123c";
}
</script>
