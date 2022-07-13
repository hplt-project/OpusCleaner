export default {
	props: {
		filters: Array,
		filterSteps: Array,
	},

	data() {
		return {};
	},

	components: {
		draggable
	},

	methods: {
		createFilterStep() {

		},
		addFilterStep() {

		}
	},

	template: `
		<div class="filters">
			<draggable tag="ul" class="available-filters"
				v-bind:modelValue="filters" item-key="name"
				v-bind:group="{name:'filters', pull:'clone', put:false}"
				v-bind:sort="false"
				v-bind:clone="createFilterStep">
				<template v-slot:item="{element:filter}">
					<li class="filter">
						<span v-bind:title="filter.description" class="filter-name">{{filter.name}}</span>
						<span class="filter-type">{{filter.type}}</span>
						<button v-on:click="addFilterStep(filter)" class="add-filter-btn">Add</button>
					</li>
				</template>
			</draggable>

			<draggable tag="ol" class="filter-steps"
				v-bind:modelValue="filterSteps" item-key="stamp" 
				v-on:update:modelValue="$emit('update:filterSteps', $event)"
				v-bind:group="{name:'filters'}"
				v-bind:multi-drag="true"
				v-bind:multi-drag-key="multiDragKey">
				<template v-slot:header>
					<li class="property-list">
						<header>
							<span>Sample</span>
						</header>
						<footer>
							<button v-on:click="selectedFilterStep={}">Show output at this stage</button>
						</footer>
					</li>
				</template>
				<template v-slot:item="{element:filterStep, index:i}">
					<li class="property-list">
						<header>
							<span>{{ filterStep.filter }}</span>
							<button v-on:click="removeFilterStep(i)">Remove</button>
						</header>
						<div v-if="filterRequiresLanguage(filterStep)">
							<label v-bind:for="`step-${i}-column`">Column</label>
							<select v-bind:id="`step-${i}-column`" v-model="filterStep.language">
								<option v-for="lang in languages">{{lang}}</option>
							</select>
						</div>
						<div v-for="(parameter, name) in filterDefinition(filterStep).parameters">
							<label v-bind:for="`step-${i}-${name}`">{{ name }}</label>
							<select v-if="parameter.type == 'str' && parameter.allowed_values" v-model="filterStep.parameters[name]" v-bind:id="`step-${i}-${name}`">
								<option v-for="value in parameter.allowed_values" v-bind:value="value">{{value}}</option>
							</select>
							<input v-else-if="parameter.type == 'bool'" type="checkbox" v-model="filterStep.parameters[name]" v-bind:id="`step-${i}-${name}`">
							<input v-else-if="parameter.type == 'int' || parameter.type == 'float'"
								type="number"
								v-model="filterStep.parameters[name]"
								v-bind:id="`step-${i}-${name}`"
								v-bind:min="parameter.min"
								v-bind:max="parameter.max"
								v-bind:step="parameter.type == 'int' ? 1 : 0.1">
							<input v-else type="text" v-model="filterStep.parameters[name]" v-bind:id="`step-${i}-${name}`">
							
							<small v-if="parameter.help" class="property-list-description">{{parameter.help}}</small>
						</div>
						<footer>
							<button v-on:click="selectedFilterStep=filterStep">Show output at this stage</button>
						</footer>
					</li>
				</template>
			</draggable>
		</div>
	</div>
	`

}