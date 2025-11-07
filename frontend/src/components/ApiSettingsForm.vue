<template>
  <section class="card">
    <header class="card__header">
      <h2>API Settings</h2>
      <p>Configure how the console connects to the backend services.</p>
    </header>

    <form class="stack" @submit.prevent="emitSubmit">
      <label class="field">
        <span class="field__label">Backend base URL</span>
        <input
          v-model="localSettings.baseUrl"
          type="url"
          name="baseUrl"
          placeholder="https://your-backend.example.com"
          required
        />
      </label>

      <label class="field">
        <span class="field__label">Optional API key</span>
        <input
          v-model="localSettings.apiKey"
          type="text"
          name="apiKey"
          autocomplete="off"
          placeholder="If your backend expects an Authorization header"
        />
      </label>

      <div class="actions">
        <button class="btn" type="submit">Save</button>
        <button class="btn btn--ghost" type="button" @click="reset">Reset</button>
      </div>
    </form>
  </section>
</template>

<script setup lang="ts">
import { reactive, watch } from 'vue';
import type { ApiSettings } from '@/types/settings';

const props = defineProps<{
  modelValue: ApiSettings;
}>();

const emit = defineEmits<{
  'update:modelValue': [value: ApiSettings];
  submit: [value: ApiSettings];
}>();

const localSettings = reactive<ApiSettings>({ ...props.modelValue });

watch(
  () => props.modelValue,
  (value) => {
    Object.assign(localSettings, value);
  },
  { deep: true }
);

function emitSubmit() {
  emit('update:modelValue', { ...localSettings });
  emit('submit', { ...localSettings });
}

function reset() {
  Object.assign(localSettings, props.modelValue);
}
</script>
