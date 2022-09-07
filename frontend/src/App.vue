<script setup>
import { RouterLink, RouterView } from 'vue-router'
</script>

<template>
  <div class="main-navigation">
    <RouterLink v-bind:to="{name:'list-datasets'}">Datasets</RouterLink>
  </div>
  <RouterView></RouterView>
</template>

<style scoped>
</style>
