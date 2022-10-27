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

let modifiedCategories = ref(null);

// Make categories default to the ones from the store, unless we've modified
// them already through the UI.
const categories = computed({
	get() {
		if (currentDataset.value === null)
			return null;

		if (modifiedCategories.value !== null)
			return modifiedCategories.value;

		// (Additional problem is that getCategoriesForDataset is reactive. When
		// called before the data is loaded from server, it will return an empty
		// answer and will update once data is fetched. But because of that we can't
		// rely on just calling getCategoriesForDataset() once on showForDataset.)
		return getCategoriesForDataset(currentDataset.value);
	},
	set(value) {
		modifiedCategories.value = value.slice();
	}
});

// When the dataset changes, also reset the changes to the categories we made.
watch(currentDataset, function (current, old) {
		if (current?.name !== old?.name)
			modifiedCategories.value = null;
	},
	{deep: true} // TODO: necessary?
);

function apply() {
	console.assert(currentDataset.value !== null);

	if (modifiedCategories.value !== null) {
		setCategoriesForDataset(modifiedCategories.value, currentDataset.value);
		modifiedCategories.value = null;
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
			<ol class="category-list">
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
	background-color: var(--background-color);
	border: 1px solid var(--border-color);
	min-width: 200px;
	box-shadow: 2px 2px 8px rgba(0, 0, 0, 0.5);
}

.popup > *:not(:last-child) {
	border-bottom: 1px solid var(--border-color);
}

footer {
	text-align: right;
}

footer > *:not(:last-child) {
	margin-right: 0.5em;
}

.category-list {
	list-style: none;
	margin: 0;
	padding: 0;
}

header,
footer,
.category-list label {
	padding: 0.5em;
}

</style>