<template>
  <div class="card" :class="{ 'card-elevated': elevated }">
    <slot />
  </div>
</template>

<script setup lang="ts">
defineProps<{
  elevated?: boolean
}>()
</script>

<style scoped>
.card {
  background-color: #ffffff;
  border-radius: 16px;
  padding: 20px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  transition: box-shadow 0.2s;
}

.card-elevated {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
}

.card:hover {
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1);
}
</style>
