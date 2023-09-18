<script setup>
import {ref, reactive, computed, watch, onMounted} from 'vue';
import {RouterLink, useRouter} from 'vue-router';
import { formatSize } from '../format.js';
import VueSelect from 'vue-select';
import {DownloadCloudIcon, CheckIcon, LoaderIcon} from 'vue3-feather';
import DownloadPopup from '../components/DownloadPopup.vue';
import {fetchJSON} from '../store/fetch.js';
import {
	startDownload,
	startDownloads,
	isDownloading,
	fetchDownloadableDatasets,
	fetchSourceLanguages,
	fetchTargetLanguages
} from '../store/downloads.js';

import 'vue-select/dist/vue-select.css';

function nonEmpty(x) {
	return x != '';
}

const Preprocessing = {
	MONOLINGUAL: 'monolingual',
	BILINGUAL: 'bilingual'
};

const props = defineProps({
	preprocessing: {
		type: String,
		default: 'bilingual'
	},
	languages: {
		type: Array,
		default: () => []
	}
});

// Store for later, used in the router for the add-dataset-defaults route
window.localStorage['add-dataset-preprocessing'] = props.preprocessing;
window.localStorage['add-dataset-languages'] = props.languages.join(';');

const router = useRouter();

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

// Per language all target languages
const languages = new Map();

// Datasets by language
const cache = new Map();

const nameFilter = ref("");

const latestOnly = ref(true);

const srcLangs = ref();

const trgLangs = computed(() => {
	if (!props.languages[0])
		return [];

	if (!languages.has(props.languages[0])) {
		const list = ref([]);
		languages.set(props.languages[0], list);
		fetchTargetLanguages(props.languages[0]).then(langs => {
			list.value = langs
		});
	}

	return languages.get(props.languages[0]).value; // reactive, so will update once fetch() finishes
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

	switch (props.preprocessing) {
		case Preprocessing.BILINGUAL:
			if (!props.languages[0] || !props.languages[1])
				return [];
			key = `${props.languages[0]}-${props.languages[1]}`;
			break;
		case Preprocessing.MONOLINGUAL:
			if (!props.languages[0])
				return [];
			key = `${props.languages[0]}`;
			break;
		default:
			throw new Error('Unknown preprocessing type');
	}
	
	if (!cache.has(key)) {
		const list = ref([]);
		cache.set(key, list);
		// Fetches actual list async, but the cache entry is available immediately.
		fetchDownloadableDatasets(key).then(datasets => list.value = datasets);
	}

	// cache contains refs, so this computed() is called again once the data
	// is actually fetched.
	let datasets = cache.get(key).value;

	if (nameFilter.value.length > 0)
		datasets = datasets.filter(({corpus, group}) => {
			return corpus.toLowerCase().indexOf(nameFilter.value.toLowerCase()) !== -1;
		});

	datasets = datasets.filter(dataset => {
		switch (props.preprocessing) {
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

const downloadableDatasets = computed(() => datasets.value.filter((dataset) => {
	// Datasets that have a path, or that are being downloaded right now, are not
	// offered as downloadable.
	if (('paths' in dataset) || isDownloading(dataset))
		return false;
	return true;
}));

onMounted(async () => {
	fetchSourceLanguages().then(languages => {
		srcLangs.value = languages;
	})
})

function beep(list) {
	alert(list.length);
}

function assignList(current, update, key = 'id') {
	const updates = Object.fromEntries(update.map(entry => [entry[key], entry]));
	for (let i = 0; i < current.length; ++i)
		if (current[i][key] in updates)
			Object.assign(current[i], updates[current[i][key]]);
	return current;
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
			<span class="segmented-control">
				<RouterLink :class="{'search-button': true, 'checked': preprocessing == Preprocessing.MONOLINGUAL}" :to="{name: 'add-dataset', params: {preprocessing: Preprocessing.MONOLINGUAL, languages:props.languages.slice(0, 1)}}">
					Monolingual
				</RouterLink>
				<RouterLink :class="{'search-button': true, 'checked': preprocessing == Preprocessing.BILINGUAL}" :to="{name: 'add-dataset', params: {preprocessing: Preprocessing.BILINGUAL, languages:props.languages}}">
					Bilingual
				</RouterLink>
			</span>
			<label class="search-button" :class="{'checked': latestOnly}">
				<input type="checkbox" v-model="latestOnly">
				Latest only
			</label>
			<label>
				<VueSelect
					:options="srcLangOptions"
					:reduce="({lang}) => lang" 
					:modelValue="props.languages[0]"
					@update:modelValue="(lang) => router.push({name: 'add-dataset', params: {preprocessing: props.preprocessing, languages: [lang].concat(props.languages.slice(1))}})"
					placeholder="Origin language" />
			</label>
			<label v-show="preprocessing == Preprocessing.BILINGUAL">
				<VueSelect 
					:options="trgLangOptions"
					:reduce="({lang}) => lang" 
					:modelValue="props.languages[1]"
					@update:modelValue="(lang) => router.push({name: 'add-dataset', params: {preprocessing: props.preprocessing, languages: [props.languages[0], lang]}})"
					placeholder="Target language" />
			</label>
			<label class="sort-order">
				Sort by:
				<VueSelect v-model="sortOrder" :options="SORT_ORDER_OPTIONS" placeholder="Sort order" />
			</label>
			<button class="download-dataset-button" @click="startDownloads(downloadableDatasets)" :disabled="downloadableDatasets.length === 0">
				Download all
				<DownloadCloudIcon class="download-icon"/>
			</button>
		</div>
		<div class="dataset-list">
			<div class="dataset" v-for="dataset in datasets" :key="dataset.id" :id="`did-${dataset.id}`">
				<div class="dataset-name">
					<h3 class="dataset-title"><a :href="`https://opus.nlpl.eu/${dataset.corpus}-${dataset.version}.php`" target="_blank">{{ dataset.corpus }}</a></h3>
					<button v-if="'paths' in dataset || isDownloading(dataset).state === 'downloaded'" class="download-dataset-button" disabled="disabled">
						Downloaded
						<CheckIcon class="download-icon"/>
					</button>
					<button v-else-if="isDownloading(dataset)" class="download-dataset-button" disabled>
						{{ isDownloading(dataset).state }}
						<LoaderIcon class="download-icon loading-spinner"/>
					</button>
					<button v-else class="download-dataset-button" @click="startDownload(dataset)">
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
			<DownloadPopup/>
		</Teleport>
	</div>
</template>

<style scoped>

.loading-spinner {
	animation: rotate 1.5s linear infinite;
}

@keyframes rotate {
	to {
		transform: rotate(360deg);
	}
}

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
	display: flex;
	margin: 10px 0 20px 0;
}

.search-inputs > *:not(:first-child) {
	margin-left: 3px;
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

.search-inputs .sort-order {
	margin-left: auto; /* push button to the right of the screen */
}

a.search-button {
	text-decoration: none;
}

.segmented-control {
	display: inline-flex;
	margin: 0 2px;
}

.segmented-control .search-button {
	flex: 1 1 auto;
	margin: 0;
	border-radius: 0;
}

.segmented-control .search-button:first-child {
	border-radius: 2px 0 0 2px;
}

.segmented-control .search-button:last-child {
	border-radius: 0 2px 2px 0;
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
	align-self: flex-start;
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