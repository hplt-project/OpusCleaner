<script setup>
import { ref, computed, readonly, onUpdated } from 'vue';
import { diffSample } from '../diff.js';
import InlineDiff from './InlineDiff.vue';

const props = defineProps({
	languages: {
		type: Array,
	},
	rows: {
		type: Array,
	},
	refRows: {
		type: Array,
		default: null
	},
	displayAsRows: {
		type: Boolean,
		default: false
	}
});

const outputElement = ref();

const isShowingDiff = computed(() => props.refRows !== null);

const differences = computed(() => readonly(props.refRows !== null ? diffSample(props.languages, props.refRows, props.rows) : []));

const stats = computed(() => {
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

function languageName(lang) {
	const intl = new Intl.DisplayNames([], {type:'language'});
	try {
		return intl.of(lang);
	} catch (RangeError) {
		return lang;
	}
}

const gutter = ref();

onUpdated(() => {
	if (gutter.value.hidden = !isShowingDiff.value)
		 return;

	const viewHeight = outputElement.value.clientHeight;
	const tableHeight = outputElement.value.firstElementChild.clientHeight;

	gutter.value.width = 16;
	gutter.value.height = viewHeight;

	const ctx = gutter.value.getContext('2d');
	const {width, height} = gutter.value;
	ctx.clearRect(0, 0, width, height);

	const colors = {
		'added': 'green',
		'removed': 'red',
		'changed': 'yellow'
	};

	outputElement.value.querySelectorAll('tbody tr:is(.added, .removed, .changed)').forEach(row => {
		ctx.fillStyle = colors[row.className];
		ctx.fillRect(
			/* x */ 0,
			/* y */ row.offsetTop / tableHeight * viewHeight,
			/* w */ width,
			/* h */ Math.max(row.offsetHeight / tableHeight, 1)
		);
	});
});

</script>

<template>
	<div class="filter-output-table">
		<div ref="outputElement" class="sample" :class="{'display-as-rows': props.displayAsRows}">
			<table v-if="rows">
				<thead>
					<tr>
						<th v-for="lang in props.languages" :key="lang">{{ languageName(lang) }}</th>
					</tr>
					<tr v-if="isShowingDiff">
						<td :colspan="props.languages.length">
							<div class="controls" v-if="stats.additions || stats.deletions || stats.changes">
								<!-- Wrapping controls in a div because a <td/> is hard to style -->
								<span>Comparing sample to the filtered sample: {{ stats.additions }} lines added, {{ stats.deletions }} lines removed, and {{ stats.changes }} lines changed.</span>
								<button @click="scrollToNextChange()" title="Scroll to next difference">Next</button>
							</div>
						</td>
					</tr>
				</thead>
				<tbody v-if="isShowingDiff" class="table-diff">
					<template v-for="(chunk, i) in differences">
						<tr v-for="(entry, j) in chunk.value" :key="`${i}:${j}`" :class="{'added':chunk.added, 'removed':chunk.removed, 'changed':chunk.changed}">
							<td v-for="lang in props.languages" :key="lang" :lang="lang">
								<template v-if="chunk.changed">
									<InlineDiff class="inline-diff" :current="entry[lang]" :previous="chunk.differences[j].previous[lang]"/>
								</template>
								<template v-else>
									{{entry[lang]}}
								</template>
							</td>
						</tr>
					</template>
				</tbody>
				<tbody v-else>
					<tr v-for="(entry, i) in props.rows" :key="i">
						<td v-for="lang in props.languages" :key="lang" :lang="lang">{{entry[lang]}}</td>
					</tr>
				</tbody>
			</table>
			<canvas class="gutter" ref="gutter" width="16"></canvas>
		</div>
	</div>
</template>

<style scoped>
.filter-output-table {
	display: flex;
	overflow: hidden;
	flex-direction: column;
}

.controls {
	flex: 0;
	display: flex;
	justify-content: space-between;
	padding: 0.4em;
}

.sample {
	flex: 1 1 auto;
	overflow-y: auto;

	display: flex;
}

.sample table {
	flex: 1;
	table-layout: fixed;
	border-collapse: collapse;
	width: 100%;
	overflow: hidden;

	border: 1px solid #1c3948;
  text-align: left;
  background-color: #e3eaeb;
  row-gap: 10px;

  position: relative; /* for the sticky thead */
}

.sample .gutter {
	flex: 0;
	position: sticky;
	top: 0;
}

.sample table thead {
  color: #e4960e;
  background-color: #17223d;
  position: sticky;
  top: 0;
}

.sample table thead th {
  padding: 20px 0 10px 10px;
}
.sample table thead tr {
  margin-bottom: 10px;
}

.sample table tbody td {
  border: 1px solid #1c3948;
  color: #1d4149;
  line-height: 1.4;
}

.sample table td {
	width: 50%;
	padding: 0.25em 0.5em;
	vertical-align: top;
	word-wrap: break-word;
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
	width: 3em;
	text-align: right;
	margin: 0 0.5em 0 0;
	opacity: 0.5;
}
</style>