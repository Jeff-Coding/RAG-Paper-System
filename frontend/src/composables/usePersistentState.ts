import { ref, watch } from 'vue';

function readFromStorage<T>(key: string, fallback: T): T {
  if (typeof window === 'undefined') {
    return fallback;
  }

  try {
    const raw = window.localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch (error) {
    console.warn(`Failed to read persistent state for ${key}:`, error);
    return fallback;
  }
}

export function usePersistentState<T>(key: string, defaultValue: T) {
  const state = ref<T>(readFromStorage<T>(key, defaultValue));

  if (typeof window !== 'undefined') {
    watch(
      state,
      (value) => {
        try {
          window.localStorage.setItem(key, JSON.stringify(value));
        } catch (error) {
          console.warn(`Failed to persist state for ${key}:`, error);
        }
      },
      { deep: true }
    );
  }

  return state;
}
