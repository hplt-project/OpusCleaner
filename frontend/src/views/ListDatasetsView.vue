<script setup>
import { ref } from 'vue';
import { RouterLink, RouterView } from 'vue-router';
import { getDatasets } from '../store/datasets.js';
import { getFilterSteps } from '../store/filtersteps.js';
import { getCategoriesForDataset } from '../store/categories.js';
import TagsEditor from '../components/TagsEditor.vue';
import {UploadIcon, CodeIcon, FilterIcon, PieChartIcon, Edit3Icon, TagIcon} from 'vue3-feather';
import NoDatasetImage from '../assets/data-cuate.svg';

function languages(dataset) {
	const keys = Object.keys(dataset?.columns || {});
	const intl = new Intl.DisplayNames([], {type:'language'});
	return keys.map(lang => intl.of(lang));
}

</script>

<template>
	<div class="table-container-first-screen">
		<Teleport to=".navbar">
			<RouterLink class="import-data-button" v-bind:to="{name:'add-dataset'}">
				Import dataset
				<UploadIcon class="import-data-icon" />
			</RouterLink>
		</Teleport>

		<h2 class="table-title">Your datasets</h2>

		<table class="datasets-table" v-if="getDatasets().length > 0">
			<thead>
				<tr>
					<th>Name</th>
					<th>Languages</th>
					<th>Categories</th>
					<th>Filter steps</th>
					<th>Actions</th>
				</tr>
			</thead>
			<tbody>
				<tr v-for="dataset in getDatasets()" :key="dataset.id">
					<td>{{ dataset.name }}</td>
					<td>{{ languages(dataset).join('–') }}</td>
					<td class="tags"><TagsEditor :dataset="dataset"/></td>
					<td class="filter-steps">
						{{ getFilterSteps(dataset).steps.value.length }}
					</td>
					<td>
						<RouterLink class="icon-button" title="Show filter yaml" :to="{name: 'edit-filters-yaml', params: {datasetName: dataset.name}}"><CodeIcon/></RouterLink>
						<RouterLink class="icon-button" title="Edit filters" :to="{name: 'edit-filters', params: {datasetName: dataset.name}}"><FilterIcon/></RouterLink>
						<RouterLink class="icon-button" title="Show dataset statistics" :to="{}"><PieChartIcon/></RouterLink>
					</td>
				</tr>
			</tbody>
		</table>
		<div class="illustration-container" v-else>
			<img :src="NoDatasetImage">
			<p>No datasets yet. Click on the import data button on the right to get started.</p>
			<p class="credits">Image by <a href="https://www.freepik.com/free-vector/no-data-concept-illustration_8961448.htm" target="_blank">storyset on Freepik</a>.</p>
		</div>
		<RouterView/><!-- for modals -->
	</div>
</template>

<style scoped>
.import-data-button {
	display: flex;
	align-items: center;
	border: none;
	border-radius: 3px;
	height: 40px;
	padding: 0 30px;
	background-color: #17223d;
	color: #e4960e;
	font-size: 18px;

	text-decoration: none;
	line-height: 40px;
}

.import-data-icon {
	margin-left: 5px;
}
.datasets-table {
	border: 2px solid #1c3948;
	border-collapse: collapse;
	width: 100%;
}

.datasets-table thead {
	background-color: #17223d;
	color: #e4960e;
	font-size: 20px;
	text-align: left;
}

.datasets-table tbody {
	color: #17223d;
}

.datasets-table thead th {
	padding: 20px 0px 10px 10px;
	min-width: 150px;
}

.datasets-table tbody tr {
	border-bottom: 1px solid #1c3948;
	border-right: 2px solid #1c3948;
}

.datasets-table tbody td {
	border-right: 2px solid #1c3948;
}

.datasets-table tbody tr td {
	padding: 10px;
}

.category-tags {
	display: flex;
}

.tags {
	width: 45%;
}

.filter-steps {
	text-align: right;
}

.illustration-container {
	text-align: center;
	font-size: 1.2em;
	line-height: 2;
}

.illustration-container img {
	max-width: 600px;
	width: calc(100% - 4em);
	margin: 2em;
}

.illustration-container .credits {
	font-size: 0.8em;
}

</style>