// Docs for Vue@3: https://vuejs.org/guide/introduction.html
import {createApp} from 'vue';
// Docs for draggable@4: https://github.com/SortableJS/vue.draggable.next
import draggable from 'vuedraggable';
import {diff} from 'diff';
import InlineDiff from 'inlinediff';

// Simple hash function for creating string hashes
function cyrb53(str, seed = 0) {
	let h1 = 0xdeadbeef ^ seed, h2 = 0x41c6ce57 ^ seed;
	for (let i = 0, ch; i < str.length; i++) {
		ch = str.charCodeAt(i);
		h1 = Math.imul(h1 ^ ch, 2654435761);
		h2 = Math.imul(h2 ^ ch, 1597334677);
	}
	h1 = Math.imul(h1 ^ (h1>>>16), 2246822507) ^ Math.imul(h2 ^ (h2>>>13), 3266489909);
	h2 = Math.imul(h2 ^ (h2>>>16), 2246822507) ^ Math.imul(h1 ^ (h1>>>13), 3266489909);
	return 4294967296 * (2097151 & h2) + (h1>>>0);
}

// Async generator for lines
// From https://developer.mozilla.org/en-US/docs/Web/API/ReadableStreamDefaultReader/read#example_2_-_handling_text_line_by_line
async function* lineIterator(reader) {
	const decoder = new TextDecoder("utf-8");
	let {value, done} = await reader.read();
	value = value ? decoder.decode(value, {stream: true}) : "";

	const re = /\r\n|\n|\r/gm;
	let startIndex = 0;

	while (true) {
	  let result = re.exec(value);
	  if (result) {
	  	yield value.substring(startIndex, result.index);
	  	startIndex = re.lastIndex;
	  	continue;
	  }
	  
	  if (done)
	  	break;

		let remainder = value.substr(startIndex);
    ({value, done} = await reader.read());
    value = remainder + (value ? decoder.decode(value, {stream: true}) : "");
    startIndex = 0;
    re.lastIndex = 0;
	}
	
	// if the last line didn't end in a newline char
  if (startIndex < value.length)
	  yield value.substr(startIndex);
}

async function* stream(url, options) {
	const response = await fetch(url, options);
	if (!response.ok)
		throw new Error(await response.text());
	const reader = response.body.getReader();
	for await (let line of lineIterator(reader)) {
		yield JSON.parse(line);
	}
}

const app = createApp({
	data() {
		return {
			displayAsRows: false,
			datasets: [],
			selectedDataset: null,
			samples: [],
			isFetchingSamples: false,
			_sampleAbortController: new AbortController(),
			filters: [],
			filterSteps: [],
			filterStepsLastSave: null,
			selectedFilterStep: null,
			comparingFilterStep: null,
			SampleStep: {}
		};
	},

	computed: {
		languages() {
			return this.selectedDataset ? Array.from(Object.keys(this.selectedDataset.columns)).sort() : []
		},
		filterStepsStateHash() {
			return cyrb53(JSON.stringify(this.filterSteps));
		},
		filterStepsChangedSinceLastSave() {
			return this.filterStepsLastSave !== this.filterStepsStateHash;
		},
		multiDragKey() {
			return navigator.platform.match(/^(iP|Mac)/) ? 'Meta' : 'Control';
		},
		sampleIndex() {
			const index = this.selectedFilterStep ? this.filterSteps.indexOf(this.selectedFilterStep) + 1 : -1;
			return index >= 0 ? index : this.samples.length - 1;
		},
		comparingSampleIndex() {
			// Trick: comparingFilterStep == SampleStep -> indexOf == -1 -> index == 0
			return this.filterSteps.indexOf(this.comparingFilterStep) + 1;
		},
		sample() {
			return this.samples.length > this.sampleIndex ? this.samples[this.sampleIndex] : null;
		},
		displayDiff() {
			return this.comparingFilterStep !== null;
		},
		diff() {
			return this.diffSample(this.samples[this.comparingSampleIndex], this.samples[this.sampleIndex]);
		}
	},

	watch: {
		selectedDataset() {
			this.fetchSample();
			this.fetchFilterSteps();
		},
		filterSteps: {
			deep: true,
			handler() {
				this.fetchSample()
			}
		}
	},

	created() {
		this._serial = 0;
		this._stamps = new WeakMap();
	},

	async mounted() {
		this.fetchDatasets();
		this.fetchFilters();
	},

	components: {
		draggable,
		InlineDiff,
	},

	methods: {
		async fetchDatasets() {
			const response = await fetch('/datasets/');
			this.datasets = await response.json();
		},
		async fetchFilters() {
			const response = await fetch('/filters/');
			// Turn the {name:Filter} map into a [Filter] list and fold the 'name' attribute into the Filter.name property.
			this.filters = Array.from(Object.entries(await response.json()), ([name, value]) => Object.assign(value, {name}));
		},
		async fetchSample() {
			this._sampleAbortController.abort();

			this._sampleAbortController = new AbortController();
			this.isFetchingSamples = true;
			this.samples.splice(0, this.samples.length);

			const response = stream(`/datasets/${encodeURIComponent(this.selectedDataset.name)}/sample`, {
				method: 'POST',
				signal: this._sampleAbortController.signal,
				headers: {
					'Content-Type': 'application/json',
					'Accept': 'application/json',
				},
				body: JSON.stringify(this.filterSteps)
			});

			for await (let sample of response) {
				this.samples.push(sample);
			}

			this.isFetchingSamples = false;
		},
		async fetchFilterSteps() {
			const response = await fetch(`/datasets/${encodeURIComponent(this.selectedDataset.name)}/configuration.json`)
			this.filterSteps = await response.json();
			this.filterStepsLastSave = this.filterStepsStateHash;
		},
		async saveFilterSteps() {
			const hash = this.filterStepsStateHash;

			const response = await fetch(`/datasets/${encodeURIComponent(this.selectedDataset.name)}/configuration.json`, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					'Accept': 'application/json'
				},
				body: JSON.stringify(this.filterSteps)
			});

			if (response.ok)
				this.filterStepsLastSave = hash;
			else
				alert(await response.text());
		},
		createFilterStep(filter) {
			return {
				filter: filter.name,
				language: this.filterRequiresLanguage({filter:filter.name}) ? this.languages[0] : null,
				parameters: Object.fromEntries(Object.entries(filter.parameters).map(([key, parameter]) => [key, parameter.default]))
			}
		},
		addFilterStep(filter) {
			this.filterSteps.push(this.createFilterStep(filter));
		},
		removeFilterStep(i) {
			this.filterSteps.splice(i, 1);
		},
		filterDefinition(filterStep) {
			return this.filters.find(filter => filter.name === filterStep.filter);
		},
		filterRequiresLanguage(filterStep) {
			return this.filterDefinition(filterStep).type == 'monolingual';
		},
		stamp(obj) {
			if (!this._stamps.has(obj))
				this._stamps.set(obj, ++this._serial);
			return this._stamps.get(obj);
		},
		formatNumberSuffix(n) {
			let suffix = 'th';

			if (n % 10 === 1 && n % 100 !== 11)
				suffix = 'st';
			else if (n % 10 === 2 && n % 100 !== 12)
				suffix = 'nd';
			else if (n % 10 === 3 && n % 100 !== 13)
				suffix = 'rd';

			return `${n}${suffix}`;
		},
		diffSample(previous, sample) {
			// Only mark different if neither of the columns is the same.
			const equals = (a, b) => !this.languages.every(lang => a[lang] != b[lang]);
			
			// Mark pairs that have exactly the same text on both sides as identical.
			const identical = (a, b) => this.languages.every(lang => a[lang] == b[lang]);

			const chunks = diff(previous?.stdout || [], sample?.stdout || [], {equals});

			let offset = 0;

			// Now also fish out all those rows that appear the same, but have
			// a difference in only one of the languages
			for (let i = 0; i < chunks.length; ++i) {
				console.assert(chunks[i].count === chunks[i].value.length);

				if (chunks[i].added) {
					offset -= chunks[i].count;
					continue;
				}

				if (chunks[i].removed) {
					offset += chunks[i].count;
					continue;
				}

				let first, last; // first offset of difference, offset of the first identical that follows.

				// Search for the first different sentence pair in this mutation block.
				for (first = 0; first < chunks[i].value.length; ++first) {
					if (!identical(previous.stdout[offset + first], chunks[i].value[first]))
						break;
				}

				// Did we find the first different sentence pair? If not skip this
				// chunk of chunks.
				if (first == chunks[i].value.length) {
					offset += chunks[i].count;
					continue;
				}

				// Find the first line that is identical again, the end of our
				// 'changed' block.
				for (last = first+1; last < chunks[i].value.length; ++last) {
					if (identical(previous.stdout[offset + last], chunks[i].value[last]))
						break;
				}

				// If it's not the first line of the mutation, we need to split it
				// in at least two (maybe three)
				if (first > 0) {
					chunks.splice(i, 0, {count: first, value: chunks[i].value.splice(0, first)})
					++i; // We inserted it before the one we're handling right now,
					     // so increase `i` accordingly
				}

				chunks[i].count = last - first;
				chunks[i].changed = true;

				// If the mutation contains lines that are the same after the
				// changed ones, add those back in as well. Make sure they are
				// evaluated next.
				if (last - first < chunks[i].value.length) {
					const count = chunks[i].value.length - (last - first);
					chunks.splice(i+1, 0, {count, value: chunks[i].value.splice(last - first, count)});
					// Do not increase i so next iteration looks at this newly added
					// one, there might be more changes here!
				}

				console.assert(chunks[i].value.every((curr, i) => !identical(previous.stdout[offset + first + i], curr)));

				// TODO clean this up this is a test.
				chunks[i].differences = chunks[i].value.map((current, i) => ({previous: previous.stdout[offset + first + i], current}));

				offset += last; // Add the offset for this plus optionally the
				                // spliced in identical chunk we added.
			}

			return chunks;
		}
	}
})

export {app};
