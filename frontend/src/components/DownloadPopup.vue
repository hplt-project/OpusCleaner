<script setup>
import {getDownloads, cancelDownload, retryDownload} from '../store/downloads.js';
import {XCircleIcon, RefreshCwIcon} from 'vue3-feather';
</script>

<template>
	<details class="downloads-popup">
		<summary>Downloads</summary>
		<ul>
			<li v-for="download in getDownloads()" :key="download.entry.id" :class="download.state">
				<span class="corpus-name">{{ download.entry.corpus }}</span>
				<em class="download-state">{{ download.state }}</em>
				<button v-if="['pending', 'downloading'].includes(download.state)" @click="cancelDownload(download)" title="Cancel download">
					<XCircleIcon/>
				</button>
				<button v-if="['failed', 'cancelled'].includes(download.state)" @click="retryDownload(download)" title="Retry download">
					<RefreshCwIcon/>
				</button>
			</li>
		</ul>
	</details>
</template>

<style scoped>
.downloads-popup summary {
	display: flex;
	align-items: center;
	border: none;
	border-radius: 3px;
	height: 40px;
	padding: 0 30px;
	background-color: #17223d;
	color: #e4960e;
	font-size: 18px;

	text-decoration: none;
	line-height: 40px;
}

.downloads-popup {
	position: relative;
}

.downloads-popup ul {
	position: absolute;
	right: 0;
	background: white;
	border: 1px solid #ccc;
	border-radius: 2px;
	padding: 10px;
	z-index: 10;
	box-shadow: rgba(0, 0, 0, 0.15) 0px 3px 6px 0px;
	overflow: hidden;
	overflow-y: auto;
	max-height: calc(100vh - 100px);
}
.downloads-popup li {
	list-style: none;
	display: flex;
	width: 240px;
	height: 40px;
	align-items: center;
}

.downloads-popup .corpus-name {
	flex: 1 1 auto;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.downloads-popup .download-state {
	margin-left: auto;
	padding: 0 4px;
	opacity: 0.5;
}

.downloads-popup button {
	appearance: none;
	background: none;
	border: none;
	margin: 0 0 0 2px;
	cursor: pointer;
	opacity: 0.5;
}

.downloads-popup button:hover,
.downloads-popup button:active {
	opacity: 1.0;
}

.pending {
	background: #FFFFBB;
}

.downloading {
	background: #BBFFBB;
}

.downloaded {
	background: #BBBBFF;
}
</style>