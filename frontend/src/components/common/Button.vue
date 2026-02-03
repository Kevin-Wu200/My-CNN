<template>
  <button
    class="btn"
    :class="[`btn-${variant}`, `btn-${size}`, { 'btn-disabled': disabled }]"
    :disabled="disabled"
  >
    <slot />
  </button>
</template>

<script setup lang="ts">
defineProps<{
  variant?: 'primary' | 'secondary' | 'danger'
  size?: 'small' | 'medium' | 'large'
  disabled?: boolean
}>()
</script>

<style scoped>
.btn {
  border-radius: 12px;
  font-weight: 500;
  transition: all 0.2s;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
  min-height: 44px;
  border: none;
}

.btn-small {
  padding: 10px 20px;
  font-size: 14px;
  min-height: 44px;
}

.btn-medium {
  padding: 12px 20px;
  font-size: 14px;
  min-height: 44px;
}

.btn-large {
  padding: 14px 24px;
  font-size: 16px;
  min-height: 44px;
}

.btn-primary {
  background-color: #0066cc;
  color: #ffffff;
}

.btn-primary:hover:not(.btn-disabled) {
  background-color: #0052a3;
  box-shadow: 0 2px 8px rgba(0, 102, 204, 0.3);
}

.btn-primary:active:not(.btn-disabled) {
  background-color: #003d7a;
  box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.2);
  transform: scale(0.98);
}

.btn-secondary {
  background-color: #f0f0f0;
  color: #333333;
}

.btn-secondary:hover:not(.btn-disabled) {
  background-color: #e0e0e0;
}

.btn-secondary:active:not(.btn-disabled) {
  background-color: #d0d0d0;
  box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.1);
  transform: scale(0.98);
}

.btn-danger {
  background-color: #ff3b30;
  color: #ffffff;
}

.btn-danger:hover:not(.btn-disabled) {
  background-color: #cc2e26;
  box-shadow: 0 2px 8px rgba(255, 59, 48, 0.3);
}

.btn-danger:active:not(.btn-disabled) {
  background-color: #991f1a;
  box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.2);
  transform: scale(0.98);
}

.btn-disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
