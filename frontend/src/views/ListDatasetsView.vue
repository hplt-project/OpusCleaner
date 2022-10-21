<script setup>
import { ref } from 'vue';
import { RouterLink } from 'vue-router';
import { getDatasets } from '../store/datasets.js';
import { getFilterSteps } from '../store/filtersteps.js';
import { getCategoriesForDataset } from '../store/categories.js';
import CategoryPicker from '../components/CategoryPicker.vue';

function languages(dataset) {
	return Object.keys(dataset?.columns || {});
}

const categoryPicker = ref(); // Element

</script>

<template>
	<div class="dataset-list">
		<table>
			<thead>
				<tr>
					<th>Name</th>
					<th>Languages</th>
					<th>Categories</th>
					<th>Filter steps</th>
				</tr>
			</thead>
			<tbody>
				<tr v-for="dataset in getDatasets()" :key="dataset.id">
					<td>{{ dataset.name }}</td>
					<td>{{ languages(dataset).join(', ') }}</td>
					<td>
						<button @click="event => categoryPicker.showForDataset(dataset, event)">Edit</button>
						<span class="category" v-for="category in getCategoriesForDataset(dataset)" :key="category.name">{{ category.name }}</span>
					</td>
					<td><router-link :to="{name: 'edit-filters', params: {datasetName: dataset.name}}">Filters ({{ getFilterSteps(dataset).value.length }})</router-link></td>
				</tr>
			</tbody>
			<tfoot>
				<tr>
					<td colspan="3">
						<RouterLink v-bind:to="{name:'add-dataset'}">Download dataset…</RouterLink>
					</td>
				</tr>
			</tfoot>
		</table>
		<CategoryPicker ref="categoryPicker"></CategoryPicker>
	</div>
</template>

<style>
@import '../css/categories.css';

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