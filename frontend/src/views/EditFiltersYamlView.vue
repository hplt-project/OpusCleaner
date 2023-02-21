<template>
	<pre><code>{{ yaml }}</code></pre>
</template>

<script setup>
import {watchEffect, ref, unref} from 'vue';
import {useRoute} from 'vue-router';

const route = useRoute();

function fetched(fn) {
	const val = ref();

	watchEffect((onCleanup) => {
		const fetcher = (url, options) => {
			const abort = new AbortController();
			onCleanup(() => abort.abort());

			const signal = abort.signal;
			return fetch(url, {...options, signal});
		};

		Promise.resolve(fn(fetcher)).then(out => {
			val.value = out
		});
	});

	return val;
}

const yaml = fetched(async (fetch) => {
	const response = await fetch(`/api/datasets/${encodeURIComponent(route.params.datasetName)}/configuration-for-opusfilter.yaml`);
	return await response.text()
});

</script>