import {reactive} from 'vue';

const data = reactive({
	categories: [],
	mapping: {}
});

async function fetchCategories() {
	const response = await fetch('/api/categories/');
	return await response.json();
}

async function pushCategories() {
	const response = await fetch('/api/categories/', {
		method: 'PUT',
		headers: {
			'Content-Type': 'application/json',
			'Accept': 'application/json'
		},
		body: JSON.stringify(data)
	});

	// TODO: Handle `request.ok === false` somehow.

	return response;
}

let request = null;

function getData() {
	if (!request)
		request = fetchCategories().then(remote => Object.assign(data, remote));

	return data
}

export function getCategories() {
	return getData().categories;
}

export function getCategoriesForDataset(dataset) {
	const data = getData();

	// Look through all mappings, and return the category objects if the dataset
	// name is mentioned in the mapping section for it.
	return Object.entries(data.mapping).reduce((acc, [name, datasets]) => {
		if (datasets.includes(dataset.name))
			return [...acc, data.categories.find(category => category.name == name)]
		else
			return acc
	}, []);
}

export function setCategoriesForDataset(categories, dataset) {
	const names = new Set(categories.map(cat => cat.name));

	// Overly complicated way of adding/removing the dataset name from each of
	// the categories. I made a stupid server side API (but the file format is
	// nicely human readable now at least. But I could have solved this in Python!)
	getCategories().forEach(({name}) => {
		// If this category should have the dataset
		if (names.has(name)) {
			// … and there is no mapping for it yet
			if (!(name in data.mapping))
				data.mapping[name] = [dataset.name]
			// … and there is a mapping for it, but this dataset is not in it
			else if (!data.mapping[name].includes(dataset.name))
				data.mapping[name].push(dataset.name)
		} 
		// else if this category should not have this dataset
		// … and there is a mapping for this category
		else if (name in data.mapping) {
			let index
			while ((index = data.mapping[name].indexOf(dataset.name)) !== -1) {
				// … and this dataset is in that mapping, remove it.
				data.mapping[name].splice(index, 1);
			}
		}
	})

	pushCategories();
}