<script setup>
// Docs for Vue@3: https://vuejs.org/guide/introduction.html
// Docs for draggable@4: https://github.com/SortableJS/vue.draggable.next
import {ref, computed, watch, watchEffect, onMounted, readonly} from 'vue';
import draggable from 'vuedraggable';
import {diff} from '../diff.js';
import InlineDiff from './InlineDiff.vue';
import LoadingIndicator from './LoadingIndicator.vue';
import {stream} from '../stream.js';
import { getFilters } from '../store/filters.js';
import { getFilterSteps, saveFilterSteps, filterStepsModified } from '../store/filtersteps.js';
import { getCategoriesForDataset } from '../store/categories.js';
import { formatNumberSuffix } from '../format.js';
import CategoryPicker from '../components/CategoryPicker.vue';


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

		if (chunks[i].added)
			continue;

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

	return readonly(chunks);
}

const {dataset} = defineProps({
	dataset: Object
});

const displayAsRows = ref(false)

const samples = ref([]);

const isFetchingSamples = ref(false);

const filters = getFilters();

let filterSteps = ref(getFilterSteps(dataset));

const selectedFilterStep = ref(null);

const comparingFilterStep = ref(null);

const languages = computed(() => {
	// Unloaded state the dataset will have a name, but not all its details yet
	if (!dataset?.columns)
		return [];

	const languages = Array.from(Object.keys(dataset.columns)).sort();
	// First try non-alphabetical order. If no success, return alphabetical order
	if (!dataset.name.includes(languages.reverse().join('-')))
		languages.reverse();
	
	return languages;
});

const filterStepsChangedSinceLastSave = computed(() => {
	return filterStepsModified(dataset);
});

const sampleIndex = computed(() => {
	const index = selectedFilterStep.value ? filterSteps.value.indexOf(selectedFilterStep.value) + 1 : -1;
	return index >= 0 ? index : samples.value.length - 1;
});

const comparingSampleIndex = computed(() => {
	// Trick: comparingFilterStep == SampleStep -> indexOf == -1 -> index == 0
	return filterSteps.value.indexOf(comparingFilterStep.value) + 1;
});

const sample = computed(() => {
	return samples.value.length > sampleIndex.value ? samples.value[sampleIndex.value] : null;
});

const isShowingDiff = computed(() => {
	return comparingFilterStep.value !== null;
});

const differences = computed(() => {
	return diffSample(
		languages.value,
		samples.value[comparingSampleIndex.value],
		samples.value[sampleIndex.value]);
});

const differencesStats = computed(() => {
	let additions = 0, deletions = 0, changes = 0;

	differences.value.forEach(({added, removed, changed, count}) => {
		if (added)
			additions += count;
		else if (removed)
			deletions += count;
		else if (changed)
			changes += count;
	});

	return {additions, deletions, changes};
});

let _sampleAbortController = new AbortController();

async function fetchSample() {
	_sampleAbortController.abort();
	_sampleAbortController = new AbortController();
	
	isFetchingSamples.value = true;
	samples.value = [];

	const response = stream(`/api/datasets/${encodeURIComponent(dataset.name)}/sample`, {
		method: 'POST',
		signal: _sampleAbortController.signal,
		headers: {
			'Content-Type': 'application/json',
			'Accept': 'application/json',
		},
		body: JSON.stringify(filterSteps.value, null, 2)
	});

	for await (let sample of response) {
		samples.value.push(readonly(sample));
	}

	isFetchingSamples.value = false;
}

watchEffect(fetchSample);

function createFilterStep(filter) {
	return {
		filter: filter.name,
		language: filterRequiresLanguage({filter:filter.name}) ? languages.value[0] : null,
		parameters: Object.fromEntries(Object.entries(filter.parameters).map(([key, parameter]) => [key, parameter.default]))
	}
}

function addFilterStep(filter) {
	filterSteps.value.push(createFilterStep(filter));
}

function removeFilterStep(i) {
	filterSteps.value.splice(i, 1);
}

function filterDefinition(filterStep) {
	return filters.value.find(filter => filter.name === filterStep.filter);
}

function filterRequiresLanguage(filterStep) {
	return filterDefinition(filterStep)?.type == 'monolingual';
}

function setFilterData(dataTransfer, el) {
	dataTransfer.setData('text/plain', JSON.stringify(createFilterStep(el.__draggable_context.element), null, 2));
}

function setFilterStepData(dataTransfer, el) {
	dataTransfer.setData('text/plain', JSON.stringify(el.__draggable_context.element, null, 2));
}
	
function getLoadingStage(index) {
	if (samples.value.length === index + 1) // `+1` because first of samples is the raw sample)
		return 'loading';
	else if (samples.value.length >= index + 1 && samples.value[index + 1].stderr)
		return 'failed';
	else if (samples.value.length >= index + 1)
		return 'loaded';
	else
		return 'pending';
}

const outputElement = ref();

function scrollToNextChange() {
	const rows = outputElement.value.querySelectorAll('tr.added, tr.removed, tr.changed');

	let next = 0;

	// Find first hidden change (i.e. the next one to scroll to if we're scrolling down)
	for (; next < rows.length; ++next) {
		if (rows[next].offsetTop > outputElement.value.clientHeight + outputElement.value.scrollTop) {
			break;
		}
	}

	const row = rows[(rows.length + next) % rows.length];
	outputElement.value.scrollTo({
		top: (row.offsetTop + row.offsetHeight) - outputElement.value.clientHeight,
		behavior: 'smooth'
	});
}

function showOutput(filterStepIndex) {
	selectedFilterStep.value = filterStepIndex >= 0 ? filterSteps.value[filterStepIndex] : SampleStep;
	comparingFilterStep.value = null;
}

function showDiff(filterStepIndex) {
	selectedFilterStep.value = filterSteps.value[filterStepIndex];
	comparingFilterStep.value = filterStepIndex > 0 ? filterSteps.value[filterStepIndex - 1] : SampleStep;
}

const categoryPicker = ref();

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

		<button @click="categoryPicker.showForDataset(dataset, $event)">Edit categories</button>
		<ul class="dataset-categories">
			<li class="category" v-for="category in getCategoriesForDataset(dataset)" :key="category.name">{{ category.name }}</li>
		</ul>

		<CategoryPicker ref="categoryPicker"></CategoryPicker>

		<button v-on:click="saveFilterSteps(dataset)" v-bind:disabled="!filterStepsChangedSinceLastSave">Save filtering steps</button>

		<label v-if="isFetchingSamples">Loading sample…</label>
	</div>

	<div class="main">
		<div class="filter-output">
			<div v-if="isShowingDiff" class="controls">
				<span>Comparing intermediate output after {{ comparingSampleIndex > 0 ? formatNumberSuffix(comparingSampleIndex) : 'the unmodified sample' }} and {{ formatNumberSuffix(sampleIndex) }} filter step: {{ differencesStats.additions }} lines added, {{ differencesStats.deletions }} lines removed, and {{ differencesStats.changes }} lines changed.</span>
				<button v-if="comparingFilterStep" v-on:click="comparingFilterStep=null">Stop comparing</button>
				<template v-if="differencesStats.additions || differencesStats.deletions || differencesStats.changes">
					<button @click="scrollToNextChange()" title="Scroll to next difference">Next</button>
				</template>
			</div>
			<div v-else-if="sampleIndex != samples.length - 1" class="controls">
				<span>Showing intermediate output of {{ sampleIndex > 0 ? formatNumberSuffix(sampleIndex) + ' filter step' : 'the unmodified sample' }}.</span>
				<button v-if="comparingFilterStep" v-on:click="selectedFilterStep=null">Show final output</button>
			</div>
			<div ref="outputElement" v-bind:class="{'sample':true, 'display-as-rows': displayAsRows}">
				<table v-if="sample?.stdout">
					<thead>
						<tr>
							<th v-for="lang in languages">{{lang}}</th>
						</tr>
					</thead>
					<tbody v-if="isShowingDiff" class="table-diff">
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
				v-bind:set-data="setFilterData"
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
				v-bind:set-data="setFilterStepData"
				v-bind:multi-drag-key="multiDragKey">
				<template v-slot:header>
					<li class="property-list">
						<header>
							<LoadingIndicator class="loading-indicator" :state="getLoadingStage(-1)"/>
							<span class="filter-name">Sample</span>
						</header>
						<footer>
							<span class="line-count" title="Line count">{{ samples[0]?.stdout?.length }}</span>
							<button v-on:click="showOutput(-1)">Show</button>
						</footer>
					</li>
				</template>
				<template v-slot:item="{element:filterStep, index:i}">
					<li class="property-list">
						<header>
							<LoadingIndicator class="loading-indicator" :state="getLoadingStage(i)"/>
							<span class="filter-name">{{ filterStep.filter }}</span>
							<button v-on:click="removeFilterStep(i)">Remove</button>
						</header>
						<div v-if="filterRequiresLanguage(filterStep)">
							<label v-bind:for="`step-${i}-column`">Column</label>
							<select v-bind:id="`step-${i}-column`" v-model="filterStep.language">
								<option v-for="lang in languages">{{lang}}</option>
							</select>
						</div>
						<div v-for="(parameter, name) in filterDefinition(filterStep)?.parameters || {}">
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
							<span class="line-count" title="Line count">{{ samples[i+1]?.stdout?.length }}</span>
							<button v-on:click="showOutput(i)">
								Show
								<span v-if="samples[i+1]?.stderr" title="This step produced output on stderr.">⚠</span>
							</button>
							<button v-on:click="showDiff(i)" title="Compare the input and output of this step to show the effects of the filter.">Diff</button>
						</footer>
					</li>
				</template>
			</draggable>
		</div>
	</div>
</template>

<style scoped>
@import '../css/categories.css';

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
	border-top: 1px solid var(--border-color);
	flex: 0 0 auto;
	overflow: hidden;
	overflow-y: auto;
	max-height: 100%;
	height: 40%;
	resize: vertical;
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
	background: rgba(128,128,128, 0.25);
}

.table-diff tr.added td {
	background: rgba(0, 255, 0, 0.25);
	font-style: italic;
}

.table-diff tr.removed td {
	background: rgba(255, 0, 0, 0.25);
	text-decoration: line-through;
}

.table-diff tr.changed td {
	background: rgba(255, 255, 0, 0.25);
}

.inline-diff ins {
	background: rgba(128, 255, 128, 0.25);
}

.inline-diff del {
	background: rgba(255, 128, 128, 0.25);
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
	border-left: 1px solid var(--border-color);
}

.available-filters {
	flex: 0;
}

.filter-steps {
	flex: 1 0 auto;
	border-top: 1px solid var(--border-color);
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
	border-left: 1px solid var(--border-color);
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
	background: var(--background-color); /* for when it is being dragged */
}

.filter-steps li.selected {
	box-shadow: 0 0 0 4px rgba(0, 0, 255, 0.5);
}

.filter-steps li:not(:last-child):not(.selected)::after {
	content: '';
	width: 0;
	height: 0;
	border-top: 1em solid var(--border-color);
	border-left: 1em solid transparent;
	border-right: 1em solid transparent;
	position: absolute;
	left: calc(50% - 1em);
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
	border: 1px solid var(--border-color);
	border-radius: 4px;
}

.property-list > *:not(:last-child) {
	border-bottom: 1px solid var(--border-color);
}

.property-list > header {
	background: var(--border-color);
}

.property-list > * > *:first-child {
	margin-left: 0;
}

.property-list > header > button {
	flex: 0;
}

.property-list > header > .filter-name {
	overflow: hidden;
	text-overflow: ellipsis;
}

.property-list > header > .loading-indicator {
	flex: 0;
	align-self: flex-start;
}

.property-list > * {
	padding: 0.5em;
	display: flex;
	flex-wrap: wrap;
	justify-content: space-between;
}

.property-list > header > *,
.property-list > footer > * {
	flex: 1;
}

.property-list > * > * {
	flex: 0;
	align-self: center;
	margin-left: 0.5em;
}

.property-list > * > small {
	flex: 1 0 100%;
}

.property-list > * > input[type=checkbox] {
	flex-basis: 1em;
}

.dataset-categories {
	display: inline;
	list-style: none;
	padding: 0;
}

.dataset-categories li {
	display: inline;
}

</style>