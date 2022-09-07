<script setup>
import { useRoute } from 'vue-router';
import {ref, watch} from 'vue';
import FilterEditor from '../components/FilterEditor.vue';

const dataset = ref(null);

const route = useRoute();

watch(route, fetchDataset, {immediate: true});

async function fetchDataset() {
	const response = await fetch('/api/datasets/');
	const datasets = await response.json();
	dataset.value = datasets.find(d => d.name === route.params.datasetName)
	console.log('Fetched dataset', dataset.value);
}

</script>

<template>
	<FilterEditor v-if="dataset" :dataset="dataset"/>
</template>