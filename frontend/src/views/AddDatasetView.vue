<script setup>
import {ref, reactive, computed, watch, onMounted} from 'vue';
import { Interval } from '../interval.js';
import { formatSize } from '../format.js';
import VueSelect from 'vue-select';
import {DownloadCloudIcon} from 'vue3-feather';

import 'vue-select/dist/vue-select.css';

const loading = ref(0);

// Per language all target languages
const languages = new Map();

// Datasets by language
const cache = new Map();

const nameFilter = ref("");

const includeMonolingual = ref(true);

const includeBilingual = ref(true);

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

const srcLangOptions = computed(() => {
	const intl = new Intl.DisplayNames([], {type: 'language', languageDisplay: 'standard'});
	return (srcLangs.value || []).map(lang => {
		try {
			return {lang, label: `${intl.of(lang)} (${lang})`};
		} catch (RangeError) {
			return {lang, label: lang};
		}
	})
});

const trgLangOptions = computed(() => {
	const intl = new Intl.DisplayNames([], {type: 'language', languageDisplay: 'standard'});
	return (trgLangs.value || []).map(lang => {
		try {
			return {lang, label: `${intl.of(lang)} (${lang})`};
		} catch (RangeError) {
			return {lang, label: lang};
		}
	})
});

const datasets = computed(() => {
	if (!srcLang.value || !trgLang.value)
		return [];

	const key = `${srcLang.value}-${trgLang.value}`;
	if (!cache.has(key)) {
		const list = ref([]);
		cache.set(key, list);
		// Fetches actual list async, but the cache entry is available immediately.
		fetchDatasets(srcLang.value, trgLang.value).then(datasets => {
			list.value = datasets;
		})
	}

	// cache contains refs, so this computed() is called again once the data
	// is actually fetched.
	let datasets = cache.get(key).value;

	if (nameFilter.value.length > 0)
		datasets = datasets.filter(({name, group}) => {
			return name.toLowerCase().indexOf(nameFilter.value.toLowerCase()) !== -1
					|| group.toLowerCase().indexOf(nameFilter.value.toLowerCase()) !== -1;
		});

	datasets = datasets.filter(dataset => {
		if (dataset.langs.length > 1)
			return includeBilingual.value;
		else
			return includeMonolingual.value;
	});

	return datasets;
});

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

function download(dataset) {
	requestDownloadSelection([dataset]).then(update => {
		Object.assign(downloads, castDownloadListToMap(update));
	});
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

const countFormat = new Intl.NumberFormat();

</script>

<template>
	<div class="downloader">
		<h1 class="datasets-catalogue-title">
			Datasets catalogue
			<small><em>TODO</em> datasets</small>
		</h1>
		<div class="search-inputs">
			<label>
				<input type="search" placeholder="Search dataset…" v-model="nameFilter">
			</label>
			<label class="search-button" :class="{'checked': includeMonolingual}">
				<input type="checkbox" v-model="includeMonolingual">
				Monolingual
			</label>
			<label class="search-button" :class="{'checked': includeBilingual}">
				<input type="checkbox" v-model="includeBilingual">
				Bilingual
			</label>
			<label>
				<VueSelect v-model="srcLang" :options="srcLangOptions" :reduce="({lang}) => lang" placeholder="Origin language" />
			</label>
			<label>
				<VueSelect v-model="trgLang" :options="trgLangOptions" :reduce="({lang}) => lang" placeholder="Target language" />
			</label>
		</div>
		<div class="dataset-list">
			<div class="dataset" v-for="dataset in datasets" :key="dataset.id" :id="`did-${dataset.id}`">
				<div class="dataset-name">
					<h3 class="dataset-title"><a :href="`https://opus.nlpl.eu/${dataset.corpus}-${dataset.version}.php`" target="_blank">{{ dataset.corpus }}</a></h3>
					<button class="download-dataset-button" @click="download(dataset)" :disabled="dataset.id in downloads || 'paths' in dataset">
						Download
						<DownloadCloudIcon class="download-icon"/>
					</button>
				</div>
				<dl class="metadata-dataset">
					<dt>Version</dt>
					<dd title="Version">{{ dataset.version }}</dd>
					<dt>Languages</dt>
					<dd title="Languages">{{ dataset.langs.join('→') }}</dd>
					<dt>Pairs</dt>
					<dd title="Sentence pairs">{{ dataset.pairs ? countFormat.format(dataset.pairs) : '' }}</dd>
					<dt>Size</dt>
					<dd title="Download size">{{ dataset.size ? formatSize(dataset.size) : '' }}</dd>
				</dl>
			</div>
		</div>
		<Teleport to=".navbar">
			<details class="downloads-popup">
				<summary><h2>Downloads</h2></summary>
				<ul>
					<li v-for="download in downloads" :key="download.entry.id">{{ download.entry.corpus }} <em>{{ download.state }}</em></li>
				</ul>
			</details>
		</Teleport>
	</div>
</template>

<style scoped>

.datasets-catalogue-title {
	font-size: 20px;
	color: #182231;
	text-transform: uppercase;
	display: flex;
	align-items: baseline;
}

.datasets-catalogue-title small {
	display: inline-block;
	border-left: 1px solid currentColor;
	margin-left: 10px;
	padding-left: 10px;
}

.datasets-catalogue-title span {
	font-size: 16px;
	font-weight: lighter;
}

.search-inputs {
	margin: 10px 0 20px 0;
}

.search-button {
	color: #182231;
	border: none;
	border-radius: 2px;
	display: inline-block;
	line-height: 28px;
	height: 28px;
	padding: 0 8px;
	margin: 0 2px;
	cursor: pointer;
	background-color: #dbe5e6;
}

.search-button.checked {
	background-color: #e4960e;
}

.search-button input {
	display: none;
}

.search-inputs input {
	height: 28px;
	border-radius: 3px;
}

.search-inputs input::placeholder {
	padding-left: 5px;
}

.search-inputs .v-select {
	display: inline-block;
	width: 180px;
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
	cursor: pointer;
}

.download-dataset-button:disabled {
	cursor: default;
}

.download-icon {
	margin-left: 5px;
}
</style>