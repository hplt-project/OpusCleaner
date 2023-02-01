<script>
export default {
  props: ['parameter', 'modelValue'],
  emits: ['update:modelValue']
}
</script>

<template>
	<slot/>
	<select
		v-if="parameter.allowed_values"
		v-bind="$attrs"
		v-bind:value="modelValue"
		v-on:input="$emit('update:modelValue', $event.target.value)">
		<option v-for="value in parameter.allowed_values" :value="value" :key="value">{{value}}</option>
	</select>
	<input
		v-else
		type="text"
		v-bind="$attrs"
		v-bind:value="modelValue"
		v-on:input="$emit('update:modelValue', $event.target.value)"/>
</template>
