<script setup>
import { ref } from 'vue';
import { RouterLink } from 'vue-router';
import { getDatasets } from '../store/datasets.js';
import { getFilterSteps } from '../store/filtersteps.js';

function languages(dataset) {
	return Object.keys(dataset?.columns || {});
}

</script>

<template>
	<div class="dataset-list">
		<table>
			<tr v-for="dataset in getDatasets()" :key="dataset.id">
				<td>{{ dataset.name }}</td>
				<td>{{ languages(dataset).join(', ') }}</td>
				<td><router-link :to="{name: 'edit-filters', params: {datasetName: dataset.name}}">Filters ({{ getFilterSteps(dataset).length }})</router-link></td>
			</tr>
			<tfoot>
				<tr>
					<td colspan="3">
						<RouterLink v-bind:to="{name:'add-dataset'}">Download dataset…</RouterLink>
					</td>
				</tr>
			</tfoot>
		</table>
	</div>
</template>

<style>
.dataset-list {
	flex: 1;
	overflow: auto;
}

.dataset-list table {
	width: 100%;
}

.dataset-list table tr:nth-child(2n) td {
	background: #eef;
}
</style>