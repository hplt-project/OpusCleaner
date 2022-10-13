<script setup>
import {ref, reactive, computed, watch, onMounted} from 'vue';
import { Interval } from '../interval.js';

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

const downloads = reactive({});

onMounted(async () => {
	fetchSourceLanguages().then(languages => {
		srcLangs.value = languages;
	})

	fetchDownloads().then(list => {
		Object.assign(downloads, castDownloadListToMap(list))
	})
})

let downloadUpdateInterval = new Interval(1000, async () => {
	const list = await fetchDownloads();
	Object.assign(downloads, castDownloadListToMap(list));
})

// Watch list of downloads to re-evaluate whether we need to do updating using
// the downloadUpdateInterval. Stop updating once there's nothing active
// anymore. The changes caused by downloadSelection() will re-trigger this
// watch expression and enable the interval again.
watch(downloads, (downloads) => {
	const activeStates = new Set(['pending', 'downloading']);
	if (Object.values(downloads).some(download => activeStates.has(download.state)))
		downloadUpdateInterval.restart();
	else
		downloadUpdateInterval.stop();
});

function assignList(current, update, key = 'id') {
	const updates = Object.fromEntries(update.map(entry => [entry[key], entry]));
	for (let i = 0; i < current.length; ++i)
		if (current[i][key] in updates)
			Object.assign(current[i], updates[current[i][key]]);
	return current;
}

function castDownloadListToMap(list) {
	return Object.fromEntries(list.map(download => [download.entry.id, download]));
}

function downloadSelection() {
	requestDownloadSelection(selection.value).then(update => {
		Object.assign(downloads, castDownloadListToMap(update));
	});
	selection.value = [];
}

async function fetchJSON(url, options) {
	try {
		loading.value += 1;
		const response = await fetch(url, options);
		return await response.json();
	} finally {
		loading.value -= 1;
	}
}

async function fetchSourceLanguages() {
	return await fetchJSON('/api/download/languages/');
}

async function fetchTargetLanguages(sourceLanguage) {
	return await fetchJSON(`/api/download/languages/${encodeURIComponent(sourceLanguage)}`);
}

async function fetchDatasets(srcLang, trgLang) {
	const key = `${srcLang}-${trgLang}`;
	return await fetchJSON(`/api/download/by-language/${encodeURIComponent(key)}`);
}

async function fetchDownloads() {
	return await fetchJSON(`/api/download/downloads/`);
}

async function requestDownloadSelection(datasets) {
	return await fetchJSON('/api/download/downloads/', {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json'
		},
		body: JSON.stringify(datasets.map(({id}) => ({id})))
	});
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
					<td><input type="checkbox" v-model="selection" :value="dataset" :disabled="dataset.id in downloads || dataset.paths.length > 0"></td>
					<td>{{ dataset.name }}</td>
					<td>{{ dataset.group }}</td>
					<td>{{ dataset.version }}</td>
					<td>{{ dataset.langs.join(', ') }}</td>
				</tr>
			</table>
		</div>
		<div class="dataset-selection">
			<h2>Downloads</h2>
			<ul>
				<li v-for="download in downloads" :key="download.entry.id">{{ download.entry.name }} <em>{{ download.state }}</em></li>
			</ul>
			<h2>Shopping cart</h2>
			<ul>
				<li v-for="dataset in selection" :key="dataset.id">{{ dataset.name }}</li>
			</ul>
			<button @click="downloadSelection">Download</button>
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