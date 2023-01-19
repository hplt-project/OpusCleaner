<script setup>
import {filterRequiresLanguage, filterDefinition} from '../store/filters.js';
import {getUniqueId} from '../hacks.js';

const {open, languages, modelValue} = defineProps({
	open: Boolean,
	languages: Array,
	modelValue: Object
})

const uid = getUniqueId();
</script>

<template>
	<li>
		<details class="property-list">
			<summary>
				<slot name="header"></slot>
			</summary>
			<div v-if="filterRequiresLanguage(modelValue)">
				<label :for="`step-${uid}-column`">Column</label>
				<select :id="`step-${uid}-column`" v-model="modelValue.language">
					<option v-for="lang in languages" v-bind:key="lang">{{lang}}</option>
				</select>
			</div>
			<div v-for="(parameter, name) in filterDefinition(modelValue)?.parameters || {}" v-bind:key="name">
				<label :for="`step-${uid}-${name}`">{{ name }}</label>
				<select
					v-if="parameter.type == 'str' && parameter.allowed_values"
					v-bind:id="`step-${uid}-${name}`"
					v-bind:value="modelValue.parameters[name]"
					v-on:input="$emit('update:modelValue', {
						...modelValue,
						parameters: {
							...modelValue.parameters,
							[name]:$event.target.value
						}
					})">
					<option
						v-for="value in parameter.allowed_values"
						v-bind:key="value"
						v-bind:value="value">{{value}}</option>
				</select>
				<input
					v-else-if="parameter.type == 'bool'"
					type="checkbox"
					v-bind:id="`step-${uid}-${name}`"
					v-bind:checked="modelValue.parameters[name]"
					v-on:input="$emit('update:modelValue', {
						...modelValue,
						parameters: {
							...modelValue.parameters,
							[name]:$event.target.checked
						}
					})">
				<input
					v-else-if="parameter.type == 'int' || parameter.type == 'float'"
					type="number"
					v-bind:id="`step-${uid}-${name}`"
					v-bind:min="parameter.min"
					v-bind:max="parameter.max"
					v-bind:step="parameter.type == 'int' ? 1 : 0.1"
					v-bind:value="modelValue.parameters[name]"
					v-on:input="$emit('update:modelValue', {
						...modelValue,
						parameters: {
							...modelValue.parameters,
							[name]:$event.target.value
						}
					})">
				<input
					v-else
					type="text"
					v-bind:id="`step-${uid}-${name}`"
					v-bind:value="modelValue.parameters[name]"
					v-on:input="$emit('update:modelValue', {
						...modelValue,
						parameters: {
							...modelValue.parameters,
							[name]:$event.target.value
						}
					})">
				<small v-if="parameter.help" class="property-list-description">{{parameter.help}}</small>
			</div>
			<footer>
				<slot name="footer"></slot>
			</footer>
		</details>
	</li>
</template>

<style scoped>
input[type=number] {
	width: 5em;
}

input[type=checkbox] {
	width: 1em;
}

.property-list {
	border: 1px solid var(--border-color);
	border-radius: 4px;
}

.property-list > *:not(:last-child) {
	border-bottom: 1px solid var(--border-color);
}

.property-list > summary {
	background: var(--border-color);
}

.property-list > * > *:first-child {
	margin-left: 0;
}

.property-list > summary > button {
	flex: 0;
}

.property-list > * {
	padding: 0.5em;
	display: flex;
	flex-wrap: wrap;
	justify-content: space-between;
}

.property-list > summary > *,
.property-list > header > *,
.property-list > footer > * {
	flex: 1;
}

.property-list > * > * {
	flex: 0;
	align-self: center;
	margin-left: 0.5em;
}

.property-list > * > small {
	flex: 1 0 100%;
}

.property-list > * > input[type=checkbox] {
	flex-basis: 1em;
}
</style>