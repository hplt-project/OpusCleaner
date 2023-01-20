<script setup>
import { ref, computed } from 'vue';
import { diffSample } from '../diff.js';
import InlineDiff from './InlineDiff.vue';

const {languages, rows, refRows, displayAsRows} = defineProps({
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

const isShowingDiff = computed(() => {
	return refRows !== null;
})

const differences = computed(() => {
	return refRows !== null ? diffSample(languages.value, refRows, rows) : [];
});

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

</script>

<template>
	<div class="filter-output-table">
		<div v-if="isShowingDiff" class="controls">
			<span>Comparing sample to the filtered sample: {{ stats.additions }} lines added, {{ stats.deletions }} lines removed, and {{ stats.changes }} lines changed.</span>
			<template v-if="stats.additions || stats.deletions || stats.changes">
				<button @click="scrollToNextChange()" title="Scroll to next difference">Next</button>
			</template>
		</div>
		<div ref="outputElement" class="sample" :class="{'display-as-rows': displayAsRows}">
			<table v-if="rows">
				<thead>
					<tr>
						<th v-for="lang in languages" :key="lang">{{ languageName(lang) }}</th>
					</tr>
				</thead>
				<tbody v-if="isShowingDiff" class="table-diff">
					<template v-for="(chunk, i) in differences">
						<tr v-for="(entry, j) in chunk.value" :key="`${i}:${j}`" :class="{'added':chunk.added, 'removed':chunk.removed, 'changed':chunk.changed}">
							<td v-for="lang in languages" :key="lang" :lang="lang">
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
					<tr v-for="(entry, i) in rows" :key="i">
						<td v-for="lang in languages" :key="lang" :lang="lang">{{entry[lang]}}</td>
					</tr>
				</tbody>
			</table>
		</div>
	</div>
</template>

<style scoped>
.filter-output-table {
	display: flex;
	overflow: hidden;
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

	border: 1px solid #1c3948;
  text-align: left;
  background-color: #e3eaeb;
  row-gap: 10px;

  position: relative; /* for the sticky thead */
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