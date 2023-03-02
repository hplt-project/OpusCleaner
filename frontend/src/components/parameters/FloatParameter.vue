<script>
export default {
  props: ['parameter', 'modelValue'],
  emits: ['update:modelValue']
}
</script>

<template>
	<slot/>
	<input
		type="number"
		v-bind="$attrs"
		v-bind:value="modelValue"
		v-on:input="$emit('update:modelValue', $event.target.value)"
		v-bind:min="parameter.min"
		v-bind:max="parameter.max"
		v-bind:step="0.1">
</template>