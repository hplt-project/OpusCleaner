<script>
export default {
  props: ['parameter', 'modelValue'],
  emits: ['update:modelValue']
}
</script>

<template>
  <slot/>
	<input
    type="checkbox"
    v-bind="$attrs"
    v-bind:value="modelValue"
    v-on:input="$emit('update:modelValue', $event.target.value)"/>
</template>
