<template>
  <div class="alert" :class="`alert-${type}`">
    <div class="alert-icon">
      <svg v-if="type === 'success'" viewBox="0 0 24 24" fill="currentColor">
        <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z" />
      </svg>
      <svg v-else-if="type === 'error'" viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z" />
      </svg>
      <svg v-else-if="type === 'warning'" viewBox="0 0 24 24" fill="currentColor">
        <path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z" />
      </svg>
      <svg v-else viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z" />
      </svg>
    </div>
    <div class="alert-content">
      <p class="alert-title">{{ title }}</p>
      <p v-if="message" class="alert-message">{{ message }}</p>
    </div>
    <button v-if="closable" class="alert-close" @click="$emit('close')">
      <svg viewBox="0 0 24 24" fill="currentColor">
        <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12 19 6.41z" />
      </svg>
    </button>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  type?: 'success' | 'error' | 'warning' | 'info'
  title: string
  message?: string
  closable?: boolean
}>()

defineEmits<{
  close: []
}>()
</script>

<style scoped>
.alert {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 16px;
  border-radius: var(--radius-md);
  border-left: 4px solid;
}

.alert-success {
  background-color: #f0f9ff;
  border-color: var(--primary-color);
  color: var(--primary-color);
}

.alert-error {
  background-color: #fff5f5;
  border-color: var(--danger-color);
  color: var(--danger-color);
}

.alert-warning {
  background-color: #fffbf0;
  border-color: #ff9500;
  color: #ff9500;
}

.alert-info {
  background-color: #f0f9ff;
  border-color: var(--primary-color);
  color: var(--primary-color);
}

.alert-icon {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.alert-icon svg {
  width: 100%;
  height: 100%;
}

.alert-content {
  flex: 1;
}

.alert-title {
  font-size: 14px;
  font-weight: 600;
  margin: 0 0 4px 0;
}

.alert-message {
  font-size: 13px;
  margin: 0;
  opacity: 0.8;
}

.alert-close {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  cursor: pointer;
  opacity: 0.6;
  transition: opacity var(--transition-normal);
}

.alert-close:hover {
  opacity: 1;
}

.alert-close svg {
  width: 100%;
  height: 100%;
}
</style>
