<script>
export default {
  props: ['parameter', 'modelValue'],
  emits: ['update:modelValue']
}
</script>

<template>
	<select v-if="parameter.allowed_values" :value="modelValue" @input="$emit('update:modelValue', $event.target.value)">
		<option v-for="value in parameter.allowed_values" :value="value" :key="value">{{value}}</option>
	</select>
	<input v-else type="text" :value="modelValue" @input="$emit('update:modelValue', $event.target.value)">
</template>
