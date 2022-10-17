import { ref, reactive } from 'vue';

/**
 * Overwrite `target` array with `source` array, but re-using any elements
 * already in `target` if possible. Sameness is determined using `keyFn`.
 */
function merge(target, source, keyFn) {
	const current = new Map(target.map(entry => [keyFn(entry), entry]));

	const merged = source.map(entry => {
		if (current.has(keyFn(entry)))
			return Object.assign(current.get(keyFn(entry)), entry)
		else
			return entry
	});

	target.splice(0, target.length, ...merged);
}

const datasets = ref([]);

async function fetchDatasets() {
	const response = await fetch('/api/datasets/');
	merge(datasets.value, await response.json(), dataset => dataset.name);
}

let datasetsRequest = null;

export function getDatasets() {
	if (!datasetsRequest)
		datasetsRequest = fetchDatasets();

	return datasets.value;
}

export function getDataset(name) {
	const dataset = datasets.value.find(dataset => dataset.name === name);
	if (dataset)
		return dataset;

	const placeholder = reactive({name});
	datasets.value.push(placeholder);

	if (!datasetsRequest)
		datasetsRequest = fetchDatasets();
	
	return placeholder;
}