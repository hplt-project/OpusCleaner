<script setup>
import {ref, onMounted} from 'vue';

const datasets = ref([]);

onMounted(async () => {
	const response = await fetch('/api/datasets/');
	datasets.value = await response.json();
})

function languages(dataset) {
	return Object.keys(dataset.columns);
}

</script>

<template>
	<table>
		<tr v-for="dataset in datasets">
			<td>{{ dataset.name }}</td>
			<td>{{ languages(dataset).join(', ') }}</td>
			<td><router-link :to="{name: 'edit-filters', params: {datasetName: dataset.name}}">Filters</router-link></td>
		</tr>
	</table>
</template>
