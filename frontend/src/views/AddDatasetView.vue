<script setup>
import {ref, reactive, computed, watch, onMounted} from 'vue';
import { Interval } from '../interval.js';
import { formatSize } from '../format.js';
import {DownloadCloudIcon} from 'vue3-feather';

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

const sizeRequests = new Map();

watch(datasets, (datasets) => {
	datasets.forEach(dataset => {
		if (dataset.size)
			return;

		if (!sizeRequests.has(dataset.id))
			sizeRequests.set(dataset.id,
				fetch(`/api/download/datasets/${encodeURIComponent(dataset.id)}`)
					.then(response => response.json()))

		sizeRequests.get(dataset.id).then(remote => {
			Object.assign(dataset, remote);
		});
	})
})

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
		<h1 class="datasets-catalogue-title">
			Datasets catalogue
			<small>12.345 datasets</small>
		</h1>
		<div class="search-inputs">
			<label>
				<input type="text" placeholder="Search dataset…">
			</label>
			<label class="toggle">
				<input type="checkbox">
				Monolingual
			</label>
			<label class="toggle">
				<input type="checkbox">
				Bilingual
			</label>
			<label>
				Origin language
				<select v-model="srcLang">
					<option v-for="lang in srcLangs" :key="lang" :value="lang">{{ lang }}</option>
				</select>
			</label>
			<label>
				Target language
				<select v-model="trgLang">
					<option v-for="lang in trgLangs" :key="lang" :value="lang">{{ lang }}</option>
				</select>
			</label>
		</div>
		<div class="dataset-list">
			<div class="dataset" v-for="dataset in datasets" :key="dataset.id" :id="`did-${dataset.id}`">
				<div class="dataset-name">
					<h3 class="dataset-title">{{ dataset.name }}</h3>
					<button class="download-dataset-button">
						Download
						<DownloadCloudIcon class="download-icon"/>
					</button>
				</div>
				<dl class="metadata-dataset">
					<dt>Group</dt>
					<dd title="Group">{{ dataset.group }}</dd>
					<dt>Languages</dt>
					<dd title="Languages">{{ dataset.langs.join('-') }}</dd>
					<dt>Size</dt>
					<dd tile="Download size">{{ dataset.size ? formatSize(dataset.size) : '' }}</dd>
				</dl>
			</div>
		</div>
		<Teleport to=".navbar">
			<details class="downloads-popup">
				<summary><h2>Downloads</h2></summary>
				<ul>
					<li v-for="download in downloads" :key="download.entry.id">{{ download.entry.name }} <em>{{ download.state }}</em></li>
				</ul>
			</details>
		</Teleport>
	</div>
</template>

<style scoped>
.datasets-catalogue-title {
	font-size: 20px;
	color: #182231;
}

.datasets-catalogue-title span {
	font-size: 16px;
	font-weight: lighter;
}

.search-inputs {
	margin: 10px 0 20px 0;
}
.search-button {
	background-color: #e4960e;
	color: #182231;
	border: none;
	border-radius: 2px;
	height: 28px;
	padding: 0 8px;
	margin: 0 2px;
}

.search-inputs input {
	height: 28px;
	border-radius: 3px;
}

.search-inputs input::placeholder {
	padding-left: 5px;
}

.search-inputs select {
	height: 28px;
	border-radius: 3px;
}

.dataset-list {
	display: grid;
	grid-template-columns: repeat(auto-fill,minmax(400px, 1fr));
	row-gap: 20px;
	column-gap: 20px;
}

.dataset {
	display: flex;
	flex-direction: column;
	justify-content: space-between;
	background-color: #dbe5e6;
	border-radius: 5px;
	padding: 20px;
	height: 120px;
}

.dataset-name {
	display: flex;
	justify-content: space-between;
}
.dataset-title {
	font-size: 26px;
}

.metadata-dataset dt {
	display: none;
}

.metadata-dataset dd {
	display: inline;
	margin-right: 20px;
}

.download-dataset-button {
	display: flex;
	align-items: center;
	width: 100px;
	padding: 2px 8px;
	border: none;
	border-radius: 2px;
	background-color: #dfbd79;
}
.download-icon {
	margin-left: 5px;
}
</style>