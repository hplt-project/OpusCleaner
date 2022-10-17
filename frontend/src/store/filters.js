import {ref} from 'vue';

const filters = ref([]);

async function fetchFilters() {
	const response = await fetch('/api/filters/');
	const filterDict = await response.json();

	// Turn the {name:Filter} map into a [Filter] list and fold the 'name' attribute into the Filter.name property.
	return Array.from(Object.entries(filterDict), ([name, value]) => Object.assign(value, {name}))
}

let filterRequest = null;

export function getFilters() {
	if (!filterRequest)
		filterRequest = fetchFilters().then(data => filters.value.splice(0, filters.length, ...data));

	return filters.value;
}