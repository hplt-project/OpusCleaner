<script setup>
import {ref, computed, onMounted} from 'vue';

const loading = ref(0);

// Per language all target languages
const languages = new Map();

// Datasets by language
const cache = new Map();

const srcLang = ref();

const trgLang = ref();

const srcLangs = ref();

const trgLangs = computed(() => {
	if (!srcLang.value)
		return [];

	if (!languages.has(srcLang.value)) {
		const list = ref([]);
		languages.set(srcLang.value, list);
		fetchTargetLanguages(srcLang.value).then(langs => {
			list.value = langs
		});
	}

	return languages.get(srcLang.value).value; // reactive, so will update once fetch() finishes
});

const datasets = computed(() => {
	if (!srcLang.value || !trgLang.value)
		return [];

	const key = `${srcLang.value}-${trgLang.value}`;
	if (!cache.has(key)) {
		const list = ref([]);
		cache.set(key, list);
		fetchDatasets(srcLang.value, trgLang.value).then(datasets => {
			list.value = datasets;
		})
	}

	return cache.get(key).value;
});

const selection = ref([]); // List of datasets to download

onMounted(async () => {
	fetchSourceLanguages().then(languages => {
		srcLangs.value = languages;
	})
})

async function fetchSourceLanguages() {
	try {
		loading.value += 1;
		const response = await fetch('/api/download/languages/');
		return await response.json();
	} finally {
		loading.value -= 1;
	}
}

async function fetchTargetLanguages(sourceLanguage) {
	try {
		loading.value += 1;
		const response = await fetch(`/api/download/languages/${encodeURIComponent(sourceLanguage)}`);
		return await response.json();
	} finally {
		loading.value -= 1;
	}
}

async function fetchDatasets(srcLang, trgLang) {
	const key = `${srcLang}-${trgLang}`;

	try {
		loading.value += 1;
		const response = await fetch(`/api/download/by-language/${encodeURIComponent(key)}`)
		return await response.json();
	} finally {
		loading.value -= 1;
	}
}

</script>

<template>
	<div class="downloader">
		<div class="filter-controls">
			<label>
				Source
				<select v-model="srcLang">
					<option v-for="lang in srcLangs" :key="lang" :value="lang">{{ lang }}</option>
				</select>
			</label>
			<label>
				Target
				<select v-model="trgLang">
					<option v-for="lang in trgLangs" :key="lang" :value="lang">{{ lang }}</option>
				</select>
			</label>
		</div>
		<div class="dataset-list">
			<table>
				<tr v-for="dataset in datasets" :key="dataset.id">
					<td><input type="checkbox" v-model="selection" :value="dataset"></td>
					<td>{{ dataset.name }}</td>
					<td>{{ dataset.group }}</td>
					<td>{{ dataset.version }}</td>
					<td>{{ dataset.langs.join(', ') }}</td>
				</tr>
			</table>
		</div>
		<div class="dataset-selection">
			<h2>Shopping cart</h2>
			<ul>
				<li v-for="dataset in selection" :key="dataset.id">{{ dataset.name }}</li>
			</ul>
		</div>
	</div>
</template>

<style scoped>
.downloader {
	flex: 1;
	display: flex;
	flex-direction: row;
	overflow: hidden;
}

.downloader > * {
	padding: 1em;
}

.downloader > *:not(:first-child) {
	border-left: 1px solid #ccc;
}

.filter-controls {
	flex: 0 0 200px;
}

.filter-controls label {
	display: block;
}

.dataset-list {
	flex: 1;
	overflow: auto;
}

.dataset-selection {
	flex: 0 0 300px;
	overflow: auto;
}

</style>