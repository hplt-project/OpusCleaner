<script setup>
import { useRoute } from 'vue-router';
import { computed } from 'vue';
import { getDataset } from '../store/datasets.js';
import FilterEditor from '../components/FilterEditor.vue';

const route = useRoute();

const dataset = computed(() => {
	return getDataset(route.params.datasetName)
});

</script>

<template>
	<FilterEditor v-if="dataset" :dataset="dataset"/>
</template>