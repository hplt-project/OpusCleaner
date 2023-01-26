import { ref, toRaw, readonly, reactive, computed } from 'vue';
import { cyrb53 } from '../hash.js';
import { getUniqueId } from '../hacks.js';

// Configuration (steps) per dataset
const configurations = new Map();

class FilterStepsList {
	#hash = ref(null); // Hash of last safe
	#steps = ref([]); // List of step configurations
	#history = []; // previous versions of #steps array
	#forward = []; // future versions of #steps array

	hash = readonly(this.#hash);
	steps = readonly(this.#steps);
	
	isModified = computed(() => {
		return this.#hash.value !== hashFilterSteps(this.#steps.value);
	});
	canUndo = computed(() => {
		console.log('canUndo', this.#history.length > 0);
		this.#steps.value;
		return this.#history.length > 0;
	});
	canRedo = computed(() => {
		console.log('canRedo', this.#forward.length > 0);
		this.#steps.value;
		return this.#forward.length > 0;
	});

	construtor() {
		//
	}

	restore(steps) {
		if (steps !== this.steps.value) {
			this.#history.splice(0, this.#history.length);
			this.#forward.splice(0, this.#forward.length);
			this.#steps.value = steps;
		}
		this.#hash.value = hashFilterSteps(steps);
	}

	update(steps) {
		this.#forward.splice(0, this.#forward.length);
		this.#history.push(this.#steps.value);
		this.#steps.value = steps;
	}

	undo() {
		this.#forward.push(this.#steps.value);
		this.#steps.value = this.#history.pop();
	}

	redo() {
		this.#history.push(this.#steps.value);
		this.#steps.value = this.#forward.pop();
	}
}

async function fetchFilterSteps(dataset) {
	const response = await fetch(`/api/datasets/${encodeURIComponent(dataset.name)}/configuration.json`);
	return await response.json();
}

function hashFilterSteps(configuration) {
	return cyrb53(JSON.stringify(configuration));
}

export function getFilterSteps(dataset) {
	if (!configurations.has(dataset.name)) {
		const entry = new FilterStepsList();

		configurations.set(dataset.name, entry);

		fetchFilterSteps(dataset).then(configuration => {
			entry.restore(configuration.map(step => ({...step, id: getUniqueId()})));
		});
	}

	return configurations.get(dataset.name);
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
		entry.restore(steps);

	return response
}
