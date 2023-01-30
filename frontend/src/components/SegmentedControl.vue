<template>
	<div class="segmented-control">
		<label v-for="option in options" :key="option" :class="{'selected': modelValue === option}">
			<input type="radio" @input="$emit('update:modelValue', option)" :checked="modelValue === option">
			<span><slot :option="option">{{option}}</slot></span>
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
.segmented-control {
	--border-color: #1c3948;
	--active-color: #e4960e;
	--color: #17223d;

	display: inline-flex;
	align-items: stretch;
	flex-direction: row;
	flex-wrap: nowrap;
}

.segmented-control > label:first-child > span {
	border-radius: 4px 0 0 4px;
}

.segmented-control > label:last-child > span {
	border-radius: 0 4px 4px 0;
}

.segmented-control > label:not(:last-child) > span {
	border-right: 1px solid var(--border-color);
}

.segmented-control > label {
	flex: 1;
	display: flex;
	white-space: nowrap;
	line-height: 2em;
	cursor: pointer;
}

.segmented-control > label > input {
	display: none;
}

.segmented-control > label > span {
	display: inline-block;
	padding: 0 1em;

	background: var(--color);
	color: var(--active-color);
}

.segmented-control > label:hover > span {
/*	box-shadow: inset 0 0 2px 2px rgba(255, 255, 255, 0.5);*/
/*	text-decoration: underline;*/
}

.segmented-control > label > input:checked + span {
	background: var(--active-color);
	color: var(--color);
}
</style>