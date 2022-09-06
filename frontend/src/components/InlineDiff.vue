<script functional setup>
import { h, defineProps, computed } from "vue";
import {diff} from "../diff.js";

const {current, previous} = defineProps({
	current: {
		type: String,
		required: true
	},
	previous: {
		type: String,
		required: true
	}
})

const mutations = computed(() => {
	return diff(previous.split(''), current.split(''), {
		equals: (a,b) => a == b,
		maxEditLength: Math.max(previous.length, current.length) * 0.5
	});
})
</script>

<template>
	<span v-if="!mutations">
		<del>{{ previous }}</del>
		<ins>{{ current }}</ins>
	</span>
	<span v-else>
		<template v-for="mutation in mutations">
			<component v-if="mutation.added || mutation.removed" :is="mutation.added ? 'ins' : 'del'">{{ mutation.value.join('') }}</component>
			<template v-else>{{ mutation.value.join('') }}</template>
		</template>
	</span>
</template>
