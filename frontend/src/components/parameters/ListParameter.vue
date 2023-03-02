<script setup>
import {unref} from 'vue';
import IntParameter from './IntParameter.vue';
import FloatParameter from './FloatParameter.vue';
import StringParameter from './StringParameter.vue';
import BoolParameter from './BoolParameter.vue';
import TupleParameter from './TupleParameter.vue';
import { defaultValue } from '../../store/filtersteps.js';
import {PlusIcon, TrashIcon} from 'vue3-feather';
import draggable from 'vuedraggable';


const ParameterComponents = {
	'int': IntParameter,
	'float': FloatParameter,
	'str': StringParameter,
	'bool': BoolParameter,
	'tuple': TupleParameter,
	'list': undefined // TODO: Is there no better way to do this?
};

const props = defineProps(['parameter', 'modelValue']);

defineEmits(['update:modelValue']);

function getItemIndex(item) {
	return props.modelValue.indexOf(item).toString();
}

</script>

<template>
	<fieldset>
		<legend>
			<slot/>
		</legend>
		<draggable
			tag="ol"
			class="parameter-list"
			v-bind:item-key="getItemIndex"
			v-bind:modelValue="props.modelValue"
			v-on:update:modelValue="$emit('update:modelValue', $event)">
			<template v-slot:item="{element, index}">
				<li>
					<component
						:is="ParameterComponents[parameter.parameter.type]"
						:parameter="parameter.parameter"
						:modelValue="element"
						@update:modelValue="$emit('update:modelValue', [...props.modelValue.slice(0, index), $event, ...props.modelValue.slice(index+1)])"
					>
						Item {{ index + 1}}
						<button class="icon-button" @click="$emit('update:modelValue', [...props.modelValue.slice(0, index), ...props.modelValue.slice(index+1)])"><TrashIcon size="16"/></button>
					</component>					
				</li>
			</template>
			<template v-slot:footer>
				<li><button class="add-item-button" @click="$emit('update:modelValue', [...props.modelValue, defaultValue(parameter.parameter)])"><PlusIcon size="16"/> Add item</button></li>
			</template>
		</draggable>
		
	</fieldset>
</template>

<style scoped>
legend {
	padding: 0;
}

legend .icon-button {
	margin-left: .4em;
}

.parameter-list {
	list-style: none;
}

.add-item-button {
	display: flex;
	padding: 0.4em;
	margin: 0.2em auto;
}

</style>
