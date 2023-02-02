<template>
	<pre><code>{{ yaml }}</code></pre>
</template>

<script setup>
import {computed, unref} from 'vue';
import {useRoute} from 'vue-router';
import {getPipeline} from '../store/filtersteps.js';

const route = useRoute();

const pipeline = getPipeline({name: route.params.datasetName});

const yaml = computed(() => {
	return JSON.stringify({
		version: unref(pipeline).version,
		files: unref(pipeline).files,
		filters: unref(unref(pipeline).filters.steps)
	}, null, '    ');
});

</script>