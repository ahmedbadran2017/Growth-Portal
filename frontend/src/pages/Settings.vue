<template>
  <div class="max-w-3xl space-y-4">
    <div v-if="!live" class="card p-3 text-[11.5px] text-ink-500">
      Read-only without a server connection — the values below are defaults.
    </div>

    <section class="card p-4">
      <h2 class="label">Alerts</h2>
      <div class="grid gap-3 sm:grid-cols-2">
        <div>
          <label class="label">Email</label>
          <input v-model="s.alert_email" class="input" :disabled="!live" placeholder="name@justyol.com" />
        </div>
        <div>
          <label class="label">WhatsApp number</label>
          <input v-model="s.whatsapp_to" class="input" :disabled="!live" placeholder="+90…" />
        </div>
        <div>
          <label class="label">WhatsApp threshold</label>
          <select v-model="s.whatsapp_min_severity" class="input" :disabled="!live">
            <option v-for="o in SEVERITIES" :key="o" :value="o">{{ o }}</option>
          </select>
          <!-- The threshold is the whole design of the channel: a phone that
               buzzes for routine findings stops being read within a week. -->
          <p class="mt-1 text-[11px] text-ink-400">
            Email always sends. WhatsApp only at this severity and above.
          </p>
        </div>
        <div>
          <label class="label">Webhook</label>
          <div class="input flex items-center gap-2" :class="s.whatsapp_webhook ? 'text-teal-700' : 'text-ink-400'">
            <span class="w-1.5 h-1.5 rounded-full" :class="s.whatsapp_webhook ? 'bg-teal-500' : 'bg-ink-300'" />
            {{ s.whatsapp_webhook ? "configured" : "not configured" }}
          </div>
          <p class="mt-1 text-[11px] text-ink-400 font-mono">
            site_config.json → growth_alert_whatsapp_webhook
          </p>
        </div>
      </div>
    </section>

    <section class="card p-4">
      <h2 class="label">Judging</h2>
      <div class="grid gap-3 sm:grid-cols-2">
        <div>
          <label class="label">Window (days)</label>
          <input v-model.number="s.window_days" type="number" min="14" class="input" :disabled="!live" />
          <p class="mt-1 text-[11px] text-ink-400">
            Shortest span where this catalogue's delivery rates stop swinging on single-day noise.
          </p>
        </div>
        <div>
          <label class="label">Daily run hour (site time)</label>
          <input v-model.number="s.judge_hour" type="number" min="0" max="23" class="input" :disabled="!live" />
          <!-- The guard refuses a window whose last day is still maturing, so
               too early an hour produces no verdicts rather than wrong ones. -->
          <p class="mt-1 text-[11px] text-ink-400">
            Must be late enough that yesterday is mature — ERPNext needs 6h, PMAX up to 72h.
          </p>
        </div>
      </div>
    </section>

    <section class="card p-4">
      <h2 class="label">Thresholds</h2>
      <p class="text-[11.5px] text-ink-500 mb-3">
        Each default was set from a specific wrong answer, not chosen as a round number.
      </p>
      <div v-for="r in rules" :key="r.entity_type + r.metric" class="rounded-xl border border-ink-200 p-3 mb-2">
        <div class="flex items-center gap-2">
          <span class="text-xs font-bold">{{ r.entity_type }}</span>
          <span class="text-[11px] font-mono text-ink-400">{{ r.metric }}</span>
          <Pill :label="r.source" color="#57534e" bg="#f5f5f4" class="ms-auto" />
        </div>
        <div class="mt-3 grid gap-3 sm:grid-cols-3">
          <div v-for="f in FIELDS" :key="f.k">
            <label class="label">{{ f.label }}</label>
            <input v-model.number="r[f.k]" type="number" class="input" :disabled="!live" />
            <p class="mt-1 text-[10.5px] text-ink-400 leading-snug">{{ f.hint }}</p>
          </div>
        </div>
        <div class="mt-2 flex justify-end">
          <button class="btn-outline !px-3 !py-1 !text-[11px]" :disabled="!live" @click="saveRule(r)">
            Save rule
          </button>
        </div>
      </div>
    </section>

    <section class="card p-4">
      <h2 class="label">Analyst</h2>
      <div class="grid gap-3 sm:grid-cols-2">
        <div>
          <label class="label">Model</label>
          <input v-model="s.agent_model" class="input" :disabled="!live" />
        </div>
        <div>
          <label class="label">Reasoning effort</label>
          <select v-model="s.agent_effort" class="input" :disabled="!live">
            <option v-for="o in EFFORTS" :key="o" :value="o">{{ o }}</option>
          </select>
        </div>
        <div>
          <label class="label">API key</label>
          <div class="input flex items-center gap-2" :class="s.api_key_configured ? 'text-teal-700' : 'text-rose-600'">
            <span class="w-1.5 h-1.5 rounded-full" :class="s.api_key_configured ? 'bg-teal-500' : 'bg-rose-400'" />
            {{ s.api_key_configured ? "configured" : "missing" }}
          </div>
          <p class="mt-1 text-[11px] text-ink-400 font-mono">site_config.json → anthropic_api_key</p>
        </div>
        <div>
          <label class="label">Enabled</label>
          <button
            class="input flex items-center gap-2 text-start"
            :disabled="!live"
            @click="s.agent_enabled = !s.agent_enabled"
          >
            <span class="w-1.5 h-1.5 rounded-full" :class="s.agent_enabled ? 'bg-teal-500' : 'bg-ink-300'" />
            {{ s.agent_enabled ? "on" : "off" }}
          </button>
        </div>
      </div>

      <!-- Stated as a property of the build, not as a switch someone forgot to
           turn on. There is no write tool on any ad platform to enable. -->
      <div class="mt-3 rounded-xl bg-ink-50 border border-ink-200 px-3 py-2.5">
        <div class="flex items-center gap-2">
          <NavIcon name="ban" :size="13" class="text-ink-400" />
          <span class="text-xs font-bold text-ink-700">Execution is off</span>
        </div>
        <p class="mt-1 text-[11.5px] text-ink-500 leading-relaxed">
          The analyst has no write tool on any ad platform — it proposes, a human executes.
          This is not a setting; it is what the build contains.
        </p>
      </div>
    </section>

    <div class="flex items-center gap-2">
      <button class="btn-primary" :disabled="!live || saving" @click="save">
        {{ saving ? "Saving…" : "Save settings" }}
      </button>
      <span v-if="saved" class="text-[11.5px] text-teal-700">Saved</span>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from "vue";
import NavIcon from "../components/NavIcon.vue";
import Pill from "../components/Pill.vue";
import { api, state } from "../api.js";

const props = defineProps({ settings: Object, rules: { type: Array, default: () => [] } });

const SEVERITIES = ["Critical", "High", "Medium", "Low"];
const EFFORTS = ["low", "medium", "high", "xhigh"];

const FIELDS = [
  { k: "min_sample", label: "Min sample", hint: "Below this the engine issues Watch, not a verdict." },
  { k: "min_weight", label: "Min weight (MAD)", hint: "Order count alone once promoted a 54 MAD packaging line to Grow." },
  { k: "min_days", label: "Min window (days)", hint: "One anomalous day is not a pattern." },
  { k: "gap_act", label: "Act gap (pp)", hint: "Acted on regardless of money." },
  { k: "gap_material", label: "Material gap (pp)", hint: "Acts only if it also clears the impact floor." },
  { k: "impact_floor", label: "Impact floor (MAD/mo)", hint: "Without this a 6.6pp gap on high volume stays invisible." },
  { k: "kill_at", label: "Kill below", hint: "Absolute floor. Empty means never issue Kill." },
];

const s = reactive({ ...(props.settings || {}) });
watch(() => props.settings, (v) => Object.assign(s, v || {}));

const rules = ref(props.rules.map((r) => ({ ...r })));
watch(() => props.rules, (v) => (rules.value = (v || []).map((r) => ({ ...r }))));

const live = computed(() => state.live !== false);
const saving = ref(false);
const saved = ref(false);

async function save() {
  saving.value = true;
  saved.value = false;
  try {
    Object.assign(s, await api.saveSettings({ ...s }));
    saved.value = true;
  } finally {
    saving.value = false;
  }
}

async function saveRule(r) {
  await api.saveRule({ ...r });
}
</script>
