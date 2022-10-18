<script setup>
import { ref, computed, watch, reactive } from 'vue';
import {
	getCategories,
	getCategoriesForDataset,
	setCategoriesForDataset
} from '../store/categories.js';

const position = reactive({
	top: '0px',
	left: '0px'
});

const isOpen = ref(false);

const currentDataset = ref(null);

let modifiedCategories = null;

// Make categories default to the ones from the store, unless we've modified
// them already through the UI.
const categories = computed({
	get() {
		if (currentDataset.value === null)
			return null;

		if (modifiedCategories !== null)
			return modifiedCategories;

		return getCategoriesForDataset(currentDataset.value);
	},
	set(value) {
		modifiedCategories = value;
	}
});

// When the dataset changes, also reset the changes to the categories we made.
watch(currentDataset, function (current, old) {
		if (current?.name !== old?.name)
			modifiedCategories = null;
	},
	{deep: true} // TODO: necessary?
);

function apply() {
	console.assert(currentDataset.value !== null);

	if (modifiedCategories !== null) {
		setCategoriesForDataset(modifiedCategories, currentDataset.value);
		modifiedCategories = null;
	}

	hide();
}

async function showForDataset(dataset, event) {
	currentDataset.value = dataset;

	if (event) {
		const rect = event.target.getBoundingClientRect();
		Object.assign(position, {
			top: `${rect.bottom}px`,
			left: `${rect.left}px`
		});
	}
}

function hide() {
	currentDataset.value = null;
}

defineExpose({
	showForDataset,
	hide
});

</script>

<template>
	<Teleport to="body">
		<div ref="element" v-if="currentDataset !== null" class="popup" :style="position">
			<header>
				Set categories
			</header>
			<ol>
				<li v-for="category in getCategories()" :key="category.name">
					<label>
						<input type="checkbox" v-model="categories" :value="category">
						{{ category.name }}
					</label>
				</li>
			</ol>
			<footer>
				<button @click="hide">Cancel</button>
				<button @click="apply">Apply</button>
			</footer>
		</div>
	</Teleport>
</template>

<style scoped>
.popup {
	position: fixed;
	top: 0;
	left: 0;
	background: white;
	border: 1px solid #ccc;
}
</style>