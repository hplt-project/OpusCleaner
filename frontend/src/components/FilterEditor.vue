<script>
// Docs for Vue@3: https://vuejs.org/guide/introduction.html
// Docs for draggable@4: https://github.com/SortableJS/vue.draggable.next
import {ref, computed, defineProps, watch, onMounted} from 'vue';
import draggable from 'vuedraggable';
import {diff} from '../diff.js';
import InlineDiff from './InlineDiff.vue';
import {stream} from '../stream.js';

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

const multiDragKey = navigator.platform.match(/^(Mac|iPhone$)/) ? 'Meta' : 'Control';

const SampleStep = Symbol('SampleStep');

function diffSample(languages, previous, sample) {
	// Only mark different if neither of the columns is the same.
	const equals = (a, b) => !languages.every(lang => a[lang] != b[lang]);
	
	// Mark pairs that have exactly the same text on both sides as identical.
	const identical = (a, b) => languages.every(lang => a[lang] == b[lang]);

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

let serial = 0;

const stamps = new WeakMap();

function stamp(obj) {
	if (!stamps.has(obj))
		stamps.set(obj, ++serial);
	return stamps.get(obj);
}

function formatNumberSuffix(n) {
	let suffix = 'th';

	if (n % 10 === 1 && n % 100 !== 11)
		suffix = 'st';
	else if (n % 10 === 2 && n % 100 !== 12)
		suffix = 'nd';
	else if (n % 10 === 3 && n % 100 !== 13)
		suffix = 'rd';

	return `${n}${suffix}`;
}

const shared = {
	// These are here just so they're available to the template
	multiDragKey,
	SampleStep 
};

export default {
	name: 'FilterEditor',

	props: {
		dataset: Object
	},

	data() {
		return Object.assign(Object.create(shared), {
			displayAsRows: false,
			samples: [],
			isFetchingSamples: false,
			filters: [],
			filterSteps: [],
			filterStepsLastSave: null,
			selectedFilterStep: null,
			comparingFilterStep: null,
		});
	},

	computed: {
		languages() {
			const languages = Array.from(Object.keys(this.dataset.columns)).sort();
			// First try non-alphabetical order. If no success, return alphabetical order
			if (!this.dataset.name.includes(languages.reverse().join('-')))
				languages.reverse();
			
			return languages;
		},
		filterStepsStateHash() {
			return cyrb53(JSON.stringify(this.filterSteps));
		},
		filterStepsChangedSinceLastSave() {
			return this.filterStepsLastSave !== this.filterStepsStateHash;
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
			return diffSample(
				this.languages,
				this.samples[this.comparingSampleIndex],
				this.samples[this.sampleIndex]);
		},
		diffStats() {
			let additions = 0, deletions = 0, changes = 0;

			this.diff.forEach(({added, removed, changed, count}) => {
				if (added)
					additions += count;
				else if (removed)
					deletions += count;
				else if (changed)
					changes += count;
			});

			return {additions, deletions, changes};
		}
	},

	watch: {
		filterSteps: {
			deep: true,
			handler() {
				this.fetchSample()
			}
		},
		// TODO: I'd expected this one to be picked up by default since fetchFilterSteps accesses this.dataset.name
		dataset: {
			handler() {
				this.fetchFilterSteps();
			}
		}
	},

	created() {
		this._sampleAbortController = new AbortController();
		this._serial = 0;
	},

	async mounted() {
		await this.fetchFilters();
		await this.fetchFilterSteps();
		// ... that will then trigger fetchSample with the filter configuration applied.
	},

	components: {
		draggable,
		InlineDiff,
	},

	methods: {
		async fetchFilters() {
			const response = await fetch('/api/filters/');
			// Turn the {name:Filter} map into a [Filter] list and fold the 'name' attribute into the Filter.name property.
			this.filters = Array.from(Object.entries(await response.json()), ([name, value]) => Object.assign(value, {name}));
		},
		async fetchSample() {
			this._sampleAbortController.abort();
			this._sampleAbortController = new AbortController();
			
			this.isFetchingSamples = true;
			this.samples.splice(0, this.samples.length);

			const response = stream(`/api/datasets/${encodeURIComponent(this.dataset.name)}/sample`, {
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
			const response = await fetch(`/api/datasets/${encodeURIComponent(this.dataset.name)}/configuration.json`)
			this.filterSteps = await response.json();
			this.filterStepsLastSave = this.filterStepsStateHash;
		},
		async saveFilterSteps() {
			const hash = this.filterStepsStateHash;

			const response = await fetch(`/api/datasets/${encodeURIComponent(this.dataset.name)}/configuration.json`, {
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
		getLoadingStage(index) {
			if (this.samples.length === index + 1) // `+1` because first of samples is the raw sample)
				return 'loading';
			else if (this.samples.length >= index + 1)
				return 'loaded';
			else
				return 'pending';
		},
		stamp,
		formatNumberSuffix,
	}
};
</script>

<template>
	<div class="controls" translate="no">
		<label>
			Dataset: <em>{{ dataset.name }}</em>
		</label>

		<label>
			<input type="checkbox" v-model="displayAsRows">
			Display as rows
		</label>

		<button v-on:click="saveFilterSteps" v-bind:disabled="!filterStepsChangedSinceLastSave">Save filtering steps</button>

		<label v-if="isFetchingSamples">Loading sample…</label>
	</div>

	<div class="main">
		<div class="filter-output">
			<div v-if="displayDiff" class="controls">
				<span>Comparing intermediate output after {{ formatNumberSuffix(comparingSampleIndex) }} and {{ formatNumberSuffix(sampleIndex) }} filter steps: {{ diffStats.additions }} lines added, {{ diffStats.deletions }} lines removed, and {{ diffStats.changes }} lines changed.</span>
				<button v-if="comparingFilterStep" v-on:click="comparingFilterStep=null">Stop comparing</button>
			</div>
			<div v-else-if="sampleIndex != samples.length - 1" class="controls">
				<span>Showing intermediate output of {{ formatNumberSuffix(sampleIndex) }} filter step.</span>
				<button v-if="comparingFilterStep" v-on:click="selectedFilterStep=null">Show final output</button>
			</div>
			<div v-bind:class="{'sample':true, 'display-as-rows': displayAsRows}">
				<table v-if="sample?.stdout">
					<thead>
						<tr>
							<th v-for="lang in languages">{{lang}}</th>
						</tr>
					</thead>
					<tbody v-if="displayDiff" class="table-diff">
						<template v-for="(chunk, i) in differences">
							<tr v-for="(entry, j) in chunk.value" v-bind:key="`${i}:${j}`" v-bind:class="{added:chunk.added, removed:chunk.removed, changed:chunk.changed}">
								<td v-for="lang in languages" v-bind:key="lang" v-bind:lang="lang">
									<template v-if="chunk.changed">
										<InlineDiff class="inline-diff" v-bind:current="entry[lang]" v-bind:previous="chunk.differences[j].previous[lang]"/>
									</template>
									<template v-else>
										{{entry[lang]}}
									</template>
								</td>
							</tr>
						</template>
					</tbody>
					<tbody v-else>
						<tr v-for="(entry, i) in sample.stdout">
							<td v-for="lang in languages" v-bind:key="lang" v-bind:lang="lang">{{entry[lang]}}</td>
						</tr>
					</tbody>
				</table>
			</div>
			<div class="filter-error" v-if="sample?.stderr" translate="no">
				<pre>{{ sample.stderr }}</pre>
			</div>
		</div>

		<div class="filters display-separately" translate="no">
			<draggable tag="ul" class="available-filters"
				v-model="filters" item-key="name"
				v-bind:group="{name:'filters', pull:'clone', put:false}"
				v-bind:sort="false"
				v-bind:clone="createFilterStep">
				<template v-slot:item="{element:filter}">
					<li class="filter">
						<span v-bind:title="filter.description" class="filter-name">{{filter.name}}</span>
						<span class="filter-type">{{filter.type}}</span>
						<button v-on:click="addFilterStep(filter)" class="add-filter-btn">Add</button>
					</li>
				</template>
			</draggable>

			<draggable tag="ol" class="filter-steps"
				v-model="filterSteps" item-key="stamp" 
				v-bind:group="{name:'filters'}"
				v-bind:multi-drag="true"
				v-bind:multi-drag-key="multiDragKey">
				<template v-slot:header>
					<li class="property-list" :class="{[getLoadingStage(-1)]: true}">
						<header>
							<span>Sample</span>
						</header>
						<footer>
							<button v-on:click="selectedFilterStep=SampleStep">Show output</button>
							<button v-on:click="comparingFilterStep=SampleStep" v-bind:disabled="comparingFilterStep===SampleStep">Diff</button>
						</footer>
					</li>
				</template>
				<template v-slot:item="{element:filterStep, index:i}">
					<li class="property-list" :class="{[getLoadingStage(i)]: true}">
						<header>
							<span>{{ filterStep.filter }}</span>
							<button v-on:click="removeFilterStep(i)">Remove</button>
						</header>
						<div v-if="filterRequiresLanguage(filterStep)">
							<label v-bind:for="`step-${i}-column`">Column</label>
							<select v-bind:id="`step-${i}-column`" v-model="filterStep.language">
								<option v-for="lang in languages">{{lang}}</option>
							</select>
						</div>
						<div v-for="(parameter, name) in filterDefinition(filterStep).parameters">
							<label v-bind:for="`step-${i}-${name}`">{{ name }}</label>
							<select v-if="parameter.type == 'str' && parameter.allowed_values" v-model="filterStep.parameters[name]" v-bind:id="`step-${i}-${name}`">
								<option v-for="value in parameter.allowed_values" v-bind:value="value">{{value}}</option>
							</select>
							<input v-else-if="parameter.type == 'bool'" type="checkbox" v-model="filterStep.parameters[name]" v-bind:id="`step-${i}-${name}`">
							<input v-else-if="parameter.type == 'int' || parameter.type == 'float'"
								type="number"
								v-model="filterStep.parameters[name]"
								v-bind:id="`step-${i}-${name}`"
								v-bind:min="parameter.min"
								v-bind:max="parameter.max"
								v-bind:step="parameter.type == 'int' ? 1 : 0.1">
							<input v-else type="text" v-model="filterStep.parameters[name]" v-bind:id="`step-${i}-${name}`">
							
							<small v-if="parameter.help" class="property-list-description">{{parameter.help}}</small>
						</div>
						<footer>
							<button v-on:click="selectedFilterStep=filterStep">
								Show output
								<span v-if="samples[i+1]?.stderr" title="This step produced output on stderr.">⚠</span>
							</button>
							<button v-on:click="comparingFilterStep=filterStep">Diff</button>
						</footer>
					</li>
				</template>
			</draggable>
		</div>
	</div>
</template>

<style scoped>
.filter-output {
	display: flex;
	flex-direction: column;
	flex: 1 1 auto;
/*				overflow: hidden;*/
}

.filter-output .controls {
/*	display: flex;*/
}

.filter-error {
	border-top: 1px solid #ccc;
	flex: 0 0 auto;
	overflow: hidden;
	overflow-y: auto;
}

.filter-error pre {
	white-space: pre-wrap;
}

.sample {
	flex: 1 1 auto;
	overflow-y: auto;
}

.sample table {
	table-layout: fixed;
	border-collapse: collapse;
	width: 100%;
	overflow: hidden;
}

.sample table td {
	width: 50%;
	padding: 0.25em 0.5em;
	vertical-align: top;
}

.sample tr:nth-child(2n) td {
	background: #eef;
}

.table-diff tr.added td {
	background: #efe;
	font-style: italic;
}

.table-diff tr.removed td {
	background: #fee;
	text-decoration: line-through;
}

.table-diff tr.changed td {
	background: #ffe;
}

.inline-diff ins {
	background: #cfc;
}

.inline-diff del {
	background: #fcc;
}

.sample.display-as-rows table thead {
	display: none;
}

.sample.display-as-rows table tr {
	display: block;
	margin-bottom: 1em;
}

.sample.display-as-rows table td {
	display: block;
	width: auto;
}

.sample.display-as-rows td[lang]::before {
	content: attr(lang) ': ';
	display: inline-block;
	margin: 0 0.5em 0 0;
	opacity: 0.5;
}

.filters {
	display: flex;
	flex-direction: column;
	flex: 0 0 300px;
	overflow: auto;
	border-left: 1px solid #ccc;
}

.available-filters {
	flex: 0;
}

.filter-steps {
	flex: 1 0 auto;
	border-top: 1px solid #ccc;
	overflow-y: auto;
}

.filters.display-separately {
	flex-direction: row-reverse;
	flex: 0 0 600px;
	overflow: hidden;
	border: 0;
}

.filters.display-separately .available-filters,
.filters.display-separately .filter-steps {
	flex: 0 0 50%;
	overflow: hidden;
	overflow-y: auto;
	box-sizing: border-box;
	border: 0;
	border-left: 1px solid #ccc;
}

.filter {
	display: flex;
}

.filter .filter-name {
	flex: 2;
}

.filter .filter-type {
	flex: 1;
	font-size: 0.8em;
	padding-left: 0.5em;
}

.filter .add-filter-btn {
	flex: 0;
	align-self: center;
}

.filter-steps li {
	margin: 1em 0;
	position: relative; /* for ::after arrow */
	background: white; /* for draggable */
}

.filter-steps li.selected {
	box-shadow: 0 0 0 4px rgba(0, 0, 255, 0.5);
}

.filter-steps li:not(:last-child):not(.selected)::after {
	content: '';
	width: 0;
	height: 0;
	border-top: 1em solid #ccc;
	border-left: 1em solid transparent;
	border-right: 1em solid transparent;
	position: absolute;
	left: calc(50% - 1em);
}

.filter-steps .property-list > header > span::after {
	content: '';
	float: right;
}

.filter-steps .property-list.loaded > header > span::after {
	content: 'Loaded';
}

.filter-steps .property-list.loading > header > span::after {
	content: 'Loading';
}

.filter-steps .property-list.pending > header > span::after {
	content: 'Pending';
}

.controls, .available-filters, .filter-steps {
	margin: 0;
	padding: 0.5em 1em;
	list-style: none;
}

input[type=number] {
	width: 5em;
}

input[type=checkbox] {
	width: 1em;
}

.property-list {
	border: 1px solid #ccc;
	border-radius: 4px;
}

.property-list > *:not(:last-child) {
	border-bottom: 1px solid #ccc;
}

.property-list > header {
	background: #ccc;
}

.property-list > header > button {
	align-self: flex-end;
}

.property-list > * {
	padding: 0.5em;
	display: flex;
	flex-wrap: wrap;
}

.property-list > * > * {
	flex: 0;
	align-self: center;
	margin-left: 0.5em;
}

.property-list > * > *:first-child {
	flex: 1;
	align-self: flex-start;
	margin-left: 0;
}

.property-list > * > small {
	flex: 1 0 100%;
}

.property-list > * > input[type=checkbox] {
	flex-basis: 1em;
}
</style>