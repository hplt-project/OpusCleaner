<script>
export default {
  props: ['parameter', 'modelValue'],
  emits: ['update:modelValue']
}
</script>

<template>
	<input
		type="number"
		:value="modelValue"
		@input="$emit('update:modelValue', $event.target.value)"
		:min="parameter.min"
		:max="parameter.max"
		:step="0.1">
</template>