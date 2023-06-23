import { reactive, watch } from 'vue';
import { fetchJSON } from './fetch.js';
import { Interval } from '../interval.js';

const downloads = reactive({});

export function getDownloads() {
	return downloads;
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

async function fetchDownloads() {
	return await fetchJSON(`/api/download/downloads/`);
}

export function download(dataset) {
	requestDownloadSelection([dataset]).then(update => {
		Object.assign(downloads, castDownloadListToMap(update));
	});
}

export function isDownloading(dataset) {
	return dataset.id in downloads;
}

export async function fetchSourceLanguages() {
	return await fetchJSON('/api/download/languages/');
}

export async function fetchTargetLanguages(sourceLanguage) {
	return await fetchJSON(`/api/download/languages/${encodeURIComponent(sourceLanguage)}`);
}

export async function fetchDownloadableDatasets(key) {
	return await fetchJSON(`/api/download/by-language/${encodeURIComponent(key)}`);
}

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

function castDownloadListToMap(list) {
	return Object.fromEntries(list.map(download => [download.entry.id, download]));
}

fetchDownloads().then(list => {
	Object.assign(downloads, castDownloadListToMap(list))
});
