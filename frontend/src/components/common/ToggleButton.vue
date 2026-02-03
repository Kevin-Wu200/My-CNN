<template>
  <button
    class="toggle-btn"
    :class="{ 'toggle-btn-active': isOpen }"
    @click="$emit('toggle')"
  >
    <span class="toggle-label">
      <slot />
    </span>
    <svg
      class="toggle-icon"
      :class="{ 'toggle-icon-rotated': isOpen }"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
    >
      <polyline points="6 9 12 15 18 9" />
    </svg>
  </button>
</template>

<script setup lang="ts">
defineProps<{
  isOpen?: boolean
}>()

defineEmits<{
  toggle: []
}>()
</script>

<style scoped>
.toggle-btn {
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-height: 44px;
  padding: 10px 16px;
  background-color: #f9f9f9;
  color: #333333;
  border: 1px solid #f0f0f0;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.toggle-btn:hover {
  background-color: #f5f5f5;
  border-color: #e0e0e0;
}

.toggle-btn:active {
  background-color: #f0f0f0;
  box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.1);
  transform: scale(0.98);
}

.toggle-btn-active {
  background-color: #f0f0f0;
  border-color: #e0e0e0;
}

.toggle-label {
  flex: 1;
  text-align: left;
}

.toggle-icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
  transition: transform 0.2s;
  color: #666666;
}

.toggle-icon-rotated {
  transform: rotate(180deg);
}
</style>
