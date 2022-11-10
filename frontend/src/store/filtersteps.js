import { ref, toRaw, readonly, reactive, computed, watch } from 'vue';
import { cyrb53 } from '../hash.js';
import { getUniqueId } from '../hacks.js';

const FILTERSTEP_SAVE_DELAY = 1500;

// Configuration (steps) per dataset
const configurations = new Map();

class FilterStepsList {
	#steps = ref([]); // List of step configurations
	steps = readonly(this.#steps);
	
	serverHash = ref(null); // Hash of last save
	clientHash = computed(() => hashFilterSteps(this.#steps.value));
	isModified = computed(() => this.serverHash.value !== this.clientHash.value);
	
	#history = []; // previous versions of #steps array
	#forward = []; // future versions of #steps array

	canUndo = computed(() => {
		this.#steps.value; // mentioned for dependency
		return this.#history.length > 0;
	});
	canRedo = computed(() => {
		this.#steps.value; // mentioned for dependency
		return this.#forward.length > 0;
	});

	restore(steps) {
		if (steps === this.steps.value)
			return;

		this.#history.splice(0, this.#history.length);
		this.#forward.splice(0, this.#forward.length);
		this.#steps.value = steps;
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
			entry.serverHash.value = entry.clientHash.value;

			watch(entry.clientHash, (newHash, oldHash, onCleanup) => {
				if (newHash === entry.serverHash.value)
					return;

				// Delay saving a bit for new changes so we don't hammer the API
				const delay = setTimeout(async () => {
					console.assert(entry.isModified.value, 'filtersteps configuration is marked as not-modified');
					console.assert(entry.clientHash.value === newHash, 'hash changed after watch() but onCleanup was not called');
					console.assert(newHash === hashFilterSteps(entry.steps.value), 'newHash does not match the hash for the current filtersteps configuration');
					
					const response = await fetch(`/api/datasets/${encodeURIComponent(dataset.name)}/configuration.json`, {
						method: 'POST',
						headers: {
							'Content-Type': 'application/json',
							'Accept': 'application/json'
						},
						body: JSON.stringify(entry.steps.value, null, 2)
					});

					if (response.ok)
						entry.serverHash.value = newHash;
				}, FILTERSTEP_SAVE_DELAY);

				onCleanup(() => clearTimeout(delay));
			})
		});
	}

	return configurations.get(dataset.name);
}

export function defaultValue(parameter) {
	switch (parameter.type) {
		case 'tuple':
			return parameter.parameters.map(parameter => defaultValue(parameter));
		case 'list':
			return [];
		case 'str':
			return '';
		default:
			return parameter.default
	}
}

