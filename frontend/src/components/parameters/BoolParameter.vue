<script>
export default {
  props: ['parameter', 'modelValue'],
  emits: ['update:modelValue']
}
</script>

<template>
	<input type="checkbox" :value="modelValue" @input="$emit('update:modelValue', $event.target.value)">
</template>
