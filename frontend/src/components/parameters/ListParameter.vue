<script setup>
import IntParameter from './IntParameter.vue';
import FloatParameter from './FloatParameter.vue';
import StringParameter from './StringParameter.vue';
import BoolParameter from './BoolParameter.vue';
import TupleParameter from './TupleParameter.vue';
import { defaultValue } from '../../store/filtersteps.js';


const ParameterComponents = {
	'int': IntParameter,
	'float': FloatParameter,
	'str': StringParameter,
	'bool': BoolParameter,
	'tuple': TupleParameter,
	'list': undefined // TODO: Is there no better way to do this?
};

defineProps(['parameter', 'modelValue']);

defineEmits(['update:modelValue']);

</script>

<template>
	<ol>
		<li v-for="item, index in modelValue" :key="index">
			<component
				:is="ParameterComponents[parameter.parameter.type]"
				:parameter="parameter.parameter"
				:modelValue="item"
				@update:modelValue="$emit('update:modelValue', [...modelValue.slice(0, index), $event, ...modelValue.slice(index+1)])"
			></component>
			<button @click="$emit('update:modelValue', [...modelValue.slice(0, index), ...modelValue.slice(index+1)])">🗑️</button>
		</li>
	</ol>
	<button @click="$emit('update:modelValue', [...modelValue, defaultValue(parameter.parameter)])">➕</button>
</template>
