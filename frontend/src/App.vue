<script setup>
import { RouterLink, RouterView } from 'vue-router'
</script>

<template>
  <div class="main-navigation">
    <RouterLink v-bind:to="{name:'dataset-editor'}">Go to Home</RouterLink>
  </div>
  <RouterView></RouterView>
</template>

<style scoped>
</style>
