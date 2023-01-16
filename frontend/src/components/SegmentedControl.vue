<template>
	<div class="segmented-control">
		<label v-for="option in options" :class="{'selected': modelValue === option}">
			<input type="radio" @input="$emit('update:modelValue', option)" :checked="modelValue === option">
			<slot :option="option">{{option}}</slot>
		</label>
	</div>
</template>

<script setup functional>
const {modelValue} = defineProps({
	options: {
		type: Array
	},
	modelValue: {}
});

defineEmits(['update:modelValue']);
</script>

<style scoped>

</style>