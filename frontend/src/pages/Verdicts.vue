<template>
  <div>
    <!-- Ranked by money, not by gap size. Ranking by percentage reports the
         loudest problem; ranking by impact reports the biggest one, and they
         are frequently not the same entity. -->
    <div class="flex items-center gap-2 flex-wrap mb-4">
      <button
        class="px-3 py-1.5 rounded-xl text-xs font-semibold transition-colors border"
        :class="filter === 'all' ? 'bg-ink-900 text-white border-ink-900' : 'bg-white text-ink-500 border-ink-200 hover:border-ink-300'"
        @click="filter = 'all'"
      >
        {{ t("All") }} <span class="font-mono opacity-60">{{ verdicts.length }}</span>
      </button>
      <button
        v-for="k in ORDER"
        :key="k"
        class="px-3 py-1.5 rounded-xl text-xs font-semibold transition-colors border inline-flex items-center gap-1.5"
        :style="
          filter === k
            ? { background: VERDICT[k].bg, color: VERDICT[k].color, borderColor: VERDICT[k].color }
            : {}
        "
        :class="filter === k ? '' : 'bg-white text-ink-500 border-ink-200 hover:border-ink-300'"
        @click="filter = k"
      >
        <span class="w-1.5 h-1.5 rounded-full" :style="{ background: VERDICT[k].color }" />
        {{ t(VERDICT[k].label) }}
        <span class="font-mono opacity-60">{{ count(k) }}</span>
      </button>
    </div>

    <p v-if="filter !== 'all'" class="text-[11.5px] text-ink-400 mb-3 -mt-1">
      {{ t(VERDICT[filter].hint) }}
    </p>

    <div v-if="loading" class="grid gap-3 sm:grid-cols-2">
      <div v-for="i in 4" :key="i" class="skeleton h-56" />
    </div>

    <!-- An empty list is a claim, so it says which claim it is making. -->
    <div v-else-if="!shown.length" class="card p-8 text-center">
      <div class="w-11 h-11 mx-auto rounded-2xl bg-ink-100 text-ink-400 grid place-items-center">
        <NavIcon name="check-circle" :size="20" />
      </div>
      <p class="mt-3 text-sm font-semibold text-ink-700">{{ t("No verdicts here") }}</p>
      <p class="mt-1 text-xs text-ink-400 max-w-sm mx-auto leading-relaxed">
        {{ t("If the sources above are live, this means no gap cleared the threshold — not that nothing was checked.") }}
      </p>
    </div>

    <div v-else class="grid gap-3 sm:grid-cols-2 stagger">
      <VerdictCard v-for="v in shown" :key="v.name" :v="v" @act="(a, b) => $emit('act', a, b)" />
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";
import VerdictCard from "../components/VerdictCard.vue";
import NavIcon from "../components/NavIcon.vue";
import { VERDICT, ORDER } from "../verdicts.js";
import { useI18n } from "../composables/useI18n";

const { t } = useI18n();

const props = defineProps({ verdicts: Array, loading: Boolean });
defineEmits(["act"]);

const filter = ref("all");
const count = (k) => props.verdicts.filter((v) => v.verdict === k).length;
const shown = computed(() =>
  filter.value === "all" ? props.verdicts : props.verdicts.filter((v) => v.verdict === filter.value)
);
</script>
