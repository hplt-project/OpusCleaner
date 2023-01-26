<script setup>
import { useRoute } from 'vue-router';
import { ref, computed } from 'vue';
import { getDataset } from '../store/datasets.js';
import { UploadIcon } from 'vue3-feather';
import TagsEditor from '../components/TagsEditor.vue';
import FilterEditor from '../components/FilterEditor.vue';

const route = useRoute();

const dataset = computed(() => {
	return getDataset(route.params.datasetName)
});
</script>

<template>
	<div class="filter-editor">
		<header>
			<h2>Dataset: <em>{{ dataset.name }}</em></h2>
			<TagsEditor :dataset="dataset"/>
		</header>

		<FilterEditor v-if="dataset" :dataset="dataset"/>

		<Teleport to=".navbar">
			<RouterLink class="import-data-button" v-bind:to="{name:'add-dataset'}">
				Import dataset
				<UploadIcon class="import-data-icon" />
			</RouterLink>
		</Teleport>
	</div>
</template>

<style scoped>
	@import '../css/navbar.css';

	.filter-editor {
		overflow: hidden;
		max-height: calc(100vh - 120px);
		display: flex;
		flex-direction: column;
	}
</style>