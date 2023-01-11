<script setup>
import { ref } from 'vue';
import { RouterLink } from 'vue-router';
import { getDatasets } from '../store/datasets.js';
import { getFilterSteps } from '../store/filtersteps.js';
import { getCategoriesForDataset } from '../store/categories.js';
import CategoryPicker from '../components/CategoryPicker.vue';
import {UploadIcon, CodeIcon, FilterIcon, PieChartIcon, Edit3Icon, TagIcon} from 'vue3-feather';

function languages(dataset) {
	const keys = Object.keys(dataset?.columns || {});
	const intl = new Intl.DisplayNames([], {type:'language'});
	return keys.map(lang => intl.of(lang));
}

const categoryPicker = ref(); // Element

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

		<table class="datasets-table">
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
					<td class="tags">
						<div class="tags-container">
							<div class="category-tags">
								<span class="tag" v-for="category in getCategoriesForDataset(dataset)" :key="category.name">
									<TagIcon/>
									<span class="tag-name">{{ category.name }}</span>
								</span>
							</div>
							<button class="icon-button" @click="event => categoryPicker.showForDataset(dataset, event)"><Edit3Icon/></button>
						</div>
					</td>
					<td class="filter-steps">
						{{ getFilterSteps(dataset).value.length }}
					</td>
					<td>
						<RouterLink class="icon-button" title="Show filter yaml" :to="{}"><CodeIcon/></RouterLink>
						<RouterLink class="icon-button" title="Edit filters" :to="{name: 'edit-filters', params: {datasetName: dataset.name}}"><FilterIcon/></RouterLink>
						<RouterLink class="icon-button" title="Show dataset statistics" :to="{}"><PieChartIcon/></RouterLink>
					</td>
				</tr>
			</tbody>
		</table>
		<CategoryPicker ref="categoryPicker"></CategoryPicker>
	</div>
</template>

<style scoped>
@import '../css/categories.css';

.icon-button {
	appearance: none;
	border: none;
	background: inherit;
	cursor: pointer;
	color: inherit;
}

.icon-button:visited {
	color: inherit;
}

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

.tags-container {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.tags {
  width: 45%;
  font-family: "Fira Code", monospace;
}

.filter-steps {
  text-align: right;
}

.tag {
  display: flex;
  align-items: center;
  width: fit-content;
  padding: 3px 20px 3px 10px;
  border-radius: 15px;
  margin-right: 5px;
  font-size: 14px;
  background-color: #ddd;
}

.green-tag {
  background-color: #afffca;
}

.red-tag {
  background-color: #ffafaf;
}

.blue-tag {
  background-color: #afcfff;
}

</style>