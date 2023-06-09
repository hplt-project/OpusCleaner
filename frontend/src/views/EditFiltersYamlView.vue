<template>
	<pre><code>{{ code }}</code></pre>
</template>

<script setup>
import {useRoute} from 'vue-router';
import {fetched} from '../hacks.js';

const route = useRoute();

const code = fetched(async (fetch) => {
	if (route.params.datasetName && route.params.format) {
		const response = await fetch(`/api/datasets/${encodeURIComponent(route.params.datasetName)}/${encodeURIComponent(route.params.format)}`);
		return await response.text();
	}
});

</script>