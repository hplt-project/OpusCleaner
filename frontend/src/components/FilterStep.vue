<script setup>
import {filterRequiresLanguage, filterDefinition} from '../store/filters.js';
import {getUniqueId} from '../hacks.js';
import IntParameter from '../components/parameters/IntParameter.vue';
import FloatParameter from '../components/parameters/FloatParameter.vue';
import StringParameter from '../components/parameters/StringParameter.vue';
import BoolParameter from '../components/parameters/BoolParameter.vue';

const ParameterComponents = {
	'int': IntParameter,
	'float': FloatParameter,
	'str': StringParameter,
	'bool': BoolParameter,
};

const {open, languages, modelValue} = defineProps({
	open: Boolean,
	languages: Array,
	modelValue: Object
})

defineEmits(['update:modelValue', 'update:open']);

const uid = getUniqueId();
</script>

<template>
	<li>
		<details class="property-list" @toggle="$emit('update:open', $event.target.open)" :open="open">
			<summary>
				<slot name="header"></slot>
			</summary>
			<div v-if="filterRequiresLanguage(modelValue)">
				<label :for="`step-${uid}-column`">Column</label>
				<select :id="`step-${uid}-column`"
					v-bind:value="modelValue.language"
					v-on:input="$emit('update:modelValue', {
						...modelValue,
						language: $event.target.value
					})">
					<option v-for="lang in languages" v-bind:key="lang">{{lang}}</option>
				</select>
			</div>
			<div v-for="(parameter, name) in filterDefinition(modelValue)?.parameters || {}" v-bind:key="name">
				<label :for="`step-${uid}-${name}`">{{ name }}</label>
				<component
					:is="ParameterComponents[parameter.type]"
					v-bind:id="`step-${uid}-${name}`"
					:parameter="parameter"
					v-bind:modelValue="modelValue.parameters[name]"
					v-on:update:modelValue="$emit('update:modelValue', {
						...modelValue,
						parameters: {
							...modelValue.parameters,
							[name]: $event
						}
					})"/>
				<small v-if="parameter.help" class="property-list-description">{{parameter.help}}</small>
			</div>
			<footer>
				<slot name="footer"></slot>
			</footer>
		</details>
	</li>
</template>

<style scoped>
@import '../css/property-list.css';
</style>