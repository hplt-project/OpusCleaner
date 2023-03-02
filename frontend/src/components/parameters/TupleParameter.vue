<script setup>
import IntParameter from './IntParameter.vue';
import FloatParameter from './FloatParameter.vue';
import StringParameter from './StringParameter.vue';
import BoolParameter from './BoolParameter.vue';
import {getUniqueId} from '../../hacks.js';

const ParameterComponents = {
	'int': IntParameter,
	'float': FloatParameter,
	'str': StringParameter,
	'bool': BoolParameter
};

defineProps(['parameter', 'modelValue']);

defineEmits(['update:modelValue']);

const uid = getUniqueId();

</script>

<template>
	<fieldset class="property-list">
		<legend><slot/></legend>
		<div v-for="(parameter, index) in parameter.parameters || []" :key="index">
			<component
				:id="`tuple-${uid}-${index}`"
				:is="ParameterComponents[parameter.type]"
				:parameter="parameter"
				:modelValue="modelValue[index]"
				@update:modelValue="$emit('update:modelValue', [...modelValue.slice(0, index), $event, ...modelValue.slice(index+1)])"
			>
				<label v-if="parameter.help" :for="`tuple-${uid}-${index}`">{{parameter.help}}</label>
			</component>
		</div>
	</fieldset>
</template>
