import { ref, toRaw, reactive } from 'vue';
import { cyrb53 } from '../hash.js';

// Configuration (steps) per dataset
const configurations = new Map();

async function fetchFilterSteps(dataset) {
	const response = await fetch(`/api/datasets/${encodeURIComponent(dataset.name)}/configuration.json`);
	return await response.json();
}

function hashFilterSteps(configuration) {
	return cyrb53(JSON.stringify(configuration));
}

export function getFilterSteps(dataset) {
	if (!configurations.has(dataset.name)) {
		const entry = {
			hash: ref(null),
			steps: ref([])
		};

		configurations.set(dataset.name, entry);

		fetchFilterSteps(dataset).then(configuration => {
			entry.steps.value = configuration;
			entry.hash.value = hashFilterSteps(configuration);
		});
	}

	return configurations.get(dataset.name).steps;
}

export async function saveFilterSteps(dataset) {
	const entry = configurations.get(dataset.name);
	const steps = entry.steps.value;

	// (Hashing before the `await fetch` to make sure we capture the submitted state)
	const hash = hashFilterSteps(steps);

	const response = await fetch(`/api/datasets/${encodeURIComponent(dataset.name)}/configuration.json`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			'Accept': 'application/json'
		},
		body: JSON.stringify(steps, null, 2)
	});

	if (response.ok)
		entry.hash.value = hash;

	return response
}

export function filterStepsModified(dataset) {
	const entry = configurations.get(dataset.name);
	const modified = entry.hash.value !== hashFilterSteps(entry.steps.value);
	return modified;
}
