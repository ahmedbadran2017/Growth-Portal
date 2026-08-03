<template>
  <div class="space-y-4">
    <div class="card p-4">
      <div class="flex items-center gap-2.5">
        <span
          class="w-9 h-9 rounded-xl grid place-items-center"
          :class="wired === total ? 'bg-teal-50 text-teal-600' : 'bg-amber-50 text-amber-600'"
        >
          <NavIcon name="link" :size="18" />
        </span>
        <div class="min-w-0">
          <div class="text-sm font-bold">
            {{ wired }} of {{ total }} sources wired
          </div>
          <div class="text-[11px] text-ink-400">
            Every unwired source is a question the portal cannot answer yet
          </div>
        </div>
        <div class="ms-auto text-end">
          <div class="text-2xl font-extrabold tabular-nums text-ink-800">{{ wired }}/{{ total }}</div>
        </div>
      </div>
    </div>

    <!-- Three states, not one light. "Implemented but unauthorised" and
         "authorised but not implemented" need different people to fix them,
         and a single status colour hides which one you have. -->
    <div class="grid gap-2.5 sm:grid-cols-2">
      <div
        v-for="c in connections"
        :key="c.source"
        class="card p-4"
        :class="c.healthy ? '' : c.implemented ? 'border-rose-200 bg-rose-50/40' : ''"
      >
        <div class="flex items-start justify-between gap-2">
          <div class="min-w-0">
            <div class="text-sm font-bold text-ink-900">{{ c.label }}</div>
            <div class="text-[11px] text-ink-400 font-mono">{{ c.source }}</div>
          </div>
          <Pill :label="st(c).label" :color="st(c).color" :bg="st(c).bg" dot />
        </div>

        <p class="mt-2 text-xs text-ink-500 leading-relaxed">{{ c.covers }}</p>

        <div class="mt-3 grid grid-cols-2 gap-x-3 gap-y-2">
          <div>
            <div class="text-[10px] font-semibold uppercase tracking-wide text-ink-400">Adapter</div>
            <div class="text-[11.5px]" :class="c.implemented ? 'text-teal-700' : 'text-ink-400'">
              {{ c.implemented ? "written" : "not written" }}
            </div>
          </div>
          <div>
            <div class="text-[10px] font-semibold uppercase tracking-wide text-ink-400">Credential</div>
            <div class="text-[11.5px]" :class="c.configured ? 'text-teal-700' : 'text-rose-600'">
              {{ c.credential_key ? (c.configured ? "present" : "missing") : "not needed" }}
            </div>
          </div>
          <div>
            <div class="text-[10px] font-semibold uppercase tracking-wide text-ink-400">Timezone</div>
            <!-- Its OWN reporting timezone. Meta's dataset stats are Pacific
                 while the account itself is Casablanca, and reading one as the
                 other shifts a whole day. -->
            <div class="text-[11.5px] font-mono text-ink-700">{{ c.timezone }}</div>
          </div>
          <div>
            <div class="text-[10px] font-semibold uppercase tracking-wide text-ink-400">Maturity</div>
            <div class="text-[11.5px] font-mono text-ink-700">{{ c.maturity_hours }}h</div>
          </div>
        </div>

        <div v-if="c.credential_key" class="mt-2.5 text-[10.5px] text-ink-400 font-mono">
          site_config.json → {{ c.credential_key }}
        </div>

        <div v-if="c.last_error" class="mt-2.5 rounded-lg bg-rose-50 border border-rose-200 px-2.5 py-1.5">
          <div class="text-[10px] font-bold uppercase tracking-wide text-rose-500">Last error</div>
          <div class="text-[11px] text-rose-700 font-mono break-all line-clamp-3">{{ c.last_error }}</div>
        </div>

        <div class="mt-3 pt-3 border-t border-ink-100 flex items-center gap-2">
          <span class="text-[11px] text-ink-400">
            <template v-if="c.last_ok">
              last pull <b class="font-mono text-ink-700">{{ c.last_ok }}</b> ·
              <b class="font-mono text-ink-700">{{ c.last_rows }}</b> rows
            </template>
            <template v-else>never pulled</template>
          </span>
          <button
            class="btn-outline !px-2.5 !py-1 !text-[11px] ms-auto"
            :disabled="!live || !c.implemented || testing === c.source"
            @click="test(c)"
          >
            {{ testing === c.source ? "testing…" : "Test" }}
          </button>
        </div>

        <p v-if="result[c.source]" class="mt-2 text-[11px] font-mono" :class="result[c.source].ok ? 'text-teal-700' : 'text-rose-600'">
          {{ result[c.source].ok ? "ok" : "failed" }} — {{ shortDetail(result[c.source].detail) }}
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";
import NavIcon from "../components/NavIcon.vue";
import Pill from "../components/Pill.vue";
import { api, state } from "../api.js";

const props = defineProps({ connections: { type: Array, default: () => [] } });

const testing = ref("");
const result = ref({});
const live = computed(() => state.live !== false);
const total = computed(() => props.connections.length);
const wired = computed(() => props.connections.filter((c) => c.implemented && c.healthy).length);

function st(c) {
  if (c.healthy) return { label: "Live", color: "#0d9488", bg: "#ccfbf1" };
  if (c.implemented) return { label: "Down", color: "#be123c", bg: "#ffe4e6" };
  if (!c.configured) return { label: "No credential", color: "#be123c", bg: "#ffe4e6" };
  return { label: "Not built", color: "#57534e", bg: "#f5f5f4" };
}

function shortDetail(d) {
  const s = typeof d === "string" ? d : JSON.stringify(d);
  return s.length > 160 ? s.slice(0, 160) + "…" : s;
}

async function test(c) {
  testing.value = c.source;
  try {
    result.value = { ...result.value, [c.source]: await api.testConnection(c.source) };
  } catch (e) {
    result.value = { ...result.value, [c.source]: { ok: false, detail: String(e) } };
  } finally {
    testing.value = "";
  }
}
</script>
