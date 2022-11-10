<script setup>
import IntParameter from './IntParameter.vue';
import FloatParameter from './FloatParameter.vue';
import StringParameter from './StringParameter.vue';
import BoolParameter from './BoolParameter.vue';

const ParameterComponents = {
	'int': IntParameter,
	'float': FloatParameter,
	'str': StringParameter,
	'bool': BoolParameter
};

defineProps(['parameter', 'modelValue']);

defineEmits(['update:modelValue']);

</script>

<template>
	<fieldset>
		<div v-for="(parameter, index) in parameter.parameters || []" :key="index">
			<component
				:is="ParameterComponents[parameter.type]"
				:parameter="parameter"
				:modelValue="modelValue[index]"
				@update:modelValue="$emit('update:modelValue', [...modelValue.slice(0, index), $event.target.value, ...modelValue.slice(index+1)])"
			></component>
			<small v-if="parameter.help" class="property-list-description">{{parameter.help}}</small>
		</div>
	</fieldset>
</template>
