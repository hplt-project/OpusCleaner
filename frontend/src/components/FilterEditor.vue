<script setup>
// Docs for Vue@3: https://vuejs.org/guide/introduction.html
// Docs for draggable@4: https://github.com/SortableJS/vue.draggable.next
import {ref, computed, watch, watchEffect, onMounted, readonly} from 'vue';
import draggable from 'vuedraggable';
import LoadingIndicator from './LoadingIndicator.vue';
import {stream} from '../stream.js';
import { getFilters, filterRequiresLanguage } from '../store/filters.js';
import { getFilterSteps, saveFilterSteps, filterStepsModified } from '../store/filtersteps.js';
import { formatNumberSuffix } from '../format.js';
import Checkbox from '../components/Checkbox.vue';
import SegmentedControl from '../components/SegmentedControl.vue';
import FilterStep from '../components/FilterStep.vue';
import FilterOutputTable from '../components/FilterOutputTable.vue';
import {Edit3Icon, TagIcon} from 'vue3-feather';


const multiDragKey = navigator.platform.match(/^(Mac|iPhone$)/) ? 'Meta' : 'Control';

const SampleStep = Symbol('SampleStep');


const {dataset} = defineProps({
	dataset: Object
});

const displayAsRows = ref(false)

const VIEWS = ['original', 'clean', 'changes'];

const view = ref('clean'); // one of VIEWs

const isFetchingSamples = ref(false);

const filters = getFilters();

let filterSteps = getFilterSteps(dataset);

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

const samples = ref([]);

const sample = computed(() => {
	return samples.value.length > 0 ? samples.value[samples.value.length - 1] : null;
});

const original = computed(() => {
	return samples.value.length > 0 ? samples.value[0] : null;
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

const categoryPicker = ref();

</script>

<template>
	<div class="clean-corpus-container">
		<div class="output-panel">
			<header class="controls">
				<Checkbox v-model="displayAsRows">Display as rows</Checkbox>
				<SegmentedControl class="table-buttons" v-model="view" :options="VIEWS"/>
			</header>

			<div class="filter-output">
				<FilterOutputTable
					class="filter-output-table"
					:languages="languages"
					:rows="view === 'original' ? original.stdout : sample?.stdout"
					:ref-rows="view === 'changes' ? original.stdout : null"
					:display-as-rows="displayAsRows"/>
				<div class="filter-error" v-if="sample?.stderr" translate="no">
					<pre>{{ sample.stderr }}</pre>
				</div>
			</div>
		</div>

		<div class="filter-container">
			<div class="filter-input"></div>

			<draggable tag="ol" class="filter-steps"
			v-model="filterSteps" item-key="stamp" 
			:group="{name:'filters'}"
			:multi-drag="true"
			:set-data="setFilterStepData"
			:multi-drag-key="multiDragKey">
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
					<FilterStep
						class="filter-step"
						v-model="filterSteps[i]"
						v-bind:languages="languages">
						<template v-slot:header>
							<LoadingIndicator class="loading-indicator" :state="getLoadingStage(i)"/>
							<span class="filter-name">{{ filterStep.filter }}</span>
							<button v-on:click="removeFilterStep(i)">Remove</button>
						</template>
						<template v-slot:footer>
							<span class="line-count" title="Line count">{{ samples[i+1]?.stdout?.length }}</span>
							<button v-on:click="showOutput(i)">
								Show
								<span v-if="samples[i+1]?.stderr" title="This step produced output on stderr.">⚠</span>
							</button>
							<button v-on:click="showDiff(i)" title="Compare the input and output of this step to show the effects of the filter.">Diff</button> 
						</template>
					</FilterStep>
				</template>
			</draggable>
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
		</div>
	</div>
</template>

<style scoped>
.clean-corpus-container {
	flex: 1 1 auto;
	overflow: hidden;
	display: flex;
	flex-direction: row;
	flex-wrap: nowrap;
}

	.output-panel {
		flex: 1 1 0;
		overflow: hidden;
		display: flex;
		flex-direction: column;
	}

		.filter-output {
			display: flex;
			flex-direction: column;
			flex: 1 1 auto;
			overflow: hidden; 
		}

			.filter-output-table {
				flex: 1;
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

	.filter-container {
		overflow: auto; /*temporary! */
		flex: 0 1 300px;
		overflow: auto;
		border-left: 1px solid var(--border-color);
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

.filter-steps .filter-name {
	flex: 1;
	overflow: hidden;
	text-overflow: ellipsis;
}

.filter-steps .loading-indicator {
	flex: 0 !important;
	align-self: flex-start;
	margin: 0 0.5em 0 0;
}


.controls, .available-filters, .filter-steps {
	margin: 0;
	padding: 0.5em 1em;
	list-style: none;
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