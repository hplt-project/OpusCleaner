<script setup>
import { useRoute } from 'vue-router';
import {ref, watch} from 'vue';
import FilterEditor from '../components/FilterEditor.vue';

const dataset = ref(null);

const route = useRoute();

watch(route.params.datasetName, fetchDataset);

async function fetchDataset() {
	const response = await fetch('/api/datasets/');
	const datasets = await response.json();
	dataset = datasets.find(d => d.name === route.params.datasetName)
}

</script>

<template>
	<FilterEditor v-if="dataset" :dataset="dataset"/>
</template>