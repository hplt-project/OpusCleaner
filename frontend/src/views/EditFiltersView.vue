<script setup>
import { useRoute } from 'vue-router';
import { ref, computed } from 'vue';
import { getDataset } from '../store/datasets.js';
import { TagIcon, UploadIcon, Edit3Icon } from 'vue3-feather';
import { getCategoriesForDataset } from '../store/categories.js';
import CategoryPicker from '../components/CategoryPicker.vue';
import FilterEditor from '../components/FilterEditor.vue';

const route = useRoute();

const dataset = computed(() => {
	return getDataset(route.params.datasetName)
});

const categoryPicker = ref();

</script>

<template>
	<div class="filter-editor">
		<header>
			<h2>Dataset: <em>{{ dataset.name }}</em></h2>

			<div class="tags-container">
				<div class="category-tags">
					<span class="tag" v-for="category in getCategoriesForDataset(dataset)" :key="category.name">
						<TagIcon/>
						<span class="tag-name">{{ category.name }}</span>
					</span>
				</div>
				<button class="icon-button" @click="categoryPicker.showForDataset(dataset, $event)"><Edit3Icon/></button>
			</div>
		</header>

		<FilterEditor v-if="dataset" :dataset="dataset"/>

		<CategoryPicker ref="categoryPicker"/>

		<Teleport to=".navbar">
			<RouterLink class="import-data-button" v-bind:to="{name:'add-dataset'}">
				Import dataset
				<UploadIcon class="import-data-icon" />
			</RouterLink>
		</Teleport>
	</div>
</template>

<style scoped>
	@import '../css/categories.css';
	@import '../css/navbar.css';

	.filter-editor {
		overflow: hidden;
		max-height: calc(100vh - 120px);
		display: flex;
		flex-direction: column;
	}
</style>