<script setup>
import {ref, reactive, computed, watch, onMounted} from 'vue';
import { Interval } from '../interval.js';
import { formatSize } from '../format.js';
import VueSelect from 'vue-select';
import {DownloadCloudIcon} from 'vue3-feather';

import 'vue-select/dist/vue-select.css';

function nonEmpty(x) {
	return x != '';
}

const Preprocessing = {
	MONOLINGUAL: 'monolingual',
	BILINGUAL: 'bilingual'
};

const SORT_ORDER_OPTIONS = [
	{
		label: 'Corpus name',
		compare: (a, b) => a.corpus.localeCompare(b.corpus)
	},
	{
		label: 'Download size',
		compare: (a, b) => b.size - a.size
	},
	{
		label: 'Sentence pairs',
		compare: (a, b) => b.pairs - a.pairs
	}
];

const sortOrder = ref(SORT_ORDER_OPTIONS[0]);

const loading = ref(0);

// Per language all target languages
const languages = new Map();

// Datasets by language
const cache = new Map();

const nameFilter = ref("");

const latestOnly = ref(true);

const preprocessing = ref(Preprocessing.BILINGUAL);

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
	let key;

	switch (preprocessing.value) {
		case Preprocessing.BILINGUAL:
			if (!srcLang.value || !trgLang.value)
				return [];
			key = `${srcLang.value}-${trgLang.value}`;
			break;
		case Preprocessing.MONOLINGUAL:
			if (!srcLang.value)
				return [];
			key = `${srcLang.value}`;
			break;
		default:
			throw new Error('Unknown preprocessing type');
	}
	
	if (!cache.has(key)) {
		const list = ref([]);
		cache.set(key, list);
		// Fetches actual list async, but the cache entry is available immediately.
		fetchDatasets(key).then(datasets => list.value = datasets);
	}

	// cache contains refs, so this computed() is called again once the data
	// is actually fetched.
	let datasets = cache.get(key).value;

	if (nameFilter.value.length > 0)
		datasets = datasets.filter(({corpus, group}) => {
			return corpus.toLowerCase().indexOf(nameFilter.value.toLowerCase()) !== -1;
		});

	datasets = datasets.filter(dataset => {
		switch (preprocessing.value) {
			case Preprocessing.BILINGUAL:
				return dataset.langs.filter(nonEmpty).length > 1;
			case Preprocessing.MONOLINGUAL:
				return dataset.langs.filter(nonEmpty).length == 1;
			default:
				return false;
		}
	});

	if (latestOnly.value) {
		datasets = Array.from(datasets.reduce((latest, dataset) => {
			if (!latest.has(dataset.corpus) || latest.get(dataset.corpus).version < dataset.version)
				latest.set(dataset.corpus, dataset);

			return latest
		}, new Map()).values());
	}

	datasets.sort(sortOrder.value.compare);

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

async function fetchDatasets(key) {
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
			<label class="search-button" :class="{'checked': preprocessing == Preprocessing.MONOLINGUAL}">
				<input type="radio" name="preprocessing" v-model="preprocessing" :value="Preprocessing.MONOLINGUAL">
				Monolingual
			</label>
			<label class="search-button" :class="{'checked': preprocessing == Preprocessing.BILINGUAL}">
				<input type="radio" name="preprocessing" v-model="preprocessing" :value="Preprocessing.BILINGUAL">
				Bilingual
			</label>
			<label class="search-button" :class="{'checked': latestOnly}">
				<input type="checkbox" v-model="latestOnly">
				Latest only
			</label>
			<label>
				<VueSelect v-model="srcLang" :options="srcLangOptions" :reduce="({lang}) => lang" placeholder="Origin language" />
			</label>
			<label v-show="preprocessing == Preprocessing.BILINGUAL">
				<VueSelect v-model="trgLang" :options="trgLangOptions" :reduce="({lang}) => lang" placeholder="Target language" />
			</label>
			<label>
				<VueSelect v-model="sortOrder" :options="SORT_ORDER_OPTIONS" placeholder="Sort order" />
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
					<dd title="Languages">{{ dataset.langs.filter(nonEmpty).join('→') }}</dd>
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