<script setup>
import {getDownloads} from '../store/downloads.js';
</script>

<template>
	<details class="downloads-popup">
		<summary><h2>Downloads</h2></summary>
		<ul>
			<li v-for="download in getDownloads()" :key="download.entry.id">{{ download.entry.corpus }} <em>{{ download.state }}</em></li>
		</ul>
	</details>
</template>

<style>

</style>