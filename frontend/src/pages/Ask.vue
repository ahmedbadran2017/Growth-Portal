<template>
  <div class="max-w-2xl">
    <div class="card p-4">
      <div class="flex items-center gap-2.5">
        <span class="w-9 h-9 rounded-xl bg-brand-50 text-brand-600 grid place-items-center">
          <NavIcon name="sparkles" :size="18" />
        </span>
        <div>
          <div class="text-sm font-bold">{{ t("Ask the analyst") }}</div>
          <!-- Stated on the page, not only in the prompt: the agent has no
               write tool on any ad platform. It proposes; a human executes. -->
          <div class="text-[11px] text-ink-400">{{ t("Reads, investigates and recommends — it does not execute on any platform") }}</div>
        </div>
      </div>

      <textarea
        v-model="q"
        rows="3"
        class="input mt-3 resize-none"
        :disabled="!live"
        :placeholder="t('e.g. why did the delivery rate drop this week?')"
        @keydown.meta.enter="ask"
      />

      <div class="mt-2.5 flex items-center gap-2">
        <button class="btn-primary" :disabled="busy || !live || !q.trim()" @click="ask">
          <NavIcon v-if="!busy" name="send" :size="14" />
          {{ busy ? t("Investigating…") : t("Ask") }}
        </button>
        <span v-if="!live" class="text-[11px] text-ink-400">{{ t("Needs a server connection") }}</span>
      </div>

      <div class="mt-3 flex flex-wrap gap-1.5">
        <button
          v-for="s in SUGGESTED"
          :key="s"
          class="text-[11px] px-2.5 py-1 rounded-lg border border-ink-200 text-ink-500 hover:border-brand-300 hover:text-brand-600 transition-colors"
          @click="q = s"
        >{{ t(s) }}</button>
      </div>
    </div>

    <div v-if="busy" class="card p-4 mt-3"><div class="skeleton h-20" /></div>

    <div v-else-if="answer" class="card p-4 mt-3 fade-up">
      <div class="flex items-center gap-2 text-[11px] text-ink-400">
        <span class="font-mono">{{ answer.name }}</span>
        <span class="font-mono ms-auto">{{ answer.tool_call_count }} {{ t("tool calls") }}</span>
      </div>
      <p class="mt-2.5 text-sm text-ink-800 leading-relaxed whitespace-pre-wrap">{{ answer.finding }}</p>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";
import NavIcon from "../components/NavIcon.vue";
import { api, state } from "../api.js";
import { useI18n } from "../composables/useI18n";

const { t } = useI18n();

const q = ref("");
const busy = ref(false);
const answer = ref(null);
const live = computed(() => state.live !== false);

const SUGGESTED = [
  "Which product is losing the most money right now?",
  "Did any ratio drift off its baseline this week?",
  "What changed before the delivery rate fell?",
];

async function ask() {
  if (!q.value.trim() || !live.value) return;
  busy.value = true;
  try {
    answer.value = await api.ask(q.value);
  } finally {
    busy.value = false;
  }
}
</script>
