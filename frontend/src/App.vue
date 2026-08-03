<template>
  <div class="min-h-screen text-ink-900">
    <div class="brand-hairline fixed top-0 inset-x-0 z-[60]" />
    <div class="min-h-screen flex">
      <!-- Sidebar -->
      <aside class="hidden md:flex flex-col w-60 shrink-0 bg-white border-e border-ink-200 h-screen sticky top-0">
        <div class="px-5 py-5 border-b border-ink-100">
          <img :src="logoSrc" alt="Justyol" class="h-5 w-auto" />
          <div class="text-[11px] font-bold text-brand-600 mt-1.5 tracking-widest uppercase">
            Growth Portal
          </div>
        </div>

        <!-- Measurement health sits in the navigation, not on one page. A clean
             verdict list over a dead feed is worse than no portal at all, so
             the state of the feeds is visible from everywhere. -->
        <div class="px-3 pt-3">
          <router-link
            to="/integrity"
            class="flex items-center gap-2.5 px-3 py-2.5 rounded-xl border transition-colors"
            :class="
              healthy
                ? 'border-ink-200 bg-ink-50/60 hover:bg-ink-50'
                : 'border-rose-200 bg-rose-50 hover:bg-rose-100/70'
            "
          >
            <span
              class="w-2 h-2 rounded-full shrink-0"
              :class="healthy ? 'bg-teal-500' : 'bg-rose-500 animate-pulse'"
            />
            <div class="min-w-0">
              <div class="text-[11px] font-bold" :class="healthy ? 'text-ink-600' : 'text-rose-700'">
                {{ t("Measurement Integrity") }}
              </div>
              <div class="text-[10px] truncate" :class="healthy ? 'text-ink-400' : 'text-rose-500'">
                {{ healthy ? t("All sources live") : t("{0} problems", problems) }}
              </div>
            </div>
          </router-link>
        </div>

        <nav class="flex-1 px-3 py-4 space-y-1 overflow-y-auto scroll-thin">
          <template v-for="(group, gi) in groups" :key="gi">
            <div v-if="gi" class="pt-3 pb-1 px-3 text-[10px] font-bold uppercase tracking-wide text-ink-300">
              {{ t(group.title) }}
            </div>
            <router-link
              v-for="item in group.items"
              :key="item.to"
              :to="item.to"
              class="group relative flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150"
              :class="
                isActive(item.to) ? 'bg-brand-50 text-brand-700' : 'text-ink-500 hover:bg-ink-50 hover:text-ink-800'
              "
            >
              <span
                v-if="isActive(item.to)"
                class="absolute start-0 top-1/2 -translate-y-1/2 w-1 h-5 rounded-e-full bg-brand-500"
              />
              <span
                class="w-7 h-7 grid place-items-center rounded-lg shrink-0"
                :class="isActive(item.to) ? 'bg-brand-100 text-brand-700' : 'bg-ink-100 text-ink-500'"
              ><NavIcon :name="item.icon" :size="15" /></span>
              {{ t(item.label) }}
              <span
                v-if="item.count"
                class="ms-auto text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-ink-100 text-ink-500 font-mono"
              >{{ item.count }}</span>
              <span
                v-else-if="item.warn"
                class="ms-auto text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-rose-100 text-rose-600 font-mono"
              >{{ item.warn }}</span>
            </router-link>
          </template>
        </nav>

        <div class="px-4 py-4 border-t border-ink-100">
          <div class="text-[10px] font-semibold uppercase tracking-wide text-ink-400">
            {{ t("Open impact") }}
          </div>
          <div class="text-xl font-extrabold text-brand-600 tabular-nums mt-0.5">
            {{ money(totalImpact) }}
            <span class="text-[10px] font-semibold text-ink-400">{{ t("MAD/mo") }}</span>
          </div>
        </div>
      </aside>

      <!-- Main -->
      <div class="flex-1 min-w-0 flex flex-col">
        <header
          class="sticky top-0 z-30 bg-white/80 backdrop-blur border-b border-ink-200 px-4 sm:px-6 py-3 flex items-center justify-between gap-3"
        >
          <div class="flex items-center gap-2 md:hidden min-w-0 flex-1">
            <img :src="logoSrc" alt="Justyol" class="h-4 w-auto shrink-0" />
            <span class="text-[10px] font-bold text-brand-600 tracking-wide uppercase mt-0.5 truncate">
              {{ t(currentTitle) }}
            </span>
          </div>
          <div class="hidden md:block text-sm font-semibold text-ink-700 min-w-0 truncate">
            {{ t(currentTitle) }}
          </div>

          <div class="flex items-center gap-1.5 shrink-0">
            <div class="hidden sm:inline-flex rounded-lg border border-ink-200 overflow-hidden">
              <button
                v-for="l in LOCALES"
                :key="l.code"
                :title="l.name"
                :aria-pressed="String(locale === l.code)"
                class="px-2 py-1 text-[11px] font-bold transition-colors"
                :class="locale === l.code ? 'bg-brand-500 text-white' : 'bg-white text-ink-500 hover:bg-ink-50'"
                @click="setLocale(l.code)"
              >
                {{ l.label }}
              </button>
            </div>
            <span
              v-if="!healthy"
              class="md:hidden inline-flex items-center gap-1 text-[10px] font-bold text-rose-600 bg-rose-50 px-2 py-1 rounded-lg"
            >
              <NavIcon name="warning" :size="11" /> {{ problems }}
            </span>
            <button class="btn-outline !px-2.5" :disabled="loading" @click="load">
              <NavIcon name="refresh" :size="14" :class="loading ? 'animate-spin' : ''" />
              <span class="hidden sm:inline">{{ t("Refresh") }}</span>
            </button>
            <router-link to="/ask" class="btn-primary">
              <NavIcon name="sparkles" :size="14" />
              <span class="hidden sm:inline">{{ t("Ask") }}</span>
            </router-link>
          </div>
        </header>

        <!-- Three different causes, three different messages. A 500 reported as
             "not connected" is the same class of lie the portal exists to
             prevent. -->
        <div
          v-if="state.live === false"
          class="mx-4 sm:mx-6 mt-4 rounded-xl border px-4 py-2.5 text-[12px] flex items-start gap-2"
          :class="
            state.reason === 'offline'
              ? 'border-amber-300 bg-amber-50 text-amber-900'
              : 'border-rose-300 bg-rose-50 text-rose-900'
          "
        >
          <NavIcon name="warning" :size="14" class="mt-0.5 shrink-0" />
          <span>{{ bannerText }}</span>
        </div>

        <main class="flex-1 p-4 sm:p-6 pb-24 md:pb-6">
          <router-view v-slot="{ Component }">
            <transition name="page" mode="out-in">
              <component
                :is="Component"
                :key="route.path"
                :verdicts="verdicts"
                :findings="findings"
                :integrity="integrity"
                :connections="connections"
                :settings="settings"
                :rules="rules"
                :loading="loading"
                @act="act"
              />
            </transition>
          </router-view>
        </main>

        <nav
          class="md:hidden fixed bottom-0 inset-x-0 z-40 bg-white/95 backdrop-blur border-t border-ink-200 flex overflow-x-auto scroll-thin"
          style="padding-bottom: env(safe-area-inset-bottom)"
        >
          <router-link
            v-for="item in flatNav"
            :key="item.to"
            :to="item.to"
            class="flex-1 shrink-0 min-w-[64px] flex flex-col items-center gap-0.5 pt-2 pb-1.5 min-h-[56px] transition-colors"
            :class="isActive(item.to) ? 'text-brand-600' : 'text-ink-400'"
            :aria-current="isActive(item.to) ? 'page' : undefined"
          >
            <span class="px-3 py-1 rounded-full transition-colors" :class="isActive(item.to) ? 'bg-brand-100/80' : ''">
              <NavIcon :name="item.icon" :size="19" />
            </span>
            <span class="text-[10px] font-semibold truncate px-1 max-w-full">
              {{ t(item.short || item.label) }}
            </span>
          </router-link>
        </nav>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import NavIcon from "./components/NavIcon.vue";
import { api, state, money } from "./api.js";
import { useI18n } from "./composables/useI18n";

const route = useRoute();
const { t, locale, setLocale, LOCALES } = useI18n();

const integrity = ref(null);
const verdicts = ref([]);
const findings = ref([]);
const connections = ref([]);
const settings = ref({});
const rules = ref([]);
const loading = ref(true);

// The dev server mounts public/ under the same base as the built assets, so
// one expression covers both.
const logoSrc = import.meta.env.BASE_URL + "justyol-logo.png";

const problems = computed(
  () => (integrity.value?.syncs || []).filter((s) => !s.ok).length + (integrity.value?.anomalies || []).length
);
const healthy = computed(() => problems.value === 0);
const totalImpact = computed(() => verdicts.value.reduce((s, v) => s + (v.impact_mad || 0), 0));

const unwired = computed(() => connections.value.filter((c) => !c.healthy).length);

const groups = computed(() => [
  {
    title: "",
    items: [
      { to: "/verdicts", label: "Verdicts", icon: "gauge", count: verdicts.value.length },
      { to: "/findings", label: "Findings", short: "Findings", icon: "flag", count: findings.value.length },
      { to: "/ask", label: "Ask the analyst", short: "Ask", icon: "sparkles" },
    ],
  },
  {
    title: "System",
    items: [
      { to: "/integrity", label: "Measurement Integrity", short: "Integrity", icon: "check-circle" },
      { to: "/connections", label: "Connections", icon: "link", warn: unwired.value },
      { to: "/settings", label: "Settings", icon: "settings" },
    ],
  },
]);
const flatNav = computed(() => groups.value.flatMap((g) => g.items));

function isActive(to) {
  return route.path.startsWith(to);
}
const currentTitle = computed(() => flatNav.value.find((n) => isActive(n.to))?.label || "Growth Portal");

const bannerText = computed(() => {
  if (state.reason === "forbidden")
    return t("Your account does not have access to the Growth Portal — ask an admin for the Growth Portal Analyst role.");
  if (state.reason === "error")
    return t("The server answered with an error ({0}). What you see below is sample data, not your numbers.", state.status);
  return t(
    "No connection to the server — this is sample data from a real engine run (6 Jul – 2 Aug 2026). Action buttons are disabled."
  );
});

async function load() {
  loading.value = true;
  try {
    [integrity.value, verdicts.value, findings.value, connections.value, settings.value, rules.value] =
      await Promise.all([
        api.integrity(),
        api.verdicts(),
        api.findings(),
        api.connections(),
        api.settings(),
        api.rules(),
      ]);
  } finally {
    loading.value = false;
  }
}

async function act(v, status) {
  if (state.live === false) return;
  await api.act(v.name, status);
  verdicts.value = verdicts.value.filter((x) => x.name !== v.name);
}

onMounted(load);
</script>
